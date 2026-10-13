# -*- coding: utf-8 -*-
"""Ads ops for the google-ads and facebook-ads agents.

One small, dependency-free tool for three things a paid-ads setup run by
agents needs: a regular cadence, a change ledger you can roll back from,
and historical versions of every file the agents rely on. Run from the
project root:

    python -I ads-ops/ads_ops.py due            # what is overdue (also run by the SessionStart hook)
    python -I ads-ops/ads_ops.py done <task> [--note "..."]
    python -I ads-ops/ads_ops.py tasks          # the whole cadence table

    # change ledger. The agent writes the row BEFORE the change, with the value read from the UI:
    python -I ads-ops/ads_ops.py ledger add --channel meta --account market-a \\
        --object MKA_acq_example_2610_ios --field "daily budget" \\
        --before "300/day" --after "345/day" --why "best cost per activation, 7 days" \\
        --rollback-if "cost per activation > 20 after 7 days" --review-by 2026-10-20
    # the OWNER approves it, in their own terminal (agents never run this):
    python -I ads-ops/ads_ops.py ledger approve <id> --by "owner name"
    python -I ads-ops/ads_ops.py ledger done <id>       # after the change (refused before approval)
    python -I ads-ops/ads_ops.py ledger verify <id>     # after the reload read-back (refused before done)
    python -I ads-ops/ads_ops.py ledger keep <id> | rolled-back <id>   # at the review date
    python -I ads-ops/ads_ops.py ledger cancel <id>     # a planned/approved change that will not happen
    python -I ads-ops/ads_ops.py ledger rollback <id>   # prints the exact way back
    python -I ads-ops/ads_ops.py ledger list [--open]

    # file versions (the PreToolUse hook does this automatically before Edit/Write)
    python -I ads-ops/ads_ops.py snapshot <file>
    python -I ads-ops/ads_ops.py versions <file>
    python -I ads-ops/ads_ops.py restore <file> <version>   # snapshots the current file first

What is enforced here: the ledger's own bookkeeping (required fields, the status
order planned > approved > done > verified > kept/rolled_back, an approval that is
recorded by a separate command with a name and a timestamp). What is NOT: nothing
here touches or watches an ad account, so it cannot stop a change made in the UI
without a row, and it cannot prove who ran `approve`. Those parts are procedure.
"""
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('ADS_OPS_ROOT') or os.path.abspath(os.path.join(HERE, '..'))   # project root
CADENCE = os.path.join(HERE, 'cadence.json')
LEDGER_JSONL = os.path.join(HERE, 'changes.jsonl')
LEDGER_MD = os.path.join(HERE, 'change-ledger.md')
LOCK = os.path.join(HERE, '.ads_ops.lock')
VERSIONS = os.path.join(ROOT, '.versions')
VERSIONS_KEEP_DEFAULT = 50

# Files whose every edit gets a version first (paths relative to ROOT, forward slashes).
# Override with a "protected" list of regexes in cadence.json.
PROTECTED_DEFAULT = [
    r'^\.claude/agents/[^/]+\.md$',
    r'^\.claude/skills/[^/]+/SKILL\.md$',
    r'^ads-ops/(goals|README|watchlist|learnings)\.md$',
    r'^ads-ops/cadence\.json$',
    r'^paid-ads-agent-playbook\.md$',
    r'^[^/]*-status\.md$',
]

# Ledger status machine: which command moves which status where.
TRANSITIONS = {
    'approve': ({'planned'}, 'approved'),
    'done': ({'approved'}, 'done'),
    'verify': ({'done'}, 'verified'),
    'keep': ({'verified'}, 'kept'),
    'rolled-back': ({'verified'}, 'rolled_back'),
    'cancel': ({'planned', 'approved'}, 'cancelled'),
}
OPEN_STATUSES = ('planned', 'approved', 'done', 'verified')


def protected():
    try:
        return load_cadence().get('protected') or PROTECTED_DEFAULT
    except Exception:
        return PROTECTED_DEFAULT


def versions_keep():
    v = os.environ.get('ADS_OPS_VERSIONS_KEEP')
    if not v:
        try:
            v = load_cadence().get('versions_keep')
        except Exception:
            v = None
    try:
        return max(1, int(v)) if v else VERSIONS_KEEP_DEFAULT
    except (TypeError, ValueError):
        return VERSIONS_KEEP_DEFAULT


def today():
    return dt.date.today()


def now():
    return dt.datetime.now().isoformat(timespec='seconds')


def rel(path):
    p = os.path.abspath(path)
    try:
        r = os.path.relpath(p, ROOT)
    except ValueError:                                       # another drive on Windows
        return None
    if r == '..' or r.startswith('..' + os.sep) or r.startswith('../'):
        return None
    return r.replace('\\', '/')


# ---------------------------------------------------------------- files and locking

def atomic_write(path, text):
    """Write to a temp file in the same folder, then os.replace: a crash or a second
    process never leaves a half-written file behind."""
    d = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.', suffix='.tmp', dir=d)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        for i in range(20):                                  # Windows: a reader may hold the file briefly
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if i == 19:
                    raise
                time.sleep(0.05)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class Lock:
    """A lock file next to the ledger (O_CREAT|O_EXCL). Waits up to `timeout` seconds;
    a lock older than `stale` seconds is treated as left over from a crash."""

    def __init__(self, path=LOCK, timeout=15.0, stale=120.0):
        self.path, self.timeout, self.stale = path, timeout, stale

    def __enter__(self):
        start = time.time()
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f'{os.getpid()} {now()}'.encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > self.stale:
                        os.unlink(self.path)
                        continue
                except OSError:
                    continue
                if time.time() - start > self.timeout:
                    raise SystemExit(f'ads-ops is locked by another process ({self.path}); '
                                     'try again, or delete the file if no other ads_ops.py is running')
                time.sleep(0.05)

    def __exit__(self, *a):
        try:
            os.unlink(self.path)
        except OSError:
            pass


# ---------------------------------------------------------------- cadence

def load_cadence():
    with open(CADENCE, encoding='utf-8') as f:
        return json.load(f)


def save_cadence(c):
    atomic_write(CADENCE, json.dumps(c, ensure_ascii=False, indent=1) + '\n')


def overdue(c):
    out = []
    for t in c['tasks']:
        last = t.get('last_run')
        due_on = (dt.date.fromisoformat(last) + dt.timedelta(days=t['every_days'])) if last else None
        if due_on is None or due_on <= today():
            late = (today() - due_on).days if due_on else None
            out.append((t, late))
    out.sort(key=lambda x: (-(x[1] if x[1] is not None else 999), x[0]['id']))
    return out


def review_overdue(e):
    """A verified row whose review date has come: someone must keep it or roll it back."""
    rb = e.get('review_by')
    if e.get('status') != 'verified':
        return False
    if not rb:
        return True                                          # an old row without a date: always ask
    try:
        return dt.date.fromisoformat(rb) <= today()
    except ValueError:
        return True


def ledger_summary(entries):
    """(counts by what is waiting, list of overdue reviews)."""
    waiting = {
        'waiting for the owner\'s approval': [e for e in entries if e['status'] == 'planned'],
        'approved, not made yet': [e for e in entries if e['status'] == 'approved'],
        'made, waiting for read-back': [e for e in entries if e['status'] == 'done'],
    }
    reviews = [e for e in entries if review_overdue(e)]
    return waiting, reviews


def cmd_due(args):
    quiet = '--quiet' in args
    try:
        c = load_cadence()
    except Exception as e:                                   # never break a session start
        print(f'[ads-ops] cadence.json unreadable: {e}')
        return 0
    od = overdue(c)
    try:
        entries = read_ledger()
    except Exception as e:
        print(f'[ads-ops] changes.jsonl unreadable: {e}')
        entries = []
    waiting, reviews = ledger_summary(entries)
    n_wait = sum(len(v) for v in waiting.values())
    if not od and not n_wait and not reviews:
        if not quiet:
            print('[ads-ops] nothing overdue, no open ledger rows.')
        return 0
    if quiet:                                                # SessionStart: one short line, details on demand
        items = ', '.join(t['id'] + ('' if late is None else f' (+{late} d)') for t, late in od)
        print(f'[ads-ops] Due: {items}.' if od else '[ads-ops]', end=' ')
        parts = [f'{len(v)} {k}' for k, v in waiting.items() if v]
        if reviews:
            parts.append(f'{len(reviews)} past their review date (keep or roll back)')
        if parts:
            print('Ledger: ' + '; '.join(parts) + '.', end=' ')
        print('If this session is about ads (or it is the first session of the day), offer it to the owner in one sentence; '
              'details: python -I ads-ops/ads_ops.py due. Nothing live without their explicit yes.')
        return 0
    print('[ads-ops] Regular tasks of the ads agents that are due (ads-ops/README.md).')
    print('Offer them to the owner in one sentence at the start of the session, start nothing live without their yes:')
    for t, late in od:
        when = 'never run' if late is None else (f'{late} d overdue' if late > 0 else 'today')
        print(f"  - {t['id']} ({t['owner']}, every {t['every_days']} d, {when}): {t['what']}")
    for k, v in waiting.items():
        if v:
            print(f"  - change ledger, {k}: {', '.join(e['id'] for e in v)}")
    for e in reviews:
        print(f"  - change ledger, review due {e.get('review_by') or '(no date)'}: {e['id']} "
              f"{e['object']} {e['field']} {e['before']} -> {e['after']}; rollback if {e['rollback_if']}. "
              f"Owner decides: ledger keep {e['id']} / ledger rollback {e['id']}")
    return 0


def cmd_done(args):
    if not args:
        print('usage: done <task-id> [--note "..."]')
        return 2
    tid = args[0]
    note = opt(args[1:], 'note', False)
    with Lock():
        c = load_cadence()
        for t in c['tasks']:
            if t['id'] == tid:
                # the PreToolUse hook only sees Edit/Write, not this script: version the file ourselves
                snapshot(CADENCE, reason=f'before ads_ops done {tid}')
                t['last_run'] = today().isoformat()
                if note:
                    t['last_note'] = note
                save_cadence(c)
                print(f'{tid}: last_run = {t["last_run"]}')
                return 0
    print(f'unknown task {tid}; known: ' + ', '.join(t['id'] for t in c['tasks']))
    return 2


def cmd_tasks(args):
    c = load_cadence()
    for t in c['tasks']:
        print(f"{t['id']:<28} every {t['every_days']:>3} d  last {t.get('last_run') or '-':<10}  {t['owner']}: {t['what']}")
    return 0


# ---------------------------------------------------------------- ledger

def read_ledger():
    if not os.path.exists(LEDGER_JSONL):
        return []
    with open(LEDGER_JSONL, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def write_ledger(entries):
    atomic_write(LEDGER_JSONL, ''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in entries))
    render_ledger(entries)


def cell(s):
    return str(s or '').replace('|', '/').replace('\n', ' ')


def render_ledger(entries):
    lines = [
        '# Ads change ledger',
        '',
        'Generated from `changes.jsonl` by `ads_ops.py` - do not edit by hand. Newest on top.',
        'Every live change to Google Ads / Meta / the attribution tool gets a row **before** it is made, with the value read from the UI.',
        'Status: `planned` (written by the agent) > `approved` (by the owner, `ledger approve <id> --by <name>`) > `done` (made) > '
        '`verified` (read back after reload) > `kept` / `rolled_back` (decided at the review date). `cancelled` = not made.',
        '',
        '| ID | Date | Channel | Account | Object | Field | Before | After | Why | Approved | Rollback if | Review by | Status | Snapshot |',
        '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|',
    ]
    for e in reversed(entries):
        approved = f"{e['approved_by']} {e.get('approved_at', '')}".strip() if e.get('approved_by') else (e.get('approved') or '')
        row = dict(e, approved=approved)
        lines.append('| ' + ' | '.join(cell(row.get(k)) for k in (
            'id', 'date', 'channel', 'account', 'object', 'field', 'before', 'after', 'why',
            'approved', 'rollback_if', 'review_by', 'status', 'snapshot')) + ' |')
    atomic_write(LEDGER_MD, '\n'.join(lines) + '\n')


def opt(args, name, required=True):
    """Value of --name. A flag followed by nothing or by another --flag is an error,
    so `--before --after 2` can never record "--after" as the old value."""
    flag = '--' + name
    if flag in args:
        i = args.index(flag) + 1
        if i >= len(args) or args[i].startswith('--'):
            raise SystemExit(f'{flag} needs a value')
        return args[i]
    if required:
        raise SystemExit(f'missing {flag}')
    return ''


def next_id(entries):
    prefix = today().strftime('%Y%m%d') + '-'
    seqs = [int(e['id'][len(prefix):]) for e in entries
            if str(e.get('id', '')).startswith(prefix) and e['id'][len(prefix):].isdigit()]
    return f'{prefix}{(max(seqs) if seqs else 0) + 1:02d}'


def find(entries, eid):
    for e in entries:
        if e['id'] == eid:
            return e
    raise SystemExit(f'no ledger entry {eid}')


def cmd_ledger(args):
    if not args:
        print(__doc__)
        return 2
    sub, rest = args[0], args[1:]
    if sub == 'add':
        if '--approved' in rest:
            raise SystemExit('--approved is not accepted on add: the owner records the approval separately with '
                             '`ledger approve <id> --by <name>`')
        for f in ('before', 'after', 'rollback-if', 'review-by'):
            if not opt(rest, f, False).strip():
                raise SystemExit(f'--{f} is required: no ledger row without the old value, the new value, '
                                 'a rollback trigger and a review date')
        review_by = opt(rest, 'review-by')
        try:
            if dt.date.fromisoformat(review_by) < today():
                raise SystemExit(f'--review-by {review_by} is in the past')
        except ValueError:
            raise SystemExit(f'--review-by must be a date, YYYY-MM-DD (got {review_by!r})')
        fields = {
            'channel': opt(rest, 'channel'), 'account': opt(rest, 'account'),
            'object': opt(rest, 'object'), 'field': opt(rest, 'field'),
            'before': opt(rest, 'before'), 'after': opt(rest, 'after'),
            'why': opt(rest, 'why', False), 'rollback_if': opt(rest, 'rollback-if'),
            'review_by': review_by, 'snapshot': opt(rest, 'snapshot', False),
        }
        with Lock():
            entries = read_ledger()
            e = {'id': next_id(entries), 'date': today().isoformat(), **fields,
                 'approved_by': '', 'approved_at': '',
                 'status': 'planned', 'history': [[now(), 'planned']]}
            entries.append(e)
            write_ledger(entries)
        print(f"ledger {e['id']} planned. Next: the owner approves it in their own terminal "
              f"(ledger approve {e['id']} --by <name>); after the change: ledger done {e['id']}; "
              f"after the reload read-back: ledger verify {e['id']}")
        return 0
    if sub == 'list':
        only_open = '--open' in rest
        for e in read_ledger():
            if only_open and e['status'] not in OPEN_STATUSES:
                continue
            flag = '  REVIEW DUE' if review_overdue(e) else ''
            print(f"{e['id']} {e['status']:<11} {e['channel']}/{e['account']} {e['object']} {e['field']}: "
                  f"{e['before']} -> {e['after']}  (rollback if {e['rollback_if']}; review by {e.get('review_by') or '-'}){flag}")
        return 0
    if sub in TRANSITIONS:
        if not rest or rest[0].startswith('--'):
            raise SystemExit(f'usage: ledger {sub} <id>' + (' --by <name>' if sub == 'approve' else ''))
        allowed, new = TRANSITIONS[sub]
        by = opt(rest[1:], 'by', sub == 'approve')
        with Lock():
            entries = read_ledger()
            e = find(entries, rest[0])
            if e['status'] not in allowed:
                hint = {'done': 'it needs the owner\'s approval first (ledger approve <id> --by <name>)',
                        'verify': 'mark it done first, after the change is made',
                        'keep': 'verify it first', 'rolled-back': 'verify it first'}.get(sub, '')
                raise SystemExit(f"{e['id']} is {e['status']}; `ledger {sub}` needs status "
                                 f"{' or '.join(sorted(allowed))}" + (f': {hint}' if hint else ''))
            if sub == 'approve':
                if not by.strip():
                    raise SystemExit('--by needs the approver\'s name')
                e['approved_by'], e['approved_at'] = by.strip(), now()
            e['status'] = new
            e.setdefault('history', []).append([now(), new] + ([by] if by else []))
            write_ledger(entries)
        print(f"{e['id']}: {new}" + (f" by {e['approved_by']} at {e['approved_at']}" if sub == 'approve' else ''))
        return 0
    if sub == 'rollback':
        if not rest:
            raise SystemExit('usage: ledger rollback <id>')
        e = find(read_ledger(), rest[0])
        print(f"Rollback plan for {e['id']} ({e['channel']} / {e['account']}):")
        print(f"  1. Ask the owner for an explicit yes (rollback is a live change too).")
        print(f"  2. Open {e['object']} and read the current value of '{e['field']}' (expected: {e['after']}).")
        print(f"     If it is not {e['after']}, someone changed it since: stop and report, do not overwrite.")
        print(f"  3. Write a new ledger entry: --before \"{e['after']}\" --after \"{e['before']}\" "
              f"--why \"rollback of {e['id']}\" --rollback-if \"...\" --review-by <date>; the owner approves it.")
        print(f"  4. Set '{e['field']}' back to: {e['before']}  (snapshot: {e.get('snapshot') or 'none'}).")
        print(f"  5. Reload, read it back, then: ledger done/verify <new id> and ledger rolled-back {e['id']}.")
        print("  Google Ads: Change history can undo some changes directly; Meta: Activity history shows the old value but has no undo.")
        return 0
    print(__doc__)
    return 2


# ---------------------------------------------------------------- versions

def version_dir(r):
    return os.path.join(VERSIONS, *r.split('/'))


def read_index(d):
    idx = os.path.join(d, 'index.jsonl')
    if not os.path.exists(idx):
        return []
    with open(idx, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def version_list(d, ext):
    """Version files of one protected file, oldest first (index.jsonl order)."""
    names = [x['version'] + ext for x in read_index(d)]
    return [n for n in names if os.path.isfile(os.path.join(d, n))]


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def prune(d, ext, keep):
    """Keep the newest `keep` versions of one file; drop older files and their index rows."""
    idx = read_index(d)
    if len(idx) <= keep:
        return 0
    drop, kept = idx[:-keep], idx[-keep:]
    for x in drop:
        try:
            os.unlink(os.path.join(d, x['version'] + ext))
        except OSError:
            pass
    atomic_write(os.path.join(d, 'index.jsonl'), ''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in kept))
    return len(drop)


def snapshot(path, reason='manual'):
    r = rel(path)
    if r is None or not os.path.isfile(path):
        return None
    d = version_dir(r)
    os.makedirs(d, exist_ok=True)
    ext = os.path.splitext(path)[1]
    existing = version_list(d, ext)
    if existing and sha(os.path.join(d, existing[-1])) == sha(path):
        return None                                          # identical to the latest version
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    dst, n = os.path.join(d, stamp + ext), 1
    while os.path.exists(dst):                               # two versions in the same second
        stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S') + f'-{n}'
        dst, n = os.path.join(d, stamp + ext), n + 1
    shutil.copy2(path, dst)
    with open(os.path.join(d, 'index.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps({'version': stamp, 'reason': reason}, ensure_ascii=False) + '\n')
    prune(d, ext, versions_keep())
    return dst


def cmd_snapshot(args):
    for p in args:
        dst = snapshot(p)
        print(f'{p}: ' + (f'saved {rel(dst)}' if dst else 'unchanged since last version (or not a file under the project root)'))
    return 0


def cmd_versions(args):
    r = rel(args[0]) if args else None
    d = version_dir(r) if r else None
    if not d or not os.path.isdir(d):
        print('no versions')
        return 0
    for x in version_list(d, os.path.splitext(args[0])[1]):
        print(os.path.splitext(x)[0], os.path.getsize(os.path.join(d, x)), 'B')
    return 0


def cmd_restore(args):
    if len(args) < 2:
        raise SystemExit('usage: restore <file> <version>')
    path, ver = args[0], args[1]
    r = rel(path)
    if r is None:
        raise SystemExit(f'{path} is outside the project root ({ROOT}); versions exist only for files inside it')
    src = os.path.join(version_dir(r), ver + os.path.splitext(path)[1])
    if not os.path.isfile(src):
        raise SystemExit(f'no version {ver} for {r} (see: versions {r})')
    snapshot(path, reason=f'before restore of {ver}')
    shutil.copy2(src, path)
    print(f'{r} restored to {ver} (the previous content was versioned first)')
    return 0


def cmd_hook_snapshot(args):
    """PreToolUse hook for Edit|Write|NotebookEdit: version protected files. Never blocks.
    It only sees those tools: an edit made through a shell command is not versioned."""
    try:
        data = json.loads(sys.stdin.buffer.read().decode('utf-8', 'replace') or '{}')
        ti = data.get('tool_input') or {}
        path = ti.get('file_path') or ti.get('notebook_path')
        if path:
            r = rel(path)
            if r and any(re.match(p, r) for p in protected()):
                snapshot(path, reason=f"before {data.get('tool_name', 'edit')}")
    except Exception:
        pass
    return 0


def main(argv):
    if not argv or argv[0] in ('-h', '--help', 'help'):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    fn = {'due': cmd_due, 'done': cmd_done, 'tasks': cmd_tasks, 'ledger': cmd_ledger,
          'snapshot': cmd_snapshot, 'versions': cmd_versions, 'restore': cmd_restore,
          'hook-snapshot': cmd_hook_snapshot}.get(cmd)
    if not fn:
        print(__doc__)
        return 2
    return fn(args)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

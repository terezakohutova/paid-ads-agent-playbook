# -*- coding: utf-8 -*-
"""Ads ops for the google-ads and facebook-ads agents.

One small, dependency-free tool for three things a paid-ads setup run by
agents needs: a regular cadence, a change ledger you can roll back from,
and historical versions of every file the agents rely on. Run from the
project root:

    python -I ads-ops/ads_ops.py due            # what is overdue (also run by the SessionStart hook)
    python -I ads-ops/ads_ops.py done <task> [--note "..."]
    python -I ads-ops/ads_ops.py tasks          # the whole cadence table

    # change ledger: write the entry BEFORE the change, with the value read from the UI
    python -I ads-ops/ads_ops.py ledger add --channel meta --account market-a \
        --object MKA_acq_example_2610_ios --field "daily budget" \
        --before "300/day" --after "345/day" --why "best cost per activation, 7 days" \
        --approved "owner 2026-10-12" --rollback-if "cost per activation > 20 after 7 days"
    python -I ads-ops/ads_ops.py ledger verify <id>    # after the reload read-back
    python -I ads-ops/ads_ops.py ledger rollback <id>  # prints the exact way back
    python -I ads-ops/ads_ops.py ledger list [--open]

    # file versions (the PreToolUse hook does this automatically before Edit/Write)
    python -I ads-ops/ads_ops.py snapshot <file>
    python -I ads-ops/ads_ops.py versions <file>
    python -I ads-ops/ads_ops.py restore <file> <version>   # snapshots the current file first

Nothing here touches an ad account. The ledger records what a person or an
agent did in the UI; rolling back is still done in the UI, with approval.
"""
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('ADS_OPS_ROOT') or os.path.abspath(os.path.join(HERE, '..'))   # project root
CADENCE = os.path.join(HERE, 'cadence.json')
LEDGER_JSONL = os.path.join(HERE, 'changes.jsonl')
LEDGER_MD = os.path.join(HERE, 'change-ledger.md')
VERSIONS = os.path.join(ROOT, '.versions')

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


def protected():
    try:
        return load_cadence().get('protected') or PROTECTED_DEFAULT
    except Exception:
        return PROTECTED_DEFAULT


def today():
    return dt.date.today()


def rel(path):
    p = os.path.abspath(path)
    try:
        r = os.path.relpath(p, ROOT)
    except ValueError:
        return None
    if r.startswith('..'):
        return None
    return r.replace('\\', '/')


# ---------------------------------------------------------------- cadence

def load_cadence():
    with open(CADENCE, encoding='utf-8') as f:
        return json.load(f)


def save_cadence(c):
    with open(CADENCE, 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=1)
        f.write('\n')


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


def cmd_due(args):
    quiet = '--quiet' in args
    try:
        c = load_cadence()
    except Exception as e:                                   # never break a session start
        print(f'[ads-ops] cadence.json unreadable: {e}')
        return 0
    od = overdue(c)
    open_changes = [e for e in read_ledger() if e['status'] in ('planned', 'done')]
    if not od and not open_changes:
        if not quiet:
            print('[ads-ops] nothing overdue, no unverified changes.')
        return 0
    if quiet:                                                # SessionStart: one short line, details on demand
        items = ', '.join(t['id'] + ('' if late is None else f' (+{late} d)') for t, late in od)
        print(f'[ads-ops] Due: {items}.' if od else '[ads-ops]', end=' ')
        if open_changes:
            print(f'Ledger: {len(open_changes)} changes waiting for verification.', end=' ')
        print('If this session is about ads (or it is the first session of the day), offer it to the owner in one sentence; '
              'details: python -I ads-ops/ads_ops.py due. Nothing live without their explicit yes.')
        return 0
    print('[ads-ops] Regular tasks of the ads agents that are due (ads-ops/README.md).')
    print('Offer them to the owner in one sentence at the start of the session, start nothing live without their yes:')
    for t, late in od:
        when = 'never run' if late is None else (f'{late} d overdue' if late > 0 else 'today')
        print(f"  - {t['id']} ({t['owner']}, every {t['every_days']} d, {when}): {t['what']}")
    if open_changes:
        print(f'  - change ledger: {len(open_changes)} changes not verified/evaluated yet '
              f'(ads_ops.py ledger list --open)')
    return 0


def cmd_done(args):
    if not args:
        print('usage: done <task-id> [--note "..."]')
        return 2
    tid = args[0]
    note = opt(args[1:], 'note', False)
    c = load_cadence()
    for t in c['tasks']:
        if t['id'] == tid:
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
    with open(LEDGER_JSONL, 'w', encoding='utf-8') as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    render_ledger(entries)


def cell(s):
    return str(s or '').replace('|', '/').replace('\n', ' ')


def render_ledger(entries):
    lines = [
        '# Ads change ledger',
        '',
        'Generated from `changes.jsonl` by `ads_ops.py` - do not edit by hand. Newest on top.',
        'Every live change to Google Ads / Meta / the attribution tool gets a row **before** it is made, with the value read from the UI.',
        'Status: `planned` (written, not yet done) > `done` (made) > `verified` (read back after reload) > `kept` / `rolled_back`.',
        '',
        '| ID | Date | Channel | Account | Object | Field | Before | After | Why | Approved | Rollback if | Status | Snapshot |',
        '|---|---|---|---|---|---|---|---|---|---|---|---|---|',
    ]
    for e in reversed(entries):
        lines.append('| ' + ' | '.join(cell(e.get(k)) for k in (
            'id', 'date', 'channel', 'account', 'object', 'field', 'before', 'after', 'why',
            'approved', 'rollback_if', 'status', 'snapshot')) + ' |')
    with open(LEDGER_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


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


def cmd_ledger(args):
    if not args:
        print(__doc__)
        return 2
    sub, rest = args[0], args[1:]
    entries = read_ledger()
    if sub == 'add':
        for f in ('before', 'after', 'approved', 'rollback-if'):
            if not opt(rest, f, False).strip():
                raise SystemExit(f'--{f} is required: no live change without the old value, the new value, '
                                 'an approval and a rollback trigger')
        n = sum(1 for e in entries if e['date'] == today().isoformat()) + 1
        e = {
            'id': f"{today().strftime('%Y%m%d')}-{n:02d}",
            'date': today().isoformat(),
            'channel': opt(rest, 'channel'), 'account': opt(rest, 'account'),
            'object': opt(rest, 'object'), 'field': opt(rest, 'field'),
            'before': opt(rest, 'before'), 'after': opt(rest, 'after'),
            'why': opt(rest, 'why', False), 'approved': opt(rest, 'approved'),
            'rollback_if': opt(rest, 'rollback-if'),
            'snapshot': opt(rest, 'snapshot', False),
            'status': 'planned', 'history': [[today().isoformat(), 'planned']],
        }
        entries.append(e)
        write_ledger(entries)
        print(f"ledger {e['id']} planned. After the change: ledger done {e['id']}; after reload read-back: ledger verify {e['id']}")
        return 0
    if sub == 'list':
        only_open = '--open' in rest
        for e in entries:
            if only_open and e['status'] not in ('planned', 'done', 'verified'):
                continue
            print(f"{e['id']} {e['status']:<11} {e['channel']}/{e['account']} {e['object']} {e['field']}: {e['before']} -> {e['after']}  (rollback if {e['rollback_if']})")
        return 0
    if sub in ('done', 'verify', 'keep', 'rolled-back'):
        if not rest:
            raise SystemExit(f'usage: ledger {sub} <id>')
        status = {'done': 'done', 'verify': 'verified', 'keep': 'kept', 'rolled-back': 'rolled_back'}[sub]
        for e in entries:
            if e['id'] == rest[0]:
                e['status'] = status
                e.setdefault('history', []).append([today().isoformat(), status] + rest[1:2])
                write_ledger(entries)
                print(f"{e['id']}: {status}")
                return 0
        raise SystemExit(f'no ledger entry {rest[0]}')
    if sub == 'rollback':
        if not rest:
            raise SystemExit('usage: ledger rollback <id>')
        for e in entries:
            if e['id'] == rest[0]:
                print(f"Rollback plan for {e['id']} ({e['channel']} / {e['account']}):")
                print(f"  1. Ask the owner for an explicit yes (rollback is a live change too).")
                print(f"  2. Open {e['object']} and read the current value of '{e['field']}' (expected: {e['after']}).")
                print(f"     If it is not {e['after']}, someone changed it since: stop and report, do not overwrite.")
                print(f"  3. Write a new ledger entry: --before \"{e['after']}\" --after \"{e['before']}\" --why \"rollback of {e['id']}\".")
                print(f"  4. Set '{e['field']}' back to: {e['before']}  (snapshot: {e.get('snapshot') or 'none'}).")
                print(f"  5. Reload, read it back, then: ledger verify <new id> and ledger rolled-back {e['id']}.")
                print("  Google Ads: Change history can undo some changes directly; Meta: Activity history shows the old value but has no undo.")
                return 0
        raise SystemExit(f'no ledger entry {rest[0]}')
    print(__doc__)
    return 2


# ---------------------------------------------------------------- versions

def version_dir(r):
    return os.path.join(VERSIONS, *r.split('/'))


def version_list(d, ext):
    """Version files of one protected file, oldest first (index.jsonl order)."""
    idx = os.path.join(d, 'index.jsonl')
    if not os.path.exists(idx):
        return []
    with open(idx, encoding='utf-8') as f:
        names = [json.loads(l)['version'] + ext for l in f if l.strip()]
    return [n for n in names if os.path.isfile(os.path.join(d, n))]


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def snapshot(path, reason='manual'):
    r = rel(path)
    if r is None or not os.path.isfile(path):
        return None
    d = version_dir(r)
    os.makedirs(d, exist_ok=True)
    existing = version_list(d, os.path.splitext(path)[1])
    if existing and sha(os.path.join(d, existing[-1])) == sha(path):
        return None                                          # identical to the latest version
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    ext = os.path.splitext(path)[1]
    dst, n = os.path.join(d, stamp + ext), 1
    while os.path.exists(dst):                               # two versions in the same second
        stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S') + f'-{n}'
        dst, n = os.path.join(d, stamp + ext), n + 1
    shutil.copy2(path, dst)
    with open(os.path.join(d, 'index.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps({'version': stamp, 'reason': reason}, ensure_ascii=False) + '\n')
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
    src = os.path.join(version_dir(r), ver + os.path.splitext(path)[1])
    if not os.path.isfile(src):
        raise SystemExit(f'no version {ver} for {r} (see: versions {r})')
    snapshot(path, reason=f'before restore of {ver}')
    shutil.copy2(src, path)
    print(f'{r} restored to {ver} (the previous content was versioned first)')
    return 0


def cmd_hook_snapshot(args):
    """PreToolUse hook for Edit|Write|NotebookEdit: version protected files. Never blocks."""
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

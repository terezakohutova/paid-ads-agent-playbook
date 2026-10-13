"""Tests for ads-ops/ads_ops.py: cadence, change ledger, file versions, hook.

Every test runs the real script as a subprocess against a throwaway copy of
ads-ops/, so the repo's own cadence.json and ledger are never touched.
Standard library only: python -m unittest discover -s tests
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TODAY = dt.date.today().isoformat()
WEEK = (dt.date.today() + dt.timedelta(days=7)).isoformat()


class AdsOpsCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='ads-ops-test-')
        self.ops = os.path.join(self.root, 'ads-ops')
        shutil.copytree(os.path.join(REPO, 'ads-ops'), self.ops,
                        ignore=shutil.ignore_patterns('__pycache__', 'dicts'))
        # start from an empty ledger regardless of the repo's state
        open(os.path.join(self.ops, 'changes.jsonl'), 'w').close()
        os.makedirs(os.path.join(self.root, '.claude', 'agents'))
        self.agent = os.path.join(self.root, '.claude', 'agents', 'google-ads.md')
        with open(self.agent, 'w', encoding='utf-8') as f:
            f.write('version one\n')

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_ops(self, *args, stdin=None, **extra_env):
        env = dict(os.environ, PYTHONIOENCODING='utf-8', **extra_env)
        env.pop('ADS_OPS_ROOT', None)
        return subprocess.run([sys.executable, '-I', os.path.join(self.ops, 'ads_ops.py'), *args],
                              input=stdin, capture_output=True, text=True, encoding='utf-8',
                              cwd=self.root, env=env)

    def assertClean(self, r, code=0):
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        self.assertNotIn('Traceback', r.stderr)

    def ledger(self):
        with open(os.path.join(self.ops, 'changes.jsonl'), encoding='utf-8') as f:
            return [json.loads(l) for l in f if l.strip()]

    LEDGER_OK = ['ledger', 'add', '--channel', 'meta', '--account', 'market-a',
                 '--object', 'MKA_acq_example_2610_ios', '--field', 'daily budget',
                 '--before', '300/day', '--after', '345/day', '--why', 'best cost per value event',
                 '--rollback-if', 'cost per event > 20 after 7 days', '--review-by', WEEK]


class TestCadence(AdsOpsCase):
    def test_fresh_cadence_lists_every_task_as_never_run(self):
        r = self.run_ops('due')
        self.assertClean(r)
        with open(os.path.join(self.ops, 'cadence.json'), encoding='utf-8') as f:
            ids = [t['id'] for t in json.load(f)['tasks']]
        for tid in ids:
            self.assertIn(tid, r.stdout)
        self.assertEqual(r.stdout.count('never run'), len(ids))

    def test_quiet_mode_is_one_line_for_the_session_start_hook(self):
        r = self.run_ops('due', '--quiet')
        self.assertClean(r)
        self.assertEqual(len(r.stdout.strip().splitlines()), 1)
        self.assertIn('Nothing live without their explicit yes', r.stdout)

    def test_done_marks_the_run_and_removes_it_from_due(self):
        r = self.run_ops('done', 'meta-weekly-check', '--note', 'all green')
        self.assertClean(r)
        with open(os.path.join(self.ops, 'cadence.json'), encoding='utf-8') as f:
            task = next(t for t in json.load(f)['tasks'] if t['id'] == 'meta-weekly-check')
        self.assertEqual(task['last_run'], TODAY)
        self.assertEqual(task['last_note'], 'all green')
        self.assertNotIn('meta-weekly-check', self.run_ops('due').stdout)

    def test_task_becomes_due_again_after_its_interval(self):
        path = os.path.join(self.ops, 'cadence.json')
        with open(path, encoding='utf-8') as f:
            c = json.load(f)
        for t in c['tasks']:
            t['last_run'] = TODAY
        c['tasks'][0]['last_run'] = (dt.date.today() - dt.timedelta(days=c['tasks'][0]['every_days'] + 2)).isoformat()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(c, f)
        r = self.run_ops('due')
        self.assertIn(c['tasks'][0]['id'], r.stdout)
        self.assertIn('2 d overdue', r.stdout)
        self.assertNotIn(c['tasks'][1]['id'], r.stdout)

    def test_nothing_due(self):
        path = os.path.join(self.ops, 'cadence.json')
        with open(path, encoding='utf-8') as f:
            c = json.load(f)
        for t in c['tasks']:
            t['last_run'] = TODAY
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(c, f)
        self.assertIn('nothing overdue', self.run_ops('due').stdout)
        self.assertEqual(self.run_ops('due', '--quiet').stdout, '')

    def test_unreadable_cadence_never_breaks_a_session_start(self):
        with open(os.path.join(self.ops, 'cadence.json'), 'w') as f:
            f.write('{not json')
        r = self.run_ops('due', '--quiet')
        self.assertClean(r)
        self.assertIn('unreadable', r.stdout)

    def test_bad_input_is_a_usage_error_not_a_traceback(self):
        self.assertClean(self.run_ops('done'), 2)
        self.assertClean(self.run_ops('done', 'no-such-task'), 2)
        r = self.run_ops('done', 'meta-weekly-check', '--note')
        self.assertEqual(r.returncode, 1)
        self.assertNotIn('Traceback', r.stderr)
        self.assertClean(self.run_ops('no-such-command'), 2)
        self.assertClean(self.run_ops('--help'), 0)


class TestLedger(AdsOpsCase):
    def test_add_writes_jsonl_and_rendered_markdown(self):
        r = self.run_ops(*self.LEDGER_OK)
        self.assertClean(r)
        (e,) = self.ledger()
        self.assertEqual(e['id'], dt.date.today().strftime('%Y%m%d') + '-01')
        self.assertEqual((e['before'], e['after'], e['status']), ('300/day', '345/day', 'planned'))
        with open(os.path.join(self.ops, 'change-ledger.md'), encoding='utf-8') as f:
            md = f.read()
        self.assertIn('| 300/day | 345/day |', md)
        self.run_ops(*self.LEDGER_OK)
        self.assertEqual(self.ledger()[1]['id'][-3:], '-02')

    def test_refuses_an_entry_without_old_value_new_value_approval_or_trigger(self):
        for flag in ('--before', '--after', '--rollback-if', '--review-by'):
            args = list(self.LEDGER_OK)
            i = args.index(flag)
            del args[i:i + 2]
            r = self.run_ops(*args)
            self.assertEqual(r.returncode, 1, flag)
            self.assertIn(flag, r.stderr)
        self.assertEqual(self.ledger(), [])

    def test_a_flag_is_never_taken_as_the_value_of_another_flag(self):
        # "--before --after 2": before the fix this stored "--after" as the old value
        r = self.run_ops('ledger', 'add', '--channel', 'meta', '--account', 'a', '--object', 'o',
                         '--field', 'f', '--before', '--after', '2', '--rollback-if', 'y', '--review-by', WEEK)
        self.assertEqual(r.returncode, 1)
        self.assertIn('--before needs a value', r.stderr)
        self.assertEqual(self.ledger(), [])

    def test_status_transitions_and_open_list(self):
        self.run_ops(*self.LEDGER_OK)
        eid = self.ledger()[0]['id']
        steps = (('approve', 'approved', ('--by', 'Owner Name')), ('done', 'done', ()),
                 ('verify', 'verified', ()), ('keep', 'kept', ()))
        for sub, status, extra in steps:
            self.assertClean(self.run_ops('ledger', sub, eid, *extra))
            self.assertEqual(self.ledger()[0]['status'], status)
            if status != 'kept':
                self.assertIn(eid, self.run_ops('ledger', 'list', '--open').stdout, status)
        e = self.ledger()[0]
        self.assertEqual([h[1] for h in e['history']], ['planned', 'approved', 'done', 'verified', 'kept'])
        self.assertEqual(e['approved_by'], 'Owner Name')
        self.assertTrue(e['approved_at'].startswith(TODAY), e['approved_at'])
        self.assertEqual(self.run_ops('ledger', 'list', '--open').stdout, '')
        self.assertIn(eid, self.run_ops('ledger', 'list').stdout)

    def test_open_changes_show_up_in_due(self):
        self.run_ops(*self.LEDGER_OK)
        self.assertIn("1 waiting for the owner's approval", self.run_ops('due', '--quiet').stdout)
        eid = self.ledger()[0]['id']
        self.run_ops('ledger', 'approve', eid, '--by', 'Owner')
        self.assertIn('1 approved, not made yet', self.run_ops('due', '--quiet').stdout)
        self.run_ops('ledger', 'done', eid)
        self.assertIn('1 made, waiting for read-back', self.run_ops('due', '--quiet').stdout)


class TestLedgerEnforcement(AdsOpsCase):
    """What the script enforces about approvals and the order of statuses."""

    def add(self):
        self.assertClean(self.run_ops(*self.LEDGER_OK))
        return self.ledger()[-1]['id']

    def test_approval_cannot_be_written_by_the_agent_on_add(self):
        r = self.run_ops(*(self.LEDGER_OK + ['--approved', 'owner said yes']))
        self.assertEqual(r.returncode, 1)
        self.assertIn('ledger approve', r.stderr)
        self.assertEqual(self.ledger(), [])

    def test_done_is_refused_before_approval(self):
        eid = self.add()
        r = self.run_ops('ledger', 'done', eid)
        self.assertEqual(r.returncode, 1)
        self.assertIn('approval', r.stderr)
        self.assertEqual(self.ledger()[0]['status'], 'planned')

    def test_verify_without_done_is_refused(self):
        eid = self.add()
        self.run_ops('ledger', 'approve', eid, '--by', 'Owner')
        r = self.run_ops('ledger', 'verify', eid)
        self.assertEqual(r.returncode, 1)
        self.assertIn('done first', r.stderr)
        self.assertEqual(self.ledger()[0]['status'], 'approved')

    def test_keep_or_rollback_needs_a_verified_row(self):
        eid = self.add()
        for sub in ('keep', 'rolled-back'):
            self.assertEqual(self.run_ops('ledger', sub, eid).returncode, 1, sub)
        self.assertEqual(self.ledger()[0]['status'], 'planned')

    def test_approve_needs_a_name_and_happens_once(self):
        eid = self.add()
        self.assertEqual(self.run_ops('ledger', 'approve', eid).returncode, 1)
        self.assertEqual(self.run_ops('ledger', 'approve', eid, '--by').returncode, 1)
        self.assertClean(self.run_ops('ledger', 'approve', eid, '--by', 'A'))
        r = self.run_ops('ledger', 'approve', eid, '--by', 'B')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.ledger()[0]['approved_by'], 'A')

    def test_cancel_closes_a_planned_row(self):
        eid = self.add()
        self.assertClean(self.run_ops('ledger', 'cancel', eid))
        self.assertEqual(self.ledger()[0]['status'], 'cancelled')
        self.assertEqual(self.run_ops('ledger', 'list', '--open').stdout, '')

    def test_review_by_must_be_a_future_date(self):
        for bad in ('next week', '2020-01-01'):
            args = list(self.LEDGER_OK)
            args[args.index('--review-by') + 1] = bad
            r = self.run_ops(*args)
            self.assertEqual(r.returncode, 1, bad)
            self.assertNotIn('Traceback', r.stderr)
        self.assertEqual(self.ledger(), [])

    def set_review_by(self, date):
        rows = self.ledger()
        rows[0]['review_by'] = date
        with open(os.path.join(self.ops, 'changes.jsonl'), 'w', encoding='utf-8') as f:
            f.write(''.join(json.dumps(e) + '\n' for e in rows))

    def walk_to_verified(self):
        eid = self.add()
        self.run_ops('ledger', 'approve', eid, '--by', 'Owner')
        self.run_ops('ledger', 'done', eid)
        self.run_ops('ledger', 'verify', eid)
        return eid

    def test_verified_row_past_its_review_date_is_surfaced_in_due(self):
        eid = self.walk_to_verified()
        self.assertNotIn('review date', self.run_ops('due', '--quiet').stdout)   # not reached yet
        self.set_review_by((dt.date.today() - dt.timedelta(days=1)).isoformat())
        q = self.run_ops('due', '--quiet').stdout
        self.assertIn('1 past their review date', q)
        full = self.run_ops('due').stdout
        self.assertIn(eid, full)
        self.assertIn('keep', full)
        self.assertIn('REVIEW DUE', self.run_ops('ledger', 'list', '--open').stdout)
        self.run_ops('ledger', 'keep', eid)
        self.assertNotIn('review date', self.run_ops('due', '--quiet').stdout)


class TestRobustness(AdsOpsCase):
    def test_concurrent_adds_get_unique_ids_and_lose_nothing(self):
        script = os.path.join(self.ops, 'ads_ops.py')
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        env.pop('ADS_OPS_ROOT', None)
        procs = [subprocess.Popen([sys.executable, '-I', script, *self.LEDGER_OK], cwd=self.root, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(8)]
        for p in procs:
            p.communicate(timeout=60)
            self.assertEqual(p.returncode, 0)
        ids = [e['id'] for e in self.ledger()]
        self.assertEqual(len(ids), 8)
        self.assertEqual(len(set(ids)), 8, ids)
        left = [f for f in os.listdir(self.ops) if f.endswith('.tmp') or f.endswith('.lock')]
        self.assertEqual(left, [])                                     # no temp or lock files left behind

    def test_a_stale_lock_from_a_crash_does_not_block_forever(self):
        lock = os.path.join(self.ops, '.ads_ops.lock')
        with open(lock, 'w') as f:
            f.write('12345 crashed')
        old = dt.datetime.now().timestamp() - 3600
        os.utime(lock, (old, old))
        self.assertClean(self.run_ops(*self.LEDGER_OK))
        self.assertEqual(len(self.ledger()), 1)

    def test_restore_outside_the_project_is_a_clean_error(self):
        outside = tempfile.mkdtemp(prefix='ads-ops-outside-')
        try:
            path = os.path.join(outside, 'x.md')
            with open(path, 'w') as f:
                f.write('x')
            r = self.run_ops('restore', path, '20260101-000000')
            self.assertEqual(r.returncode, 1)
            self.assertNotIn('Traceback', r.stderr)
            self.assertIn('outside the project root', r.stderr)
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_done_versions_cadence_json_before_rewriting_it(self):
        self.assertClean(self.run_ops('done', 'meta-weekly-check'))
        d = os.path.join(self.root, '.versions', 'ads-ops', 'cadence.json')
        versions = [x for x in os.listdir(d) if x != 'index.jsonl']
        self.assertEqual(len(versions), 1)
        with open(os.path.join(d, versions[0]), encoding='utf-8') as f:
            old = json.load(f)
        self.assertIsNone(next(t for t in old['tasks'] if t['id'] == 'meta-weekly-check')['last_run'])

    def test_versions_keep_only_the_last_n(self):
        for i in range(6):
            with open(self.agent, 'w', encoding='utf-8') as f:
                f.write(f'v{i}\n')
            self.assertClean(self.run_ops('snapshot', self.agent, ADS_OPS_VERSIONS_KEEP='3'))
        d = os.path.join(self.root, '.versions', '.claude', 'agents', 'google-ads.md')
        files = sorted(x for x in os.listdir(d) if x != 'index.jsonl')
        self.assertEqual(len(files), 3)
        with open(os.path.join(d, 'index.jsonl'), encoding='utf-8') as f:
            self.assertEqual(len([l for l in f if l.strip()]), 3)
        contents = []
        for name in self.run_ops('versions', self.agent).stdout.split('\n'):
            if name.strip():
                with open(os.path.join(d, name.split()[0] + '.md'), encoding='utf-8') as f:
                    contents.append(f.read())
        self.assertEqual(contents, ['v3\n', 'v4\n', 'v5\n'])           # the newest three, oldest first

    def test_rollback_prints_the_way_back_to_the_old_value(self):
        self.run_ops(*self.LEDGER_OK)
        eid = self.ledger()[0]['id']
        r = self.run_ops('ledger', 'rollback', eid)
        self.assertClean(r)
        self.assertIn('back to: 300/day', r.stdout)
        self.assertIn('--before "345/day" --after "300/day"', r.stdout)
        self.assertIn('explicit yes', r.stdout)
        self.assertIn('--review-by', r.stdout)
        self.assertEqual(self.ledger()[0]['status'], 'planned')   # printing a plan changes nothing

    def test_rollback_and_status_errors_are_clean(self):
        for args in (('ledger', 'rollback'), ('ledger', 'rollback', 'nope'),
                     ('ledger', 'verify'), ('ledger', 'verify', 'nope')):
            r = self.run_ops(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertNotIn('Traceback', r.stderr, args)

    def test_pipe_in_a_value_cannot_break_the_markdown_table(self):
        args = list(self.LEDGER_OK)
        args[args.index('--why') + 1] = 'a | b\nc'
        self.run_ops(*args)
        with open(os.path.join(self.ops, 'change-ledger.md'), encoding='utf-8') as f:
            row = f.read().strip().splitlines()[-1]
        self.assertEqual(row.count('|'), 15)


class TestVersions(AdsOpsCase):
    def hook(self, path, tool='Edit'):
        return self.run_ops('hook-snapshot', stdin=json.dumps({'tool_name': tool, 'tool_input': {'file_path': path}}))

    def versions_of(self, rel):
        d = os.path.join(self.root, '.versions', *rel.split('/'))
        return sorted(x for x in os.listdir(d) if x != 'index.jsonl') if os.path.isdir(d) else []

    def test_hook_versions_a_protected_file_once_per_content(self):
        self.assertClean(self.hook(self.agent))
        self.assertEqual(len(self.versions_of('.claude/agents/google-ads.md')), 1)
        self.assertClean(self.hook(self.agent))                      # unchanged: no new version
        self.assertEqual(len(self.versions_of('.claude/agents/google-ads.md')), 1)

    def test_hook_ignores_unprotected_and_outside_files(self):
        other = os.path.join(self.root, 'notes.md')
        with open(other, 'w') as f:
            f.write('x')
        self.assertClean(self.hook(other))
        self.assertClean(self.hook(os.path.join(tempfile.gettempdir(), 'elsewhere.md')))
        self.assertFalse(os.path.exists(os.path.join(self.root, '.versions')))

    def test_hook_never_blocks_on_garbage_input(self):
        for stdin in ('', 'not json', '{"tool_input": null}', json.dumps({'tool_input': {'file_path': 42}})):
            self.assertClean(self.run_ops('hook-snapshot', stdin=stdin))

    def test_restore_brings_back_an_old_version_and_keeps_the_current_one(self):
        self.run_ops('snapshot', self.agent)
        (v1,) = self.versions_of('.claude/agents/google-ads.md')
        with open(self.agent, 'w', encoding='utf-8') as f:
            f.write('version two\n')
        r = self.run_ops('restore', self.agent, os.path.splitext(v1)[0])
        self.assertClean(r)
        with open(self.agent, encoding='utf-8') as f:
            self.assertEqual(f.read(), 'version one\n')
        contents = []
        for v in self.versions_of('.claude/agents/google-ads.md'):
            with open(os.path.join(self.root, '.versions', '.claude', 'agents', 'google-ads.md', v), encoding='utf-8') as f:
                contents.append(f.read())
        self.assertIn('version two\n', contents)                      # versioned before the restore

    def test_versions_within_the_same_second_never_overwrite_each_other(self):
        for text in ('a\n', 'b\n', 'c\n', 'a\n'):
            with open(self.agent, 'w', encoding='utf-8') as f:
                f.write(text)
            self.run_ops('snapshot', self.agent)
        self.run_ops('snapshot', self.agent)                          # same as latest: skipped
        listed = self.run_ops('versions', self.agent).stdout.split('\n')
        names = [l.split()[0] for l in listed if l.strip()]
        self.assertEqual(len(names), 4)
        d = os.path.join(self.root, '.versions', '.claude', 'agents', 'google-ads.md')
        got = []
        for n in names:
            with open(os.path.join(d, n + '.md'), encoding='utf-8') as f:
                got.append(f.read())
        self.assertEqual(got, ['a\n', 'b\n', 'c\n', 'a\n'])          # listed oldest first

    def test_restore_of_unknown_version_is_refused(self):
        r = self.run_ops('restore', self.agent, '19990101-000000')
        self.assertEqual(r.returncode, 1)
        self.assertIn('no version', r.stderr)


class TestShippedFiles(unittest.TestCase):
    def test_cadence_json_is_valid(self):
        with open(os.path.join(REPO, 'ads-ops', 'cadence.json'), encoding='utf-8') as f:
            c = json.load(f)
        ids = [t['id'] for t in c['tasks']]
        self.assertEqual(len(ids), len(set(ids)), 'duplicate task ids')
        for t in c['tasks']:
            self.assertGreater(t['every_days'], 0, t['id'])
            self.assertTrue(t['what'].strip(), t['id'])
            self.assertIsNone(t['last_run'], 'a template ships with no run history: ' + t['id'])

    def test_template_ledger_is_empty(self):
        with open(os.path.join(REPO, 'ads-ops', 'changes.jsonl'), encoding='utf-8') as f:
            self.assertEqual(f.read().strip(), '')

    def test_hook_example_calls_real_subcommands(self):
        with open(os.path.join(REPO, 'ads-ops', 'settings.hooks.example.json'), encoding='utf-8') as f:
            hooks = json.load(f)['hooks']
        cmds = [h['command'] for ev in hooks.values() for m in ev for h in m['hooks']]
        self.assertTrue(any(c.endswith('hook-snapshot') for c in cmds))
        self.assertTrue(any(c.endswith('due --quiet') for c in cmds))


if __name__ == '__main__':
    unittest.main()

"""Repo integrity: links resolve, agent files are loadable, the sample client is
internally consistent with its own audit. Standard library only."""
import csv
import glob
import importlib.util
import json
import os
import re
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SAMPLE = os.path.join(REPO, 'sample-client', 'tallo')


def markdown_files():
    out = []
    for dirpath, dirnames, files in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d not in ('.git', '.versions', '__pycache__')]
        out += [os.path.join(dirpath, f) for f in files if f.endswith('.md')]
    return out


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def frontmatter(path):
    m = re.match(r'---\r?\n(.*?)\r?\n---\r?\n', read(path), re.S)
    return dict(re.findall(r'^(\w+):\s*(.+)$', m.group(1), re.M)) if m else {}


class TestLinks(unittest.TestCase):
    def test_every_relative_markdown_link_resolves(self):
        broken = []
        for md in markdown_files():
            for target in re.findall(r'\]\(([^)\s]+)\)', read(md)):
                target = target.split('#')[0]
                if not target or re.match(r'[a-z]+:', target):
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(md), target))):
                    broken.append(f'{os.path.relpath(md, REPO)} -> {target}')
        self.assertEqual(broken, [])


class TestAgentsAndSkills(unittest.TestCase):
    def test_agents_have_the_frontmatter_claude_code_needs(self):
        agents = glob.glob(os.path.join(REPO, '.claude', 'agents', '*.md'))
        self.assertEqual(len(agents), 2)
        for a in agents:
            fm = frontmatter(a)
            self.assertEqual(fm.get('name'), os.path.splitext(os.path.basename(a))[0], a)
            self.assertGreater(len(fm.get('description', '')), 50, a)
            self.assertIn('tools', fm, a)

    def test_skill_has_name_and_description(self):
        for s in glob.glob(os.path.join(REPO, '.claude', 'skills', '*', 'SKILL.md')):
            fm = frontmatter(s)
            self.assertEqual(fm.get('name'), os.path.basename(os.path.dirname(s)))
            self.assertTrue(fm.get('description'))

    def test_shared_blocks_are_identical_in_both_agents(self):
        """Step 0b and guardrails 1-16 exist once in content, twice on disk: keep the copies equal."""
        g = read(os.path.join(REPO, '.claude', 'agents', 'google-ads.md'))
        f = read(os.path.join(REPO, '.claude', 'agents', 'facebook-ads.md'))
        for name in ('step0b', 'guardrails'):
            self.assertEqual(shared_block(g, name), shared_block(f, name), name)

    def test_guardrails_are_numbered_the_same_everywhere(self):
        g = read(os.path.join(REPO, '.claude', 'agents', 'google-ads.md'))
        f = read(os.path.join(REPO, '.claude', 'agents', 'facebook-ads.md'))
        shared = [int(n) for n in re.findall(r'^(\d+)\. ', shared_block(g, 'guardrails'), re.M)]
        self.assertEqual(shared, list(range(1, 17)))
        meta_only = f.split('<!-- /shared:guardrails -->')[1].split('\n## ')[0]
        self.assertEqual([int(n) for n in re.findall(r'^(\d+)\. ', meta_only, re.M)], [17, 18, 19])
        book = read(os.path.join(REPO, 'paid-ads-agent-playbook.md'))
        shared_book = book.split('**Non-negotiable guardrails (both platforms)**')[1].split('- **Budget rules')[0]
        self.assertEqual([int(n) for n in re.findall(r'^  (\d+)\. ', shared_book, re.M)], list(range(1, 17)))
        meta_book = book.split('### Non-negotiable guardrails')[1].split('\n### ')[0]
        self.assertEqual([int(n) for n in re.findall(r'^(\d+)\. ', meta_book, re.M)], [17, 18, 19])
        for text in (g, f):                                   # every "guardrail N" reference exists
            for n in re.findall(r'guardrails? (\d+)', text):
                self.assertLessEqual(int(n), 19 if text is f else 16, n)

    def test_every_playbook_audit_item_is_in_the_agent(self):
        """The playbook's Phase 0 checklists are canonical; each bold label must appear in
        the matching agent's Phase 0 section, so the two cannot drift apart again."""
        book = read(os.path.join(REPO, 'paid-ads-agent-playbook.md'))
        google_book = book.split('## Google Ads subagent')[1].split('## Meta (Facebook/Instagram) Ads subagent')[0]
        meta_book = book.split('## Meta (Facebook/Instagram) Ads subagent')[1]
        for agent, part in (('google-ads', google_book), ('facebook-ads', meta_book)):
            checklist = part.split('### Phase 0')[1].split('\n### ')[0]
            labels = re.findall(r'^- \[ \] \*\*([^*]+)\*\*', checklist, re.M)
            self.assertGreater(len(labels), 10, agent)
            a = read(os.path.join(REPO, '.claude', 'agents', agent + '.md'))
            phase0 = a.split('## Phase 0')[1].split('\n## ')[0]
            missing = [l for l in labels if f'**{l}**' not in phase0]
            self.assertEqual(missing, [], agent)

    def test_pass_means_confirmed(self):
        for agent in ('google-ads', 'facebook-ads'):
            a = read(os.path.join(REPO, '.claude', 'agents', agent + '.md'))
            self.assertNotIn('assumed or confirmed', a)
            self.assertIn('is blocked, not pass', a)


def shared_block(text, name):
    m = re.search(r'<!-- shared:%s[^>]*-->(.*?)<!-- /shared:%s -->' % (name, name), text, re.S)
    assert m, name
    return m.group(1)


class TestSampleClient(unittest.TestCase):
    def rows(self, platform, name):
        with open(os.path.join(SAMPLE, platform, 'data', name), encoding='utf-8', newline='') as f:
            return list(csv.DictReader(f))

    def test_csvs_are_rectangular(self):
        for p in glob.glob(os.path.join(SAMPLE, '*', 'data', '*.csv')):
            with open(p, encoding='utf-8', newline='') as f:
                widths = {len(r) for r in csv.reader(f)}
            self.assertEqual(len(widths), 1, p)

    def test_no_notes_column_gives_the_answer_away(self):
        for p in glob.glob(os.path.join(SAMPLE, '*', 'data', '*.csv')):
            with open(p, encoding='utf-8', newline='') as f:
                header = next(csv.reader(f))
            self.assertFalse({'notes', 'note', 'comment', 'issue'} & {h.lower() for h in header}, p)

    def test_key_facts_are_in_the_data(self):
        conv = self.rows('google', 'conversion-actions.csv')
        fd = {r['account']: r['goal_role'] for r in conv if r['conversion_action'].startswith('First Deposit')}
        self.assertEqual(fd, {'CZ': 'Secondary', 'SK': 'Secondary'})                       # G1, G2
        pl_installs = [r for r in conv if r['account'] == 'PL' and r['category'] == 'Download'
                       and r['goal_role'] == 'Primary']
        self.assertEqual(len(pl_installs), 2)                                              # G3
        (pl,) = [r for r in self.rows('google', 'attribution-check.csv') if r['market'] == 'PL']
        self.assertGreaterEqual(int(pl['google_ads_installs']) / int(pl['mmp_installs_attributed_to_google_ads']), 10)
        ledger_objects = {r['object'] for r in self.rows('google', 'change-ledger.csv')}
        budget = [r for r in self.rows('google', 'change-history.csv') if 'Budget' in r['change']]
        self.assertEqual(sorted(r['campaign'] for r in budget if r['campaign'] not in ledger_objects),
                         ['PL_APP_acq_promo_2509', 'SK_APP_acq_promo_2508'])               # G9
        events = {r['event']: r for r in self.rows('meta', 'events.csv')}
        self.assertTrue(events['first_deposit']['mapped_to_standard_event'].startswith('Not mapped'))  # M5
        admins = [r for r in self.rows('meta', 'people.csv')
                  if r['portfolio'] == 'Tallo CZ' and r['role'].startswith('Full control')]
        self.assertEqual(len(admins), 1)                                                   # M1
        under = sorted(r['campaign'] for r in self.rows('google', 'campaigns.csv')
                       if r['status'] == 'Enabled' and r['bid_strategy'] == 'Target CPI'
                       and float(r['budget_eur_day']) < 50 * float(r['target_eur']))
        self.assertEqual(under, ['CZ_APP_acq_install_2505', 'PL_APP_acq_dowod_spoleczny_2509',
                                 'PL_APP_acq_promo_2509', 'SK_APP_acq_promo_2508'])        # G17 (review)
        cz_ads = [r['text'] for r in self.rows('google', 'ads.csv') if r['account'] == 'CZ']
        self.assertTrue(any('€' in t for t in cz_ads))                                     # G18 (review)

    def test_answer_key_ids_are_unique_and_cover_checklist_labels(self):
        key = json.loads(read(os.path.join(SAMPLE, 'answer-key.json')))
        book = read(os.path.join(REPO, 'paid-ads-agent-playbook.md'))
        for platform in ('google', 'meta'):
            ids = [x['id'] for x in key[platform]]
            self.assertEqual(len(ids), len(set(ids)))
            for x in key[platform]:
                self.assertIn(f"**{x['checklist']}**", book, x['id'])
        md = read(os.path.join(SAMPLE, 'answer-key.md'))
        for x in key['google'] + key['meta']:
            self.assertIn(f"| {x['id']} |", md)


def load_score():
    spec = importlib.util.spec_from_file_location('score', os.path.join(SAMPLE, 'score.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBlindRuns(unittest.TestCase):
    RUNS = os.path.join(SAMPLE, 'blind-runs')

    def runs(self):
        return sorted(d for d in os.listdir(self.RUNS)
                      if os.path.isfile(os.path.join(self.RUNS, d, 'run.json')))

    def test_agent_files_as_run_match_the_recorded_hashes(self):
        """The agent files changed after the runs; the exact versions read are kept."""
        import hashlib
        for run in self.runs():
            meta = json.loads(read(os.path.join(self.RUNS, run, 'run.json')))
            name = meta['inputs']['agent_file']['name'].replace('.md', '-as-run.md.txt')
            with open(os.path.join(self.RUNS, 'agent-files', name), 'rb') as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(),
                                 meta['inputs']['agent_file']['sha256'], run)

    def test_at_least_two_google_runs_and_one_meta_run(self):
        runs = self.runs()
        self.assertGreaterEqual(len([r for r in runs if r.startswith('google')]), 2)
        self.assertGreaterEqual(len([r for r in runs if r.startswith('meta')]), 1)

    def test_every_run_has_output_metadata_and_scoring(self):
        import hashlib
        for run in self.runs():
            d = os.path.join(self.RUNS, run)
            meta = json.loads(read(os.path.join(d, 'run.json')))
            for k in ('date', 'model', 'prompt', 'inputs', 'output'):
                self.assertIn(k, meta, run)
            with open(os.path.join(d, 'output.md'), 'rb') as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), meta['output']['sha256'],
                                 f'{run}: output.md changed since the run')
            platform = 'meta' if run.startswith('meta') else 'google'
            for name, digest in meta['inputs']['data_files'].items():
                with open(os.path.join(SAMPLE, platform, 'data', name), 'rb') as f:
                    self.assertEqual(hashlib.sha256(f.read()).hexdigest(), digest, f'{run}: {name} changed')
            self.assertNotIn('invest', meta['prompt'].lower(), 'the prompt must not hint the vertical')

    def test_scoring_quotes_are_verbatim(self):
        for run in self.runs():
            d = os.path.join(self.RUNS, run)
            out = read(os.path.join(d, 'output.md'))
            s = json.loads(read(os.path.join(d, 'scoring.json')))
            for f in s['findings'] + s.get('not_counted', []):
                self.assertIn(f['excerpt'], out, f'{run}: {f["excerpt"][:60]}')

    def test_readme_reports_what_the_script_computes(self):
        readme = read(os.path.join(SAMPLE, 'README.md'))
        for run, r in load_score().score_all().items():
            row = (f"| {run} | {r['found']}/{r['planted']} | {r['matched'] + r['extra_valid']}/{r['fail_findings']} "
                   f"| {r['matched']}/{r['fail_findings']} | {r['false_positives']} |")
            self.assertIn(row, readme, run)


class TestScoreArithmetic(unittest.TestCase):
    def test_recall_and_precision(self):
        score = load_score().score
        r = score(['A', 'B', 'C', 'D'], ['A', 'A', 'B', 'extra-valid', 'false-positive'])
        self.assertEqual((r['found'], r['missed']), (2, ['C', 'D']))
        self.assertAlmostEqual(r['recall'], 0.5)
        self.assertAlmostEqual(r['precision'], 4 / 5)          # A, A, B, extra-valid
        self.assertAlmostEqual(r['strict_precision'], 3 / 5)
        self.assertEqual(r['false_positives'], 1)

    def test_unknown_label_is_an_error(self):
        with self.assertRaises(ValueError):
            load_score().score(['A'], ['B'])

    def test_empty_run(self):
        r = load_score().score(['A'], [])
        self.assertEqual((r['recall'], r['precision']), (0.0, 0.0))


class TestJson(unittest.TestCase):
    def test_all_json_parses(self):
        for p in glob.glob(os.path.join(REPO, '**', '*.json'), recursive=True):
            json.loads(read(p))


if __name__ == '__main__':
    unittest.main()

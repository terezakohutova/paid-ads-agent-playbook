"""Repo integrity: links resolve, agent files are loadable, the sample client is
internally consistent with its own audit. Standard library only."""
import csv
import glob
import json
import os
import re
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SAMPLE = os.path.join(REPO, 'sample-client', 'vela-invest')


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

    def test_agents_name_the_same_number_of_guardrails_as_the_playbook_promises(self):
        g = read(os.path.join(REPO, '.claude', 'agents', 'google-ads.md'))
        numbered = re.findall(r'^(\d+)\. ', g.split('## Non-negotiable guardrails')[1].split('\n## ')[0], re.M)
        self.assertEqual([int(n) for n in numbered], list(range(1, len(numbered) + 1)))


class TestSampleClient(unittest.TestCase):
    def rows(self, name):
        with open(os.path.join(SAMPLE, 'data', name), encoding='utf-8', newline='') as f:
            return list(csv.DictReader(f))

    def test_every_campaign_in_the_data_appears_in_snapshot_and_audit(self):
        snapshot = read(os.path.join(SAMPLE, 'account-snapshot.md'))
        audit = read(os.path.join(SAMPLE, 'audit-output.md'))
        campaigns = [r['campaign'] for r in self.rows('campaigns.csv')]
        self.assertEqual(len(campaigns), 6)
        for c in campaigns:
            self.assertIn(c, snapshot)
        self.assertIn(f'attached to one\nof six campaigns', audit)

    def test_audit_numbers_match_the_data(self):
        audit = read(os.path.join(SAMPLE, 'audit-output.md'))
        (att,) = self.rows('attribution-check.csv')
        self.assertIn(f"reports {att['platform_installs']} PL installs", audit)
        self.assertIn(f"against {att['attribution_tool_installs']} from", audit)
        (chg,) = self.rows('change-history.csv')
        self.assertEqual(chg['approver'], '')
        self.assertIn('EUR 40/day to EUR 90/day', audit)

    def test_audit_names_the_only_primary_action_correctly(self):
        primary = [r['action'] for r in self.rows('conversion-actions.csv') if r['status'] == 'Primary']
        self.assertEqual(primary, ['App Install'])
        audit = read(os.path.join(SAMPLE, 'audit-output.md'))
        self.assertIn('`App Install` is the only Primary action', audit)

    def test_every_audit_fail_cites_a_rule(self):
        audit = read(os.path.join(SAMPLE, 'audit-output.md')).split('## What this account needs')[0]
        for block in audit.split('\n\n'):
            if '\nFAIL' in block or block.startswith('FAIL'):
                self.assertRegex(block, r'(?i)guardrail|rule|checklist|playbook', block[:80])


class TestJson(unittest.TestCase):
    def test_all_json_parses(self):
        for p in glob.glob(os.path.join(REPO, '**', '*.json'), recursive=True):
            json.loads(read(p))


if __name__ == '__main__':
    unittest.main()

"""Tests for ads-ops/langcheck_ads.py, the language gate before ad copy is uploaded.

No dictionaries, no network: LanguageTool is replaced by a tiny local HTTP
server that answers like the real /v2/check endpoint, so the gate logic
(exit codes, fail-closed behaviour, ignore list, text collection) is tested
exactly as it runs. Standard library only.
"""
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SCRIPT = os.path.join(REPO, 'ads-ops', 'langcheck_ads.py')


class FakeLanguageTool(http.server.BaseHTTPRequestHandler):
    """Flags the word 'Tset' wherever it appears, like a spelling rule would."""
    seen = []

    def do_POST(self):
        body = urllib.parse.parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode())
        text, lang = body['text'][0], body['language'][0]
        FakeLanguageTool.seen.append((lang, text, body.get('level', [''])[0]))
        matches = []
        i = text.find('Tset')
        if i >= 0:
            matches.append({'offset': i, 'length': 4, 'message': 'Possible typo',
                            'replacements': [{'value': 'Test'}], 'rule': {'id': 'GERMAN_SPELLER_RULE'}})
        i = text.find('Google')
        if i >= 0:   # an ignored platform term must not count as a finding
            matches.append({'offset': i, 'length': 6, 'message': 'x', 'replacements': [],
                            'rule': {'id': 'SPELLER'}})
        out = json.dumps({'matches': matches}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def run(*args, lt_url='http://127.0.0.1:9/v2/check'):
    env = dict(os.environ, PYTHONIOENCODING='utf-8', LT_URL=lt_url,
               LANGTOOLS_DICTS=os.path.join(tempfile.gettempdir(), 'no-dicts-here'))
    return subprocess.run([sys.executable, '-I', SCRIPT, *args], capture_output=True,
                          text=True, encoding='utf-8', env=env)


class TestFailsClosed(unittest.TestCase):
    def test_no_tool_available_is_exit_3_never_clean(self):
        r = run('--lang', 'de', 'Das ist ein Tset')
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn('NOT CHECKED', r.stdout)
        self.assertNotIn('clean', r.stdout)

    def test_allow_unchecked_is_an_explicit_dry_run(self):
        r = run('--allow-unchecked', '--lang', 'de', 'Das ist ein Tset')
        self.assertEqual(r.returncode, 0)
        self.assertIn('NOT CHECKED', r.stdout)

    def test_czech_with_korektor_off_and_no_dictionary_is_unchecked(self):
        self.assertEqual(run('--no-online', '--lang', 'cz', 'Ahoj svete').returncode, 3)

    def test_usage_errors(self):
        self.assertEqual(run().returncode, 2)
        self.assertEqual(run('--lang').returncode, 2)
        self.assertEqual(run('--lang', 'de').returncode, 2)          # no texts
        self.assertEqual(run('--help').returncode, 0)


class TestWithLanguageTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(('127.0.0.1', 0), FakeLanguageTool)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/v2/check'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeLanguageTool.seen.clear()

    def test_finding_blocks_the_upload(self):
        r = run('--lang', 'de', 'Das ist ein Tset', lt_url=self.url)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn('"Tset" -> Test', r.stdout)
        self.assertEqual(FakeLanguageTool.seen[0][0], 'de-DE')
        self.assertEqual(FakeLanguageTool.seen[0][2], 'picky')

    def test_clean_copy_passes_and_names_the_tool_that_ran(self):
        r = run('--lang', 'pl', 'Zainstaluj aplikacje', lt_url=self.url)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('checked in pl with languagetool: clean', r.stdout)

    def test_ignored_platform_terms_are_not_findings(self):
        r = run('--lang', 'de', 'Jetzt bei Google Play', lt_url=self.url)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_spec_file_texts_are_collected_from_known_keys_only(self):
        spec = {'market': 'AT', 'name': 'Tset internal name, not ad copy',
                'formats': [{'headline': 'Ein Tset', 'cta': 'Los'}, {'primary_text': 'Alles gut'}],
                'descriptions': ['Eins', 'Eins']}
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(spec, f)
        try:
            r = run(f.name, lt_url=self.url)
        finally:
            os.unlink(f.name)
        self.assertEqual(r.returncode, 1, r.stdout)
        texts = sorted(t for _, t, _ in FakeLanguageTool.seen)
        self.assertEqual(texts, ['Alles gut', 'Ein Tset', 'Eins', 'Los'])   # deduplicated, 'name' skipped
        self.assertEqual(FakeLanguageTool.seen[0][0], 'de-DE')               # market AT -> German


if __name__ == '__main__':
    unittest.main()

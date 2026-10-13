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


class FlakyLanguageTool(FakeLanguageTool):
    """Answers the first request like FakeLanguageTool, then fails with HTTP 500,
    the way a LanguageTool server that runs out of memory mid-batch does."""
    calls = 0

    def do_POST(self):
        FlakyLanguageTool.calls += 1
        if FlakyLanguageTool.calls == 1:
            return FakeLanguageTool.do_POST(self)
        self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(500)
        self.end_headers()


class FakeKorektor(http.server.BaseHTTPRequestHandler):
    """Stand-in for the LINDAT Korektor API: echoes the text back (no fixes);
    after the first call it fails if `fail_after_first` is set."""
    calls = 0
    fail_after_first = False

    def do_GET(self):
        FakeKorektor.calls += 1
        if FakeKorektor.fail_after_first and FakeKorektor.calls > 1:
            self.send_response(503)
            self.end_headers()
            return
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        out = json.dumps({'result': q['data'][0]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def serve(handler):
    server = http.server.HTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{server.server_port}'


def spec_file(obj):
    f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(obj, f)
    f.close()
    return f.name


def run(*args, lt_url='http://127.0.0.1:9/v2/check', korektor_url='http://127.0.0.1:9/korektor'):
    env = dict(os.environ, PYTHONIOENCODING='utf-8', LT_URL=lt_url, KOREKTOR_URL=korektor_url,
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


class TestPartialCoverage(unittest.TestCase):
    """Bug: a checker that answered for the first text and then failed left the
    remaining texts unchecked, yet the summary said "clean" and the exit code was 0."""

    def test_languagetool_failing_after_the_first_text_is_not_clean(self):
        FlakyLanguageTool.calls = 0
        server, url = serve(FlakyLanguageTool)
        try:
            r = run('--lang', 'de', 'Alles gut', 'Auch gut', 'Noch ein Text', lt_url=url + '/v2/check')
        finally:
            server.shutdown()
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertNotIn('clean', r.stdout)
        self.assertIn('2 of 3 texts', r.stdout)

    def test_allow_unchecked_still_reports_the_gap(self):
        FlakyLanguageTool.calls = 0
        server, url = serve(FlakyLanguageTool)
        try:
            r = run('--allow-unchecked', '--lang', 'de', 'Alles gut', 'Auch gut', lt_url=url + '/v2/check')
        finally:
            server.shutdown()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('NOT CHECKED', r.stdout)

    def test_korektor_failing_after_the_first_text_is_not_clean(self):
        FakeKorektor.calls, FakeKorektor.fail_after_first = 0, True
        server, url = serve(FakeKorektor)
        try:
            r = run('--online', '--lang', 'cz', 'Ahoj světe', 'Druhý text', korektor_url=url + '/correct')
        finally:
            server.shutdown()
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertNotIn('clean', r.stdout)


class TestOnlineIsOptIn(unittest.TestCase):
    def test_korektor_is_not_called_without_online(self):
        FakeKorektor.calls, FakeKorektor.fail_after_first = 0, False
        server, url = serve(FakeKorektor)
        try:
            r = run('--lang', 'cz', 'Ahoj světe', korektor_url=url + '/correct')
        finally:
            server.shutdown()
        self.assertEqual(FakeKorektor.calls, 0)
        self.assertEqual(r.returncode, 3, r.stdout)        # nothing local ran: unchecked, not clean
        self.assertIn('--online', r.stdout)

    def test_korektor_runs_with_online(self):
        FakeKorektor.calls, FakeKorektor.fail_after_first = 0, False
        server, url = serve(FakeKorektor)
        try:
            r = run('--online', '--lang', 'cz', 'Ahoj světe', 'Druhý text', korektor_url=url + '/correct')
        finally:
            server.shutdown()
        self.assertEqual(FakeKorektor.calls, 2)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('with korektor: clean', r.stdout)


class TestMetaAndGoogleFields(unittest.TestCase):
    """Bug: Meta's primary text (`message`) and headline (`name` inside link_data)
    were never collected, so a spec could pass with its main copy unchecked."""

    @classmethod
    def setUpClass(cls):
        cls.server, base = serve(FakeLanguageTool)
        cls.url = base + '/v2/check'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeLanguageTool.seen.clear()

    def texts(self, spec):
        path = spec_file(spec)
        try:
            r = run(path, lt_url=self.url)
        finally:
            os.unlink(path)
        return r, sorted(t for _, t, _ in FakeLanguageTool.seen)

    def test_meta_object_story_spec(self):
        spec = {'market': 'de', 'name': 'DE_acq_internal_ad_name',
                'object_story_spec': {
                    'link_data': {'message': 'Primaertext mit Tset', 'name': 'Die Headline',
                                  'description': 'Linkbeschreibung',
                                  'child_attachments': [{'name': 'Karte eins', 'description': 'Karte'}]},
                    'video_data': {'message': 'Video Text', 'title': 'Video Titel',
                                   'link_description': 'Video Beschreibung'}}}
        r, texts = self.texts(spec)
        self.assertEqual(r.returncode, 1, r.stdout)                  # the typo in `message` is found
        self.assertEqual(texts, sorted(['Primaertext mit Tset', 'Die Headline', 'Linkbeschreibung',
                                        'Karte eins', 'Karte', 'Video Text', 'Video Titel',
                                        'Video Beschreibung']))
        self.assertNotIn('DE_acq_internal_ad_name', texts)           # top-level name = ad name, not copy

    def test_meta_asset_feed_spec_and_plain_keys(self):
        spec = {'market': 'pl', 'asset_feed_spec': {
                    'bodies': [{'text': 'Tekst glowny'}], 'titles': [{'text': 'Naglowek'}],
                    'descriptions': [{'text': 'Opis'}]},
                'body': 'Body text', 'title': 'Title text', 'message': 'Message text'}
        r, texts = self.texts(spec)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(texts, sorted(['Tekst glowny', 'Naglowek', 'Opis', 'Body text', 'Title text',
                                        'Message text']))

    def test_google_plural_fields(self):
        spec = {'market': 'de', 'headlines': ['H1', 'H2'], 'long_headlines': ['Lang'],
                'descriptions': ['D1'], 'long_headline': 'Lang zwei'}
        r, texts = self.texts(spec)
        self.assertEqual(texts, ['D1', 'H1', 'H2', 'Lang', 'Lang zwei'])

    def test_spec_without_any_known_copy_field_is_a_usage_error(self):
        path = spec_file({'market': 'de', 'adcopy': {'zeile': 'Ein Text'}})
        try:
            r = run(path, lt_url=self.url)
        finally:
            os.unlink(path)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn('zeile', r.stdout)                              # names the keys it saw


if __name__ == '__main__':
    unittest.main()

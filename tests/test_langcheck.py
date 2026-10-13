"""Tests for ads-ops/langcheck_ads.py, the language gate before ad copy is uploaded.

No dictionaries, no network: LanguageTool is replaced by a tiny local HTTP
server that answers like the real /v2/check endpoint, so the gate logic
(exit codes, fail-closed behaviour, ignore list, text collection) is tested
exactly as it runs. Standard library only.
"""
import contextlib
import http.server
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import types
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


def stop(server):
    server.shutdown()
    server.server_close()                       # no unclosed-socket ResourceWarning


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
        cls.server, base = serve(FakeLanguageTool)
        cls.url = base + '/v2/check'

    @classmethod
    def tearDownClass(cls):
        stop(cls.server)

    def setUp(self):
        FakeLanguageTool.seen.clear()

    def test_finding_blocks_the_upload(self):
        r = run('--lang', 'de', 'Das ist ein Tset', lt_url=self.url)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn('"Tset" -> Test', r.stdout)
        self.assertEqual(FakeLanguageTool.seen[0][0], 'de-DE')
        self.assertEqual(FakeLanguageTool.seen[0][2], 'picky')

    def test_clean_copy_passes_and_names_the_tool_that_ran(self):
        r = run('--layers', 'languagetool', '--lang', 'pl', 'Zainstaluj aplikacje', lt_url=self.url)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('checked in pl with languagetool: clean', r.stdout)

    def test_ignored_platform_terms_are_not_findings(self):
        r = run('--layers', 'languagetool', '--lang', 'de', 'Jetzt bei Google Play', lt_url=self.url)
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
        self.assertEqual(FakeLanguageTool.seen[0][0], 'de-AT')               # market AT -> Austrian German


class TestPartialCoverage(unittest.TestCase):
    """Bug: a checker that answered for the first text and then failed left the
    remaining texts unchecked, yet the summary said "clean" and the exit code was 0."""

    def test_languagetool_failing_after_the_first_text_is_not_clean(self):
        FlakyLanguageTool.calls = 0
        server, url = serve(FlakyLanguageTool)
        try:
            r = run('--layers', 'languagetool', '--lang', 'de', 'Alles gut', 'Auch gut', 'Noch ein Text',
                    lt_url=url + '/v2/check')
        finally:
            stop(server)
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertNotIn('clean', r.stdout)
        self.assertIn('2 of 3 texts', r.stdout)

    def test_allow_unchecked_still_reports_the_gap(self):
        FlakyLanguageTool.calls = 0
        server, url = serve(FlakyLanguageTool)
        try:
            r = run('--allow-unchecked', '--lang', 'de', 'Alles gut', 'Auch gut', lt_url=url + '/v2/check')
        finally:
            stop(server)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('NOT CHECKED', r.stdout)

    def test_korektor_failing_after_the_first_text_is_not_clean(self):
        FakeKorektor.calls, FakeKorektor.fail_after_first = 0, True
        server, url = serve(FakeKorektor)
        try:
            r = run('--online', '--lang', 'cz', 'Ahoj světe', 'Druhý text', korektor_url=url + '/correct')
        finally:
            stop(server)
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertNotIn('clean', r.stdout)


class TestOnlineIsOptIn(unittest.TestCase):
    def test_korektor_is_not_called_without_online(self):
        FakeKorektor.calls, FakeKorektor.fail_after_first = 0, False
        server, url = serve(FakeKorektor)
        try:
            r = run('--lang', 'cz', 'Ahoj světe', korektor_url=url + '/correct')
        finally:
            stop(server)
        self.assertEqual(FakeKorektor.calls, 0)
        self.assertEqual(r.returncode, 3, r.stdout)        # nothing local ran: unchecked, not clean
        self.assertIn('--online', r.stdout)

    def test_korektor_runs_with_online(self):
        FakeKorektor.calls, FakeKorektor.fail_after_first = 0, False
        server, url = serve(FakeKorektor)
        try:
            r = run('--layers', 'korektor', '--online', '--lang', 'cz', 'Ahoj světe', 'Druhý text',
                    korektor_url=url + '/correct')
        finally:
            stop(server)
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
        stop(cls.server)

    def setUp(self):
        FakeLanguageTool.seen.clear()

    def texts(self, spec):
        path = spec_file(spec)
        try:
            r = run('--layers', 'languagetool', path, lt_url=self.url)
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


# ---------------------------------------------------------------- in-process tests with a fake Hunspell
# The subprocess tests above have no dictionary. These load the script as a module,
# give it a fake `spylls` and a fake dictionary file, and call main() directly, so the
# case "Hunspell ran, LanguageTool did not" can be tested without installing anything.

DEAD_LT = 'http://127.0.0.1:9/v2/check'


class FakeDictionary:
    words = set()
    loaded = None

    @classmethod
    def from_files(cls, path):
        FakeDictionary.loaded = os.path.basename(path)
        return cls()

    def lookup(self, w):
        return w in FakeDictionary.words


def load_module(dicts=None):
    if dicts is not None:
        fake = types.ModuleType('spylls')
        fake.hunspell = types.ModuleType('spylls.hunspell')
        fake.hunspell.Dictionary = FakeDictionary
        sys.modules['spylls'], sys.modules['spylls.hunspell'] = fake, fake.hunspell
    spec = importlib.util.spec_from_file_location('langcheck_ads_under_test', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if dicts is not None:
        mod.DICTS = dicts
    mod.LT_URL = DEAD_LT                                         # nothing listens there
    mod.KOREKTOR = 'http://127.0.0.1:9/korektor'
    return mod


class InProcess(unittest.TestCase):
    DICT_NAMES = ('pl_PL', 'cs_CZ', 'de_DE_frami', 'de_AT_frami', 'de_CH_frami', 'hu_HU')

    @classmethod
    def setUpClass(cls):
        cls.dicts = tempfile.mkdtemp(prefix='langcheck-dicts-')
        for n in cls.DICT_NAMES:
            for ext in ('.aff', '.dic'):
                open(os.path.join(cls.dicts, n + ext), 'w').close()
        cls.mod = load_module(cls.dicts)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dicts, ignore_errors=True)
        for m in ('spylls', 'spylls.hunspell'):
            sys.modules.pop(m, None)

    def setUp(self):
        FakeDictionary.words = {'zainstaluj', 'aplikację', 'ahoj', 'světe', 'nové', 'jetzt', 'testen',
                                'egészség', 'das', 'ist', 'gut'}
        FakeDictionary.loaded = None
        self.mod.LT_URL = DEAD_LT

    def main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.mod.main(list(argv))
        return code, out.getvalue()

    def with_lt(self, *argv):
        server, url = serve(FakeLanguageTool)
        self.mod.LT_URL = url + '/v2/check'
        FakeLanguageTool.seen.clear()
        try:
            return self.main(*argv)
        finally:
            stop(server)
            self.mod.LT_URL = DEAD_LT


class TestRequestedLayerUnavailable(InProcess):
    """Bug: LanguageTool unreachable from the first text was dropped from coverage, so a
    spelling-only run printed "clean" and exited 0 with grammar never checked."""

    def test_total_languagetool_outage_with_hunspell_is_exit_3(self):
        code, out = self.main('--lang', 'pl', 'Zainstaluj aplikację')
        self.assertEqual(code, 3, out)
        self.assertNotIn('clean', out)
        self.assertIn('grammar NOT checked', out)
        self.assertIn('LanguageTool is the only grammar layer for pl', out)

    def test_total_outage_with_allow_unchecked_is_a_dry_run(self):
        code, out = self.main('--allow-unchecked', '--lang', 'pl', 'Zainstaluj aplikację')
        self.assertEqual(code, 0, out)
        self.assertIn('NOT CHECKED', out)

    def test_explicit_hunspell_only_is_clean(self):
        code, out = self.main('--layers', 'hunspell', '--lang', 'pl', 'Zainstaluj aplikację')
        self.assertEqual(code, 0, out)
        self.assertIn('with hunspell: clean', out)

    def test_both_layers_up_is_clean(self):
        code, out = self.with_lt('--lang', 'pl', 'Zainstaluj aplikację')
        self.assertEqual(code, 0, out)
        self.assertIn('with hunspell + languagetool: clean', out)

    def test_missing_dictionary_is_exit_3_even_when_languagetool_is_up(self):
        code, out = self.with_lt('--lang', 'sk', 'Nainštalujte si aplikáciu')   # no sk_SK in the fake dicts
        self.assertEqual(code, 3, out)
        self.assertIn('[hunspell] NOT available', out)

    def test_czech_without_online_says_grammar_not_checked(self):
        code, out = self.main('--lang', 'cz', 'Ahoj světe')
        self.assertEqual(code, 3, out)
        self.assertIn('grammar not checked', out)
        self.assertNotIn('clean', out)

    def test_czech_hunspell_only_on_purpose(self):
        code, out = self.main('--layers', 'hunspell', '--lang', 'cz', 'Ahoj světe')
        self.assertEqual(code, 0, out)
        code, out = self.main('--allow-unchecked', '--lang', 'cz', 'Ahoj světe')
        self.assertEqual(code, 0, out)
        self.assertIn('grammar not checked', out)

    def test_language_without_any_grammar_layer_is_not_clean_by_default(self):
        code, out = self.main('--lang', 'hu', 'Egészség')
        self.assertEqual(code, 3, out)
        self.assertIn('grammar not checked', out)
        self.assertEqual(self.main('--layers', 'hunspell', '--lang', 'hu', 'Egészség')[0], 0)

    def test_unknown_layer_is_a_usage_error(self):
        self.assertEqual(self.main('--layers', 'grammarly', '--lang', 'pl', 'x')[0], 2)


class TestSpellingDetails(InProcess):
    def test_short_all_caps_words_are_checked(self):
        code, out = self.main('--layers', 'hunspell', '--lang', 'cz', 'NOVÉ GRATSI')
        self.assertEqual(code, 1, out)
        self.assertIn('"GRATSI"', out)
        self.assertNotIn('"NOVÉ"', out)                          # known in lower case

    def test_listed_acronyms_stay_ignored(self):
        code, out = self.main('--layers', 'hunspell', '--lang', 'cz', 'Ahoj EUR CTA')
        self.assertEqual(code, 0, out)

    def test_german_variants_use_their_own_dictionary_and_languagetool_code(self):
        for code_in, dict_name, lt in (('de-AT', 'de_AT_frami', 'de-AT'), ('ch', 'de_CH_frami', 'de-CH'),
                                       ('at', 'de_AT_frami', 'de-AT'), ('de', 'de_DE_frami', 'de-DE')):
            self.assertEqual(self.mod.resolve(code_in), ('de', lt, dict_name), code_in)
        self.main('--layers', 'hunspell', '--lang', 'de-CH', 'Das ist gut')
        self.assertEqual(FakeDictionary.loaded, 'de_CH_frami')

    def test_swiss_market_reaches_languagetool_as_de_ch(self):
        path = spec_file({'market': 'CH', 'headline': 'Das ist gut'})
        try:
            code, out = self.with_lt(path)
        finally:
            os.unlink(path)
        self.assertEqual(FakeLanguageTool.seen[0][0], 'de-CH')
        self.assertEqual(code, 0, out)


class TestGoogleAssetFields(unittest.TestCase):
    """Bug: sitelink text, callouts, display paths and other Google text assets were
    not collected, so they were never checked."""

    def test_google_text_asset_fields_are_collected(self):
        spec = {'market': 'pl', 'campaign': 'internal name',
                'sitelinks': [{'sitelink_text': 'Cennik', 'description1': 'Opis jeden', 'description2': 'Opis dwa'},
                              {'link_text': 'Kontakt', 'line1': 'Linia'}],
                'callouts': ['Bez opłat', 'Szybko'], 'callout_text': 'Pomoc 24/7',
                'path1': 'konto', 'path2': 'darmowe',
                'structured_snippet': {'header': 'Services', 'values': ['Konto', 'Karta']},
                'business_name': 'Firma', 'promotion_target': 'Promocja', 'final_url': 'https://example.com/x',
                'values': ['not copy outside a snippet']}
        path = spec_file(spec)
        try:
            _, texts, other = load_module().collect(path)
        finally:
            os.unlink(path)
        self.assertEqual(sorted(texts), sorted(['Cennik', 'Opis jeden', 'Opis dwa', 'Kontakt', 'Linia',
                                                'Bez opłat', 'Szybko', 'Pomoc 24/7', 'konto', 'darmowe',
                                                'Konto', 'Karta', 'Firma', 'Promocja']))
        self.assertIn('final_url', other)
        self.assertNotIn('not copy outside a snippet', texts)


if __name__ == '__main__':
    unittest.main()

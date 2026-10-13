# -*- coding: utf-8 -*-
"""Native-language check of ad copy before upload.

Read-only, it never changes the copy. Exit codes, so it can gate an upload the
same way creative QA does:
    0  every text was checked by every requested layer, nothing found
    1  findings (do not upload)
    2  usage error (no texts, no language, unknown layer, a spec file with no recognised copy field)
    3  not fully checked: a requested layer was not available (no dictionary, server
       unreachable, Korektor without --online, no grammar layer for the language) or
       failed part way and left some texts unchecked. Fails closed: a partial check is
       never reported as clean. --allow-unchecked turns this into exit 0 for a
       deliberate dry run (the gap is still printed).

    python -I ads-ops/langcheck_ads.py copy.json            # {"market": "pl", "copy": ["...", "..."]}
    python -I ads-ops/langcheck_ads.py spec.json            # any JSON with a "market"/"lang" key, see COPY_KEYS
    python -I ads-ops/langcheck_ads.py --lang de "Text 1" "Text 2"
    add --online to also use Korektor for Czech (the only tool that sends text out)
    add --layers hunspell[,languagetool,korektor] to request only some layers on purpose
    add --allow-unchecked to exit 0 even when not every text was checked (dry run only)

Layers. By default a language gets spelling (Hunspell) and grammar (LanguageTool;
for Czech, Korektor). Every requested layer must run on every text, or the result is exit 3:
  - Hunspell via spylls (pip install spylls) + LibreOffice dictionaries
    (github.com/LibreOffice/dictionaries; put the .aff/.dic files in LANGTOOLS_DICTS).
    Regional variants use their own dictionary (de_AT_frami, de_CH_frami, en_US, pt_BR).
  - LanguageTool, level=picky, local HTTP server (LT_URL, default http://localhost:8081/v2/check).
    For every language except Czech it is the only grammar layer, so when it is down
    grammar is not checked at all. It has no Czech.
  - Czech has no local grammar layer. Without --online the run says "grammar not checked"
    and exits 3, unless you pass --layers hunspell (spelling only, on purpose).
  - Korektor (UFAL, LINDAT REST API) for Czech spelling and diacritics. Off unless
    --online is given: it sends the ad text to an external server. Per the LINDAT
    service pages at the time of writing, the Korektor models are licensed CC BY-NC-SA
    (commercial use needs permission from the authors) and submitted text may be
    logged by the service. Check the current terms before using it on client copy.
Extra words that are fine on purpose (brand, product, feature names): one per line in
ads-ops/langcheck-ignore.txt.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DICTS = os.environ.get('LANGTOOLS_DICTS') or os.path.join(HERE, 'dicts')
LT_URL = os.environ.get('LT_URL') or 'http://localhost:8081/v2/check'
KOREKTOR = os.environ.get('KOREKTOR_URL') or 'https://lindat.mff.cuni.cz/services/korektor/api/correct'

MARKET_LANG = {'cz': 'cs', 'cs': 'cs', 'sk': 'sk', 'pl': 'pl', 'de': 'de', 'at': 'de', 'ch': 'de',
               'en': 'en', 'uk': 'en', 'gb': 'en', 'eu': 'en', 'es': 'es', 'fr': 'fr', 'it': 'it',
               'hu': 'hu', 'nl': 'nl', 'pt': 'pt'}
LT_LANG = {'en': 'en-GB', 'de': 'de-DE', 'pl': 'pl-PL', 'sk': 'sk-SK', 'es': 'es', 'fr': 'fr',
           'it': 'it', 'pt': 'pt-PT', 'nl': 'nl'}
HUNSPELL = {'cs': 'cs_CZ', 'sk': 'sk_SK', 'pl': 'pl_PL', 'de': 'de_DE_frami', 'es': 'es_ES',
            'fr': 'fr_FR', 'it': 'it_IT', 'en': 'en_GB', 'hu': 'hu_HU', 'nl': 'nl_NL', 'pt': 'pt_PT'}
# Regional variants: (language, LanguageTool code, Hunspell dictionary). Swiss German has
# no "ß", Austrian German has its own vocabulary: checking them as de-DE gives wrong findings.
VARIANTS = {
    'at': ('de', 'de-AT', 'de_AT_frami'), 'de-at': ('de', 'de-AT', 'de_AT_frami'),
    'ch': ('de', 'de-CH', 'de_CH_frami'), 'de-ch': ('de', 'de-CH', 'de_CH_frami'),
    'us': ('en', 'en-US', 'en_US'), 'en-us': ('en', 'en-US', 'en_US'),
    'br': ('pt', 'pt-BR', 'pt_BR'), 'pt-br': ('pt', 'pt-BR', 'pt_BR'),
}
LAYERS = ('hunspell', 'languagetool', 'korektor')


def resolve(code):
    """Market or language code -> (language, LanguageTool code or None, Hunspell dictionary or None)."""
    c = str(code or '').strip().lower().replace('_', '-')
    if c in VARIANTS:
        return VARIANTS[c]
    lang = MARKET_LANG.get(c) or MARKET_LANG.get(c.split('-')[0]) or c
    return lang, LT_LANG.get(lang), HUNSPELL.get(lang)


def grammar_layers(lang):
    """The layers that check more than single words, for this language."""
    return ['korektor'] if lang == 'cs' else (['languagetool'] if LT_LANG.get(lang) else [])

# Platform and industry terms that are never typos.
IGNORE = {
    'iOS', 'Android', 'App', 'Store', 'Google', 'Play', 'Apple', 'Pay', 'Meta', 'TikTok', 'Instagram',
    'Facebook', 'YouTube', 'WhatsApp', 'Visa', 'Mastercard', 'API', 'CTA', 'EU', 'EUR', 'USD', 'GBP',
    'CZK', 'PLN', 'Kč', 'zł', 'app', 'apps', 'cashback', 'Cashback', 'online', 'Online', 'e-mail',
    'email', 'onboarding', 'fintech', 'premium', 'Premium',
}
_extra = os.path.join(HERE, 'langcheck-ignore.txt')
if os.path.exists(_extra):
    with open(_extra, encoding='utf-8') as f:
        IGNORE |= {w.strip() for w in f if w.strip() and not w.startswith('#')}
IGNORE_LOWER = {w.lower() for w in IGNORE}

# Picky-level LanguageTool rules that only flag ad formatting (headlines without a full
# stop, typographic quotes), never the language.
LT_DISABLED = ','.join([
    'WHITESPACE_RULE', 'PUNCTUATION_PARAGRAPH_END', 'UPPERCASE_SENTENCE_START', 'EN_QUOTES',
    'DASH_RULE', 'TYPOGRAFISCHE_ANFUEHRUNGSZEICHEN', 'FRENCH_WHITESPACE', 'APOS_TYP', 'TYPOGRAPHY',
    'UNPAIRED_BRACKETS', 'DOUBLE_PUNCTUATION', 'SENTENCE_WHITESPACE', 'PUNKT_ENDE_ABSATZ',
    'EN_UNPAIRED_QUOTES', 'ES_QUOTES', 'IT_QUOTES', 'FR_QUOTES', 'PL_QUOTES', 'SK_QUOTES',
    'ELLIPSIS', 'BRAK_KROPKI', 'POINT', 'COMILLAS_TIPOGRAFICAS', 'TYPOGRAFISCHE_APOSTROPHE',
])
# Keys whose string values (or lists of strings) are ad copy, wherever they sit in the JSON.
#   generic / creative specs: headline, sub, subline, cta, text, copy, primary_text
#   Google: headlines, descriptions, long_headline(s), description
#   Meta Marketing API: message (primary text), body/bodies, title/titles, link_description,
#   description(s); asset_feed_spec lists hold {"text": ...} objects, collected via "text".
#   Google assets: sitelink text and its two description lines, callouts, display URL paths,
#   business name, promotion text, structured snippet values (see VALUES_ARE_COPY_UNDER).
COPY_KEYS = ('headline', 'headlines', 'sub', 'subline', 'cta', 'text', 'copy', 'primary_text',
             'primary_texts', 'description', 'descriptions', 'long_headline', 'long_headlines',
             'message', 'body', 'bodies', 'title', 'titles', 'link_description',
             'sitelink_text', 'link_text', 'description1', 'description2', 'description_1',
             'description_2', 'line1', 'line2', 'callout', 'callouts', 'callout_text',
             'path1', 'path2', 'path_1', 'path_2', 'business_name', 'promotion_target')
# "name" is the headline inside Meta's link_data and carousel cards, but an internal
# ad/campaign name everywhere else, so it only counts under these parents.
NAME_IS_COPY_UNDER = ('link_data', 'child_attachments', 'template_data')
# "values" is ad copy only inside a structured snippet.
VALUES_ARE_COPY_UNDER = ('structured_snippet', 'structured_snippets', 'structured_snippet_asset', 'snippet')
TEXT_KEYS = COPY_KEYS                                         # backwards-compatible alias


def ignored(w):
    return w in IGNORE or w.lower() in IGNORE_LOWER


def collect(path):
    """Return (market/lang code as written, [texts], {unrecognised string keys}) from any JSON."""
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    lang = (str(d.get('market', d.get('lang', ''))).strip() or None) if isinstance(d, dict) else None
    texts, other = [], set()

    def walk(x, key='', parents=()):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, k, parents + (key,))
        elif isinstance(x, list):
            for v in x:
                walk(v, key, parents)
        elif isinstance(x, str):
            if (key in COPY_KEYS or (key == 'name' and any(p in NAME_IS_COPY_UNDER for p in parents))
                    or (key == 'values' and any(p in VALUES_ARE_COPY_UNDER for p in parents))):
                texts.append(x)
            elif key not in ('market', 'lang'):
                other.add(key)
    walk(d)
    return lang, texts, other


def unknown_words(texts, name):
    """{text: {word: text}} per text, or None when Hunspell or the dictionary `name` is not available."""
    if not name or not os.path.exists(os.path.join(DICTS, name + '.aff')):
        return None
    try:
        from spylls.hunspell import Dictionary
    except ImportError:
        return None
    d = Dictionary.from_files(os.path.join(DICTS, name))
    out = {}
    for t in texts:
        found = {}
        clean = re.sub(r'\S+@\S+|https?://\S+|\b[\w.-]+\.[a-z]{2,4}\b\S*', ' ', t)
        for w in re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)*", clean):
            if len(w) < 2 or ignored(w):
                continue
            # ALL-CAPS words are checked too ("GRATIS", "NOVÉ"): an acronym that is fine
            # on purpose goes in IGNORE or langcheck-ignore.txt.
            ok = (d.lookup(w) or (w[0].isupper() and d.lookup(w.lower()))
                  or (w.isupper() and d.lookup(w.capitalize())))
            if not ok and re.search(r"['’]", w):
                ok = all(d.lookup(p) or ignored(p) for p in re.split(r"['’]", w) if len(p) > 1)
            if not ok:
                found.setdefault(w, t)
        out[t] = found
    return out


def lt_check(text, lang):
    data = urllib.parse.urlencode({'text': text, 'language': lang, 'level': 'picky',
                                   'disabledRules': LT_DISABLED}).encode()
    with urllib.request.urlopen(LT_URL, data=data, timeout=120) as r:
        return json.load(r)['matches']


def korektor(text):
    q = urllib.parse.urlencode({'model': 'czech-spellchecker-130202', 'data': text})
    with urllib.request.urlopen(KOREKTOR + '?' + q, timeout=30) as r:
        out = json.load(r)['result']
    a, b = re.findall(r'\S+', text), re.findall(r'\S+', out)
    if len(a) != len(b):
        return [(text, out)] if out.strip() != text.strip() else []
    return [(x, y) for x, y in zip(a, b) if x != y]


def run_per_text(name, texts, check, report):
    """Run one tool text by text. Returns the set of texts it actually checked.
    On the first failure it stops (the server is most likely gone) and says how far it got."""
    done = set()
    for t in texts:
        try:
            result = check(t)
        except Exception as e:
            print(f'[{name}] failed after {len(done)} of {len(texts)} texts ({e.__class__.__name__}); '
                  f'the rest are NOT checked by {name}')
            break
        done.add(t)
        report(t, result)
    return done


def main(argv):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    online = '--online' in argv
    allow_unchecked = '--allow-unchecked' in argv
    argv = [a for a in argv if a not in ('--online', '--no-online', '--allow-unchecked')]   # --no-online: old default, now a no-op
    explicit_layers = None
    if '--layers' in argv:
        i = argv.index('--layers')
        if i + 1 >= len(argv):
            print('usage: --layers hunspell[,languagetool,korektor]')
            return 2
        explicit_layers = [x.strip().lower() for x in argv[i + 1].split(',') if x.strip()]
        bad = [x for x in explicit_layers if x not in LAYERS]
        if bad or not explicit_layers:
            print(f'unknown layer {", ".join(bad) or "(none)"}; known: {", ".join(LAYERS)}')
            return 2
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == '--lang':
        if len(argv) < 2:
            print('usage: --lang <code> "text" ...')
            return 2
        code, texts, other = argv[1], argv[2:], set()
    else:
        code, texts, other = collect(argv[0])
    if not code:
        print('no market/lang in the file; pass --lang')
        return 2
    lang, ltl, dict_name = resolve(code)
    texts = [t for t in dict.fromkeys(texts) if t.strip()]
    if not texts:
        print(f'no ad copy found (recognised keys: {", ".join(COPY_KEYS)}, and "name" under '
              f'{", ".join(NAME_IS_COPY_UNDER)}).' + (f' Keys seen: {", ".join(sorted(other))}.' if other else '')
              + ' Nothing was checked.')
        return 2
    grammar = grammar_layers(lang)
    requested = explicit_layers or ['hunspell'] + grammar
    problems = 0
    coverage = {name: set() for name in requested}     # requested layer -> texts it actually checked
    gaps = []                                          # why something requested did not run

    if not explicit_layers and not grammar:
        gaps.append(f'grammar not checked: no grammar layer for {lang} (LanguageTool does not support it). '
                    'Pass --layers hunspell to check spelling only on purpose.')

    if 'hunspell' in requested:
        unk = unknown_words(texts, dict_name)
        if unk is None:
            gaps.append(f'[hunspell] NOT available: no spylls or no {dict_name or lang} dictionary in {DICTS}; '
                        'spelling NOT checked')
        else:
            coverage['hunspell'] = set(unk)
            for t, found in unk.items():
                for w in found:
                    problems += 1
                    print(f'[hunspell] unknown "{w}"  in: {t}')

    if 'languagetool' in requested:
        only = ' (LanguageTool is the only grammar layer for ' + lang + ')' if grammar == ['languagetool'] else ''
        if not ltl:
            gaps.append(f'[languagetool] has no {lang}; grammar NOT checked by it')
        else:
            def lt_report(t, matches):
                nonlocal problems
                for x in matches:
                    bad = t[x['offset']:x['offset'] + x['length']]
                    if ignored(bad):
                        continue
                    problems += 1
                    sug = ', '.join(r['value'] for r in x['replacements'][:3])
                    print(f"[languagetool] {x['rule']['id']}: \"{bad}\" -> {sug or '?'}  ({x['message']})  in: {t}")
            coverage['languagetool'] = run_per_text('languagetool', texts, lambda t: lt_check(t, ltl), lt_report)
            if not coverage['languagetool']:
                gaps.append(f'[languagetool] not reachable at {LT_URL}: grammar NOT checked{only}')

    if 'korektor' in requested:
        if lang != 'cs':
            gaps.append(f'[korektor] is Czech only; {lang} NOT checked by it')
        elif not online:
            gaps.append('[korektor] off (it sends text to an external server; pass --online to use it). '
                        'Czech grammar not checked: there is no local grammar layer for Czech. '
                        'Pass --layers hunspell to check spelling only on purpose.')
        else:
            def k_report(t, fixes):
                nonlocal problems
                for a, b in fixes:
                    if ignored(a.strip('.,!?:;"()')):
                        continue
                    problems += 1
                    print(f'[korektor] "{a}" -> "{b}"  in: {t}')
            coverage['korektor'] = run_per_text('korektor', texts, korektor, k_report)
            if not coverage['korektor']:
                gaps.append('[korektor] not reachable, Czech NOT checked by Korektor')

    for g in gaps:
        print(g)
    # A text counts as checked only if every requested layer checked it.
    unchecked = [t for t in texts if any(t not in got for got in coverage.values())]
    ran = [name for name, got in coverage.items() if got]
    tools = ' + '.join(ran) or 'nothing'
    if unchecked or gaps:
        if not ran:
            print(f'{len(texts)} texts in {lang}: NOT CHECKED, no spelling or grammar tool was available '
                  '(see the setup in the docstring).')
        else:
            for name, got in coverage.items():
                if got and len(got) < len(texts):
                    print(f'[{name}] checked {len(got)} of {len(texts)} texts')
            missing = [name for name, got in coverage.items() if not got]
            print(f'{len(unchecked) or len(texts)} of {len(texts)} texts in {lang} NOT CHECKED by every requested layer '
                  f'(ran: {tools}' + (f'; did not run: {", ".join(missing)}' if missing else '') + '):')
            for t in (unchecked or texts):
                print(f'  - {t}')
        if problems:
            print(f'{problems} findings in the texts that were checked.')
            return 1
        print('Allowed by --allow-unchecked.' if allow_unchecked else 'Do not upload.')
        return 0 if allow_unchecked else 3
    print(f'{len(texts)} texts checked in {lang} with {tools}: '
          + ('clean' if not problems else f'{problems} findings'))
    print('Tools do not judge tone, claims or brand rules: read every text yourself too.')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

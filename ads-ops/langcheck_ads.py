# -*- coding: utf-8 -*-
"""Language check of ad copy before upload.

Read-only: it never changes the copy. Exit codes, so it can gate an upload:
    0  every layer that applies checked every text, nothing found
    1  findings, and every layer that applies checked every text (do not upload)
    2  usage error (no texts, unknown language or market, unknown layer, a spec file
       with no recognised copy field)
    3  not fully checked: a layer that applies did not check every text (no dictionary,
       LanguageTool unreachable or failing part way). 3 wins over 1: findings are still
       printed, but a partial check is never reported as clean or as "only findings".
       --allow-unchecked is a deliberate dry run: it gives 1 for findings, otherwise 0,
       and still prints the gap.

    python -I ads-ops/langcheck_ads.py copy.json              # {"market": "PL", "copy": ["...", "..."]}
    python -I ads-ops/langcheck_ads.py spec.json              # any JSON with "lang" or "market", see COPY_KEYS
    python -I ads-ops/langcheck_ads.py --lang de-AT "Text 1" "Text 2"
    python -I ads-ops/langcheck_ads.py --market CZ "Text"
    add --online to also use Korektor for Czech (the only layer that sends text out)
    add --layers hunspell[,languagetool,korektor] to request only some layers on purpose
    add --allow-unchecked for a dry run that does not fail on a missing layer

Language or market. --lang and a JSON "lang" or "language" key take a language tag:
cs, sk, pl, de, de-AT, de-CH, en, en-GB, en-US, es, fr, it, hu, nl, pt, pt-BR
(case and "_" or "-" do not matter). --market and a JSON "market" key take a country
and map it through MARKETS:
    CZ cs, SK sk, PL pl, DE de, AT de-AT, CH de-CH, GB en-GB, UK en-GB, IE en-GB,
    US en-US, ES es, FR fr, IT it, HU hu, NL nl, PT pt, BR pt-BR
A country code given as a language (--lang cz, --lang at, --lang uk) is exit 2, not a
guess: "uk" is Ukrainian as a language. In a file, "lang" wins over "market".

Layers that apply:
  - Hunspell (spelling), always: spylls (pip install spylls) with LibreOffice
    dictionaries (github.com/LibreOffice/dictionaries; .aff/.dic files in LANGTOOLS_DICTS).
    Regional variants use their own dictionary (de_AT_frami, de_CH_frami, en_US, pt_BR).
  - LanguageTool (grammar), for every language it has a module for: level=picky, a local
    server (LT_URL, default http://localhost:8081/v2/check). It has no Czech and no
    Hungarian, so those are checked for spelling only, and the run says so.
  - Korektor (UFAL, LINDAT REST API): Czech spelling and diacritics in context, not
    grammar. It applies only with --online, because it sends the ad text to an external
    server. Per the LINDAT service pages at the time of writing, the Korektor models are
    licensed CC BY-NC-SA (commercial use needs permission from the authors) and
    submitted text may be logged. Check the current terms before using it on client copy.

Same layers, exit codes and language tags as copy-langcheck
(github.com/terezakohutova/copy-langcheck), which also reads HTML, Markdown and plain
text and runs as a GitHub Action. This script adds the ad-platform fields (Meta
Marketing API specs, Google text assets) and market codes. Extra words that are fine on
purpose (brand, product, feature names): one per line in ads-ops/langcheck-ignore.txt.
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

# Language tag -> (language, LanguageTool code or None, Hunspell dictionary). Regional
# variants have their own entry: Swiss German has no "ß", Austrian German has its own
# vocabulary, so checking them as de-DE gives wrong findings.
LANGS = {
    'cs': ('cs', None, 'cs_CZ'), 'cs-cz': ('cs', None, 'cs_CZ'),
    'sk': ('sk', 'sk-SK', 'sk_SK'), 'sk-sk': ('sk', 'sk-SK', 'sk_SK'),
    'pl': ('pl', 'pl-PL', 'pl_PL'), 'pl-pl': ('pl', 'pl-PL', 'pl_PL'),
    'de': ('de', 'de-DE', 'de_DE_frami'), 'de-de': ('de', 'de-DE', 'de_DE_frami'),
    'de-at': ('de', 'de-AT', 'de_AT_frami'), 'de-ch': ('de', 'de-CH', 'de_CH_frami'),
    'en': ('en', 'en-GB', 'en_GB'), 'en-gb': ('en', 'en-GB', 'en_GB'), 'en-us': ('en', 'en-US', 'en_US'),
    'es': ('es', 'es', 'es_ES'), 'fr': ('fr', 'fr', 'fr_FR'), 'it': ('it', 'it', 'it_IT'),
    'hu': ('hu', None, 'hu_HU'), 'nl': ('nl', 'nl', 'nl_NL'),
    'pt': ('pt', 'pt-PT', 'pt_PT'), 'pt-pt': ('pt', 'pt-PT', 'pt_PT'), 'pt-br': ('pt', 'pt-BR', 'pt_BR'),
}
# Market (country) -> language tag. Listed in the docstring too; a test keeps them in sync.
MARKETS = {
    'CZ': 'cs', 'SK': 'sk', 'PL': 'pl', 'DE': 'de', 'AT': 'de-AT', 'CH': 'de-CH',
    'GB': 'en-GB', 'UK': 'en-GB', 'IE': 'en-GB', 'US': 'en-US', 'ES': 'es', 'FR': 'fr',
    'IT': 'it', 'HU': 'hu', 'NL': 'nl', 'PT': 'pt', 'BR': 'pt-BR',
}
LAYERS = ('hunspell', 'languagetool', 'korektor')


def resolve(code):
    """Language tag -> (language, LanguageTool code or None, Hunspell dictionary), or None."""
    return LANGS.get(str(code or '').strip().lower().replace('_', '-'))


def resolve_market(code):
    """Market (country code) -> the same tuple as resolve(), or None."""
    tag = MARKETS.get(str(code or '').strip().upper())
    return resolve(tag) if tag else None


def bad_code_message(code, kind):
    c = str(code).strip()
    if kind == 'lang' and c.upper() in MARKETS and resolve(c) is None:
        return (f'"{c}" is a country code, not a language: use --lang {MARKETS[c.upper()]} '
                f'or --market {c.upper()}')
    if kind == 'lang':
        return f'unsupported language "{c}"; known: {", ".join(sorted(LANGS))}'
    return f'unknown market "{c}"; known: {", ".join(MARKETS)}'

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
    """Return ((kind, code) or None, [texts], {unrecognised string keys}) from any JSON.
    kind is 'lang' for a "lang"/"language" key (wins) or 'market' for a "market" key."""
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    lang = None
    if isinstance(d, dict):
        for key, kind in (('lang', 'lang'), ('language', 'lang'), ('market', 'market')):
            if str(d.get(key) or '').strip():
                lang = (kind, str(d[key]).strip())
                break
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
            elif key not in ('market', 'lang', 'language'):
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
    if argv[0] in ('--lang', '--market'):
        if len(argv) < 2:
            print(f'usage: {argv[0]} <code> "text" ...')
            return 2
        code, texts, other = (argv[0][2:], argv[1]), argv[2:], set()
    else:
        code, texts, other = collect(argv[0])
    if not code:
        print('no "lang" or "market" in the file; pass --lang or --market')
        return 2
    kind, value = code
    resolved = resolve(value) if kind == 'lang' else resolve_market(value)
    if resolved is None:
        print(bad_code_message(value, kind))
        return 2
    lang, ltl, dict_name = resolved
    texts = [t for t in dict.fromkeys(texts) if t.strip()]
    if not texts:
        print(f'no ad copy found (recognised keys: {", ".join(COPY_KEYS)}, and "name" under '
              f'{", ".join(NAME_IS_COPY_UNDER)}).' + (f' Keys seen: {", ".join(sorted(other))}.' if other else '')
              + ' Nothing was checked.')
        return 2
    # The layers that apply: Hunspell always, LanguageTool where it has the language,
    # Korektor for Czech only with --online. --layers narrows this on purpose.
    applies = ['hunspell'] + (['languagetool'] if ltl else []) + (['korektor'] if lang == 'cs' and online else [])
    requested = explicit_layers or applies
    problems = 0
    coverage = {name: set() for name in requested}     # requested layer -> texts it actually checked
    gaps = []                                          # why something requested did not run

    if not explicit_layers and not ltl:
        print(f'note: LanguageTool has no {lang}, so {lang} is checked for spelling only (no grammar layer).'
              + (' Korektor (Czech spelling and diacritics in context) is off; --online turns it on.'
                 if lang == 'cs' and not online else ''))

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
        only = f' (LanguageTool is the only grammar layer for {lang})' if ltl else ''
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
            gaps.append('[korektor] requested but off: it sends text to an external server, '
                        'pass --online to use it. Czech NOT checked by Korektor')
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
        if allow_unchecked:
            print('Dry run (--allow-unchecked): the gap above is not counted.')
            return 1 if problems else 0
        print('Do not upload: not fully checked (exit 3 wins over findings).')
        return 3
    print(f'{len(texts)} texts checked in {lang} with {tools}: '
          + ('clean' if not problems else f'{problems} findings'))
    print('Tools do not judge tone, claims or brand rules: read every text yourself too.')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

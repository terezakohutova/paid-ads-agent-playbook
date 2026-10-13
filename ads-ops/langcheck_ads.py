# -*- coding: utf-8 -*-
"""Native-language check of ad copy before upload.

Read-only, it never changes the copy. Exit codes, so it can gate an upload the
same way creative QA does:
    0  every text checked by at least one tool, nothing found
    1  findings (do not upload)
    2  usage error (no texts, no language)
    3  nothing was actually checked (no dictionary, no LanguageTool server, Korektor
       off or unreachable). Fails closed: "no tool ran" is never reported as clean.
       --allow-unchecked turns this into exit 0 for a deliberate dry run.

    python -I ads-ops/langcheck_ads.py copy.json            # {"market": "pl", "copy": ["...", "..."]}
    python -I ads-ops/langcheck_ads.py spec.json            # any JSON with a "market"/"lang" key: headline, cta, primary_text, ... are collected
    python -I ads-ops/langcheck_ads.py --lang de "Text 1" "Text 2"
    add --no-online to skip Korektor (the only tool that sends text out)
    add --allow-unchecked to exit 0 even when no checker is available (dry run only)

Tools (each one is optional, a missing one is reported, not fatal):
  - Hunspell via spylls (pip install spylls) + LibreOffice dictionaries
    (github.com/LibreOffice/dictionaries; put the .aff/.dic files in LANGTOOLS_DICTS).
  - LanguageTool, level=picky, local HTTP server (LT_URL, default http://localhost:8081/v2/check).
    It has no Czech, so Czech gets Hunspell + Korektor.
  - Korektor (UFAL, LINDAT REST API) for Czech spelling and diacritics.
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
KOREKTOR = 'https://lindat.mff.cuni.cz/services/korektor/api/correct'

MARKET_LANG = {'cz': 'cs', 'cs': 'cs', 'sk': 'sk', 'pl': 'pl', 'de': 'de', 'at': 'de', 'ch': 'de',
               'en': 'en', 'uk': 'en', 'gb': 'en', 'eu': 'en', 'es': 'es', 'fr': 'fr', 'it': 'it',
               'hu': 'hu', 'nl': 'nl', 'pt': 'pt'}
LT_LANG = {'en': 'en-GB', 'de': 'de-DE', 'pl': 'pl-PL', 'sk': 'sk-SK', 'es': 'es', 'fr': 'fr',
           'it': 'it', 'pt': 'pt-PT', 'nl': 'nl'}
HUNSPELL = {'cs': 'cs_CZ', 'sk': 'sk_SK', 'pl': 'pl_PL', 'de': 'de_DE_frami', 'es': 'es_ES',
            'fr': 'fr_FR', 'it': 'it_IT', 'en': 'en_GB', 'hu': 'hu_HU', 'nl': 'nl_NL', 'pt': 'pt_PT'}

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
TEXT_KEYS = ('headline', 'headlines', 'sub', 'subline', 'cta', 'text', 'copy', 'primary_text',
             'description', 'descriptions', 'long_headline')


def ignored(w):
    return w in IGNORE or w.lower() in IGNORE_LOWER


def collect(path):
    """Return (lang, [texts]) from any JSON with a market/lang key."""
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    lang = MARKET_LANG.get(str(d.get('market', d.get('lang', ''))).lower())
    texts = []

    def walk(x, key=''):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, k)
        elif isinstance(x, list):
            for v in x:
                walk(v, key)
        elif isinstance(x, str) and key in TEXT_KEYS:
            texts.append(x)
    walk(d)
    return lang, texts


def unknown_words(texts, lang):
    name = HUNSPELL.get(lang)
    if not name or not os.path.exists(os.path.join(DICTS, name + '.aff')):
        return None
    try:
        from spylls.hunspell import Dictionary
    except ImportError:
        return None
    d = Dictionary.from_files(os.path.join(DICTS, name))
    out = {}
    for t in texts:
        t = re.sub(r'\S+@\S+|https?://\S+|\b[\w.-]+\.[a-z]{2,4}\b\S*', ' ', t)
        for w in re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)*", t):
            if len(w) < 2 or ignored(w) or (w.isupper() and len(w) <= 6):
                continue
            ok = d.lookup(w) or (w[0].isupper() and d.lookup(w.lower()))
            if not ok and re.search(r"['’]", w):
                ok = all(d.lookup(p) or ignored(p) for p in re.split(r"['’]", w) if len(p) > 1)
            if not ok:
                out.setdefault(w, t)
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


def main(argv):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    online = '--no-online' not in argv
    allow_unchecked = '--allow-unchecked' in argv
    argv = [a for a in argv if a not in ('--no-online', '--allow-unchecked')]
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == '--lang':
        if len(argv) < 2:
            print('usage: --lang <code> "text" ...')
            return 2
        lang, texts = MARKET_LANG.get(argv[1].lower(), argv[1].lower()), argv[2:]
    else:
        lang, texts = collect(argv[0])
    if not lang:
        print('no market/lang in the file; pass --lang')
        return 2
    texts = [t for t in dict.fromkeys(texts) if t.strip()]
    if not texts:
        print(f'no ad texts found (looked for keys: {", ".join(TEXT_KEYS)})')
        return 2
    problems = 0
    ran = []                                  # tools that actually checked the texts

    unk = unknown_words(texts, lang)
    if unk is None:
        print(f'[hunspell] skipped: no spylls or no {HUNSPELL.get(lang, lang)} dictionary in {DICTS}')
    else:
        ran.append('hunspell')
        for w, ctx in unk.items():
            problems += 1
            print(f'[hunspell] unknown "{w}"  in: {ctx}')

    ltl = LT_LANG.get(lang)
    if ltl:
        try:
            for i, t in enumerate(texts):
                matches = lt_check(t, ltl)
                if i == 0:
                    ran.append('languagetool')
                for x in matches:
                    bad = t[x['offset']:x['offset'] + x['length']]
                    if ignored(bad):
                        continue
                    problems += 1
                    sug = ', '.join(r['value'] for r in x['replacements'][:3])
                    print(f"[languagetool] {x['rule']['id']}: \"{bad}\" -> {sug or '?'}  ({x['message']})  in: {t}")
        except Exception as e:
            print(f'[languagetool] not reachable at {LT_URL} ({e.__class__.__name__}), grammar NOT checked')

    if lang == 'cs' and online:
        for i, t in enumerate(texts):
            try:
                fixes = korektor(t)
                if i == 0:
                    ran.append('korektor')
                for a, b in fixes:
                    if ignored(a.strip('.,!?:;"()')):
                        continue
                    problems += 1
                    print(f'[korektor] "{a}" -> "{b}"  in: {t}')
            except Exception as e:
                print(f'[korektor] not reachable ({e.__class__.__name__}), Czech checked by dictionary only')
                break

    if not ran:
        print(f'{len(texts)} texts in {lang}: NOT CHECKED, no spelling or grammar tool was available '
              '(see the setup in the docstring).' + (' Allowed by --allow-unchecked.' if allow_unchecked else ' Do not upload.'))
        return 0 if allow_unchecked else 3
    print(f'{len(texts)} texts checked in {lang} with {" + ".join(ran)}: '
          + ('clean' if not problems else f'{problems} findings'))
    print('Tools do not judge tone, claims or brand rules: read every text yourself too.')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

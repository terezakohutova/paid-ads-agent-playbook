# -*- coding: utf-8 -*-
"""Score the blind runs against the answer key.

    python -I sample-client/tallo/score.py

Each run folder in blind-runs/ holds the unedited output.md, run.json and a
scoring.json in which every FAIL finding of the run is quoted verbatim and
labelled by hand: a key id (G1..., M1...), "extra-valid" (a real problem that
was not planted) or "false-positive". This script only does the arithmetic and
checks the labels against the key; the labelling itself is a human judgment.

    recall            = planted issues found / planted issues
    precision         = (findings matching a planted issue + valid extras) / FAIL findings
    strict precision  = findings matching a planted issue / FAIL findings
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, 'blind-runs')


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def score(key_ids, labels):
    """key_ids: list of planted ids; labels: one label per FAIL finding."""
    unknown = [l for l in labels if l not in key_ids and l not in ('extra-valid', 'false-positive')]
    if unknown:
        raise ValueError(f'labels not in the key: {unknown}')
    found = sorted(set(l for l in labels if l in key_ids), key=key_ids.index)
    matched = sum(1 for l in labels if l in key_ids)
    extra = labels.count('extra-valid')
    fp = labels.count('false-positive')
    n = len(labels)
    return {
        'found': len(found), 'planted': len(key_ids),
        'missed': [k for k in key_ids if k not in found],
        'fail_findings': n, 'matched': matched, 'extra_valid': extra, 'false_positives': fp,
        'recall': len(found) / len(key_ids) if key_ids else 0.0,
        'precision': (matched + extra) / n if n else 0.0,
        'strict_precision': matched / n if n else 0.0,
    }


def score_all():
    key = load(os.path.join(HERE, 'answer-key.json'))
    out = {}
    for run in sorted(os.listdir(RUNS)):
        sc = os.path.join(RUNS, run, 'scoring.json')
        if not os.path.isfile(sc):
            continue
        s = load(sc)
        ids = [x['id'] for x in key[s['key']]]
        out[run] = score(ids, [f['label'] for f in s['findings']])
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print('| Run | Recall | Precision | Strict precision | False positives | Missed |')
    print('|---|---|---|---|---|---|')
    for run, r in score_all().items():
        print(f"| {run} | {r['found']}/{r['planted']} | {r['matched'] + r['extra_valid']}/{r['fail_findings']} "
              f"| {r['matched']}/{r['fail_findings']} | {r['false_positives']} | {', '.join(r['missed']) or 'none'} |")
    return 0


if __name__ == '__main__':
    sys.exit(main())

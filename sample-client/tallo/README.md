# Sample client: Tallo

Tallo is fictional: an invented app for saving and investing in ETF portfolios,
running Google Ads and Meta in CZ, SK and PL. Any resemblance to a real company is
accidental. It exists to test the two agents' Phase 0 audits against
data where the right answer is known.

- [`google/data/`](google/data/) and [`meta/data/`](meta/data/): the accounts as CSV
  exports, plus `client-facts.csv` (what a brief would supply) and the team's own
  `change-ledger.csv`. No column says what is wrong.
- [`answer-key.md`](answer-key.md) / [`answer-key.json`](answer-key.json): 16
  planted issues for Google plus 2 found later by an outside review, 12 for Meta,
  the clean controls, the corrections made after that review, and two flaws in the
  sample that the runs found.
- [`blind-runs/`](blind-runs/): three runs, each with the unedited `output.md`, a
  `run.json` (date, model, exact prompt, sha256 of every input) and a hand-labelled
  `scoring.json`.
- [`score.py`](score.py): the arithmetic. `python -I sample-client/tallo/score.py`

## How the runs were made

Each run was a fresh Claude Sonnet subagent with no conversation history. Its folder
held only a copy of the agent file and the CSVs. The prompt was neutral ("Audit the
Google Ads account. The exports are in .../data/") and said nothing about the
vertical, the date or what to look for (the exact text is in each `run.json`). No
playbook, no answer key, no web. The agent files the runs read are kept byte for
byte in [`blind-runs/agent-files/`](blind-runs/agent-files/).

## Results

| Run | Recall | Precision | Strict precision | False positives | Missed |
|---|---|---|---|---|---|
| google-run-1 | 16/18 | 16/16 | 16/16 | 0 | G17, G18 |
| google-run-2 | 16/18 | 17/17 | 16/17 | 0 | G17, G18 |
| meta-run-1 | 12/12 | 14/14 | 12/14 | 0 | none |

Recall is planted issues found. Precision counts FAIL findings that match a planted
issue or are real but unplanted ("extra-valid", explained in each `scoring.json`);
strict precision counts only planted matches. Strict precision is the number to
quote: the "extra-valid" label is the author's call.

The table was re-scored after an outside review added two issues nobody planted
(G17, G18) and corrected G1; no run output changed. What changed and why is in
[`answer-key.md`](answer-key.md#corrections-after-an-outside-review-2026-10-13).

## What these numbers do and don't show

- **They show** that a fresh agent with only the agent file follows the whole
  checklist and joins files to find issues no single column states.
- **They don't show** how it does on an account whose problems nobody planted. The
  same author wrote the checklist, the data and the key, so every planted issue maps
  to a checklist item; recall on planted issues is a test of following the
  checklist, not of finding the unknown. The two issues an outside reviewer found
  were missed by both Google runs, and one planted item (G1) was keyed on the wrong
  mechanism, which the runs repeated. Three runs is a small sample.
- **Scoring is a human judgment.** The labels in `scoring.json` were assigned by the
  repo author after reading each output. The tests check that every quoted excerpt
  is verbatim in the output and that the arithmetic matches this table; they cannot
  check that a label is right. Read the outputs and disagree where you do.
- **The runs found flaws in the sample** (a "clean" ledger row that likely breached
  its trigger, an unexplained conversion count). They are listed in the answer key
  and left in the data, since the runs were made against it.

## Try it yourself

From the repo root, start `claude` and ask "audit the Google Ads account in
`sample-client/tallo/google/data/`", then compare with the answer key. To repeat a
blind run properly, give a fresh agent a folder holding only the agent file and the
data, not this repo.

# Sample client: Tallo

A fictional app for saving and investing in ETF portfolios, running Google Ads and
Meta in CZ, SK and PL. It exists to test the two agents' Phase 0 audits against
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
held only a copy of the agent file and the CSVs. The prompt was neutral: "Audit the
Google Ads account. The exports are in .../data/", nothing about the vertical, the
date or what to look for (the exact text is in each `run.json`). No playbook, no
answer key, no web.

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

**Re-scored 2026-10-13** after an outside review, without changing any run output:
G1 in the key named the wrong lever (a Target CPI App campaign optimises for
installs whatever the Primary/Secondary status of First Deposit; bidding on it
needs tCPA on that in-app action or tROAS). Both Google runs still count as finding
G1, because both say nothing bids on First Deposit, but both blame the goal status,
so neither would have fixed it. The reviewer also found two issues nobody planted
(G17 App budgets under 50x target CPI, G18 a CZ ad priced in euro); they are in the
key now and both Google runs miss them. M8 was reworded as low severity, and
meta-run-1 had M6 counted twice for precision, now once. Before the re-score the
table read 16/16 recall for both Google runs and 15/15 (strict 13/15) precision
for the Meta run. Details in [`answer-key.md`](answer-key.md).

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

Copy `.claude/agents/google-ads.md` into your project and ask it to audit
`sample-client/tallo/google/data/`, then compare with the answer key. To repeat a
blind run properly, give a fresh agent a folder holding only the agent file and the
data, not this repo.

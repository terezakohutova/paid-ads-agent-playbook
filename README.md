# Paid Ads Agent Playbook

[![CI](https://github.com/terezakohutova/paid-ads-agent-playbook/actions/workflows/tests.yml/badge.svg)](https://github.com/terezakohutova/paid-ads-agent-playbook/actions/workflows/tests.yml)

Two Claude Code subagents that audit Google Ads and Meta (Facebook/Instagram) Ads
accounts by a fixed checklist, tested blind against a fictional account with a
known answer. The same agents and [playbook](paid-ads-agent-playbook.md) also cover
setup, campaign structure, QA, launch and optimization. Live work needs browser
tools that you add yourself, and every live change goes through an approved
change ledger first.

**Blind runs on the sample account** (fresh agent, only the agent file and the CSV
exports, a neutral prompt):

| Run | Recall | Precision | Strict precision | False positives | Missed |
|---|---|---|---|---|---|
| google-run-1 | 16/18 | 16/16 | 16/16 | 0 | G17, G18 |
| google-run-2 | 16/18 | 17/17 | 16/17 | 0 | G17, G18 |
| meta-run-1 | 12/12 | 14/14 | 12/14 | 0 | none |

The first lines of [google-run-1](sample-client/tallo/blind-runs/google-run-1/output.md),
unedited (two shortened with [...]):

> 1. No account bids on the value event. First Deposit is Secondary in CZ and SK and does not exist in PL. Installs are Primary everywhere, and PL counts the same install twice.
> 2. PL is broken on measurement: 655 installs in Google Ads vs 44 attributed in the MMP (about 15x), 0% EEA consent signals, and a duplicate Primary install action. [...]
> 3. SK and PL promo ads say "guaranteed return 8% a year" (an investment product) plus an iPhone prize draw. This is a restricted claim copied 1:1 between markets (guardrail 9) [...]
> 4. A former agency (Brightlane Media, contract ended 2025-12-31) still has Admin on CZ and SK.

What the numbers do and don't prove (one author wrote the checklist, the data and
the key; the two issues an outside reviewer added were missed) is in the
[sample README](sample-client/tallo/README.md#what-these-numbers-do-and-dont-show).

## Try it

```
git clone https://github.com/terezakohutova/paid-ads-agent-playbook
cd paid-ads-agent-playbook
claude
> audit the Google Ads account in sample-client/tallo/google/data/
```

The agents are already in `.claude/agents/`, so Claude Code picks them up in this
folder. Compare the result with the [answer key](sample-client/tallo/answer-key.md)
and the [blind runs](sample-client/tallo/blind-runs/). For Meta, ask for an audit of
`sample-client/tallo/meta/data/`.

## What is in the repo

| Path | What |
|---|---|
| [`.claude/agents/`](.claude/agents/) | `google-ads` and `facebook-ads`: operating summary, guardrails, Phase 0 audit checklist, output format. Audit-only by default (`Read, Grep, Glob`) |
| [`paid-ads-agent-playbook.md`](paid-ads-agent-playbook.md) | The full ruleset: entities, naming, starter pack, briefs, measurement, creative production, event priority, guardrails 1-19, budget rules, Phases 0-7 per platform, learning loop, ops layer |
| [`ads-ops/`](ads-ops/README.md) | Running the agents every week: cadence with overdue reminders, goals check-in, change ledger, automatic file versions, a language gate for ad copy |
| [`.claude/skills/ads-research-scan/`](.claude/skills/ads-research-scan/SKILL.md) | Monthly scan of changelogs, practitioner sources and GitHub, logged as hypotheses, never installed on the spot |
| [`sample-client/tallo/`](sample-client/tallo/README.md) | The fictional account as CSV exports, answer key, blind runs with input hashes, `score.py` |
| [`tests/`](tests/) | Standard-library tests for both scripts, repo integrity (links, agent frontmatter, agents in sync with the playbook and each other) and the sample (data vs. key, verbatim quotes in the scoring, the table above vs. `score.py`), on Linux, macOS and Windows in [CI](.github/workflows/tests.yml) |

Several rules come from mistakes that actually happened: a placeholder budget used
for real (guardrail 3), a banned claim copied into a third market from a second one
that already had it live (guardrail 9), a local-language token in an English naming
scheme. The playbook was extracted from a real production setup and
anonymized: company names, account IDs, internal links and people's names are
removed or replaced with placeholders.

## Using it for real

1. Read [`paid-ads-agent-playbook.md`](paid-ads-agent-playbook.md).
2. Replace `[Product]`, `[Company]`, `[Market A/B/C]` and the entity/account tables
   with your own, and point the "source of truth" bullets at wherever you keep
   campaign plans, tone of voice and naming.
3. Copy both agent files into your project. For live work, add your browser tools
   (and `Bash` for the ads-ops scripts) to `tools:` in your copy.
4. Keep the guardrails and phase checklists; delete what doesn't apply (one market
   = no multi-entity billing rules).
5. Optional: copy `ads-ops/` next to `.claude/` and merge its hooks (below).

## Running it on a schedule: what is enforced and what is procedure

| Piece | Enforced by code | Procedure only |
|---|---|---|
| Cadence (`cadence.json` + `SessionStart` hook) | Lists overdue tasks and open ledger rows at every session start | Whether anyone acts on the list |
| Goals (`goals.md`) | Nothing | Agents are told to ask when a goal is missing or older than 30 days |
| Change ledger (`ads_ops.py ledger`) | A row needs old value, new value, rollback trigger and a review date. Approval is a separate `ledger approve <id> --by <name>` with a timestamp. Status order planned > approved > done > verified > kept/rolled back, plus done > failed when a read-back does not match. `approve` is refused when the approver is the row's creator. Verified rows past their review date show in `due` | That the change in the ad account was made only after an approved row (the script never sees the account), and that the owner ran `approve` (the creator check catches accidents; anyone with a shell can pass another name) |
| File versions (`PreToolUse` hook) | Agent, skill, goals and playbook files are copied to `.versions/` before every Edit/Write; last 50 per file kept; `ads_ops.py done` versions `cadence.json` itself | Edits made through shell commands are not seen by the hook |
| Language gate (`langcheck_ads.py`) | Exit 1 on findings, exit 3 when a layer that applies did not check every text (3 wins over 1). Markets map to languages explicitly (`AT` = de-AT); a country code given as a language is refused. Meta and Google copy fields, sitelinks, callouts and paths are collected; a spec with no copy field is exit 2. Same exit codes and language tags as [copy-langcheck](https://github.com/terezakohutova/copy-langcheck) | A person still reads tone, claims and brand rules |

The tool list is the other half: with the default `Read, Grep, Glob` the agents
cannot change an account at all.

## Requirements

Claude Code for the agents. Python 3.10+ for the scripts, standard library only.
The language check optionally uses `spylls`, LibreOffice dictionaries, a local
LanguageTool server and, only with `--online`, the external Korektor service for
Czech (see its terms in [`ads-ops/README.md`](ads-ops/README.md)). Commands are
written as `python`; use `python3` where that is the name on your system (macOS,
most Linux). Run the tests with `python -m unittest discover -s tests`.

## License

MIT, see [LICENSE](LICENSE).

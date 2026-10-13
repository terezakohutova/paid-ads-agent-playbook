# Paid Ads Agent Playbook

[![CI](https://github.com/terezakohutova/paid-ads-agent-playbook/actions/workflows/tests.yml/badge.svg)](https://github.com/terezakohutova/paid-ads-agent-playbook/actions/workflows/tests.yml)

Two Claude Code subagents that run Google Ads and Meta (Facebook/Instagram) Ads
accounts by a fixed process instead of ad-hoc clicking: audit, account setup,
campaign structure, creative specs, QA, launch and ongoing optimization, across
several markets and legal entities.

- **[`google-ads`](.claude/agents/google-ads.md) and [`facebook-ads`](.claude/agents/facebook-ads.md)**: drop-in agent files. Audit-only by default (`Read, Grep, Glob`).
- **[The playbook](paid-ads-agent-playbook.md)**: the full ruleset both agents point to. Every guardrail is a mistake that actually happened once (a placeholder budget used for real, a banned claim copied into a second market, a local-language token in an English naming scheme).
- **[`ads-ops/`](ads-ops/README.md)**: the scripts and files for running the agents every week. A cadence with overdue reminders, a change ledger, automatic versions of the agent files, and a language gate for ad copy. What each one enforces and what stays procedure is spelled out below.
- **[A test account with a known answer](sample-client/tallo/README.md)**: fictional Google Ads and Meta exports with 16 and 12 planted issues (plus 2 found later by review), an answer key, and three unedited blind runs scored for precision and recall, including what the numbers don't show.

It is extracted from a real production setup and anonymized: company names,
account IDs, internal links and people's names are removed or replaced with
placeholders.

## Try it in five minutes

1. Copy `.claude/agents/google-ads.md` into your own project's `.claude/agents/`.
   No editing needed to try it; the placeholders only matter once you point it at
   your own account.
2. Ask: "audit the Google Ads account in `sample-client/tallo/google/data/`".
3. Compare with the [answer key](sample-client/tallo/answer-key.md) and with the
   [blind runs](sample-client/tallo/blind-runs/), where fresh agents with only the
   agent file and the CSVs did the same.

## What is in the repo

| Path | What |
|---|---|
| [`paid-ads-agent-playbook.md`](paid-ads-agent-playbook.md) | Shared conventions (entities, naming, starter pack, briefs, measurement, creative production, event priority, guardrails 1-16, budget rules), then Phase 0-7 for each platform, the learning loop and the ops layer |
| [`.claude/agents/`](.claude/agents/) | The two subagents: operating summary, guardrails, Phase 0 audit checklist, output format |
| [`.claude/skills/ads-research-scan/`](.claude/skills/ads-research-scan/SKILL.md) | Monthly scan of changelogs, practitioner sources and GitHub, logged as hypotheses, never installed on the spot |
| [`ads-ops/`](ads-ops/README.md) | `cadence.json`, `goals.md`, change ledger, watchlist, learnings, `ads_ops.py`, `langcheck_ads.py`, hook config |
| [`sample-client/tallo/`](sample-client/tallo/README.md) | Fictional accounts as CSV exports, answer key, blind runs, `score.py` |
| [`tests/`](tests/) | 73 standard-library tests: both scripts, repo integrity (links, agent frontmatter, agents in sync with the playbook checklists and with each other), and the sample (data vs. key, verbatim quotes in the scoring, scores vs. README), run on Linux, macOS and Windows by [CI](.github/workflows/tests.yml) |

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
| Change ledger (`ads_ops.py ledger`) | A row needs old value, new value, rollback trigger and a review date; the approval is recorded by a separate `ledger approve <id> --by <name>` with a timestamp; status order planned > approved > done > verified > kept/rolled back, with done > failed for a read-back that did not match (no `done` before approval, no `verify` before `done`); `approve` refused when the approver equals the row's recorded creator; verified rows past their review date show in `due` | That the change in the ad account was made only after an approved row (the script never sees the account), and that `approve` was run by the owner (agents are told never to run it; the creator check catches accidents, but anyone with a shell can pass another name) |
| File versions (`PreToolUse` hook) | Agent, skill, goals and playbook files are copied to `.versions/` before every Edit/Write; last 50 per file kept; `ads_ops.py done` versions `cadence.json` itself | Edits made through shell commands are not seen by the hook |
| Language gate (`langcheck_ads.py`) | Exit 1 on findings, exit 3 when any requested layer (spelling, grammar) did not run on every text, including a LanguageTool outage and Czech without `--online`; regional variants (de-AT, de-CH) checked as such; Meta and Google copy fields, sitelinks, callouts and paths collected; a spec with no copy field is exit 2 | A person still reads tone, claims and brand rules |

The tool list is the other half: with the default `Read, Grep, Glob` the agents
cannot change an account at all.

## Requirements

Claude Code for the agents. Python 3.9+ for the scripts, standard library only;
the language check optionally uses `spylls`, LibreOffice dictionaries, a local
LanguageTool server, and, only with `--online`, the external Korektor service for
Czech (see its terms in [`ads-ops/README.md`](ads-ops/README.md)). Commands are
written as `python`; use `python3` where that is the name on your system (macOS,
most Linux). Run the tests with `python -m unittest discover -s tests`.

## License

MIT, see [LICENSE](LICENSE).

# Ads ops: running the ads agents regularly and safely

The agents in `.claude/agents/` know *how* to audit, build and optimise. This folder makes them do it **on a schedule**, **ask for goals instead of guessing**, and **never make a change that can't be undone**. Everything here is plain files plus one dependency-free Python script.

| File | What |
|---|---|
| [`cadence.json`](cadence.json) | Every regular task, how often, last run |
| [`goals.md`](goals.md) | Goals, budgets, optimisation target, confirmed by the owner, stale after 30 days, plus the check-in questions |
| [`watchlist.md`](watchlist.md) | GitHub repos (MCP, optimisation, language), official changelogs, trends, industry reports, competitors |
| [`learnings.md`](learnings.md) | Outside tips logged as hypotheses with a status |
| [`change-ledger.md`](change-ledger.md) | Every live change with the old value and the way back (generated from `changes.jsonl`) |
| `snapshots/` | Exports of account state before audits and bigger changes (`YYYYMMDD-<channel>-<account>/`) |
| [`ads_ops.py`](ads_ops.py) | `due`, `done`, `tasks`, `ledger ...`, `snapshot`, `versions`, `restore`, `hook-snapshot` |
| [`langcheck_ads.py`](langcheck_ads.py) | Spelling and grammar gate for ad copy, by language or market |
| [`settings.hooks.example.json`](settings.hooks.example.json) | The two Claude Code hooks to merge into your `.claude/settings.json` |

## 1. How "regularly" actually happens
- **SessionStart hook** runs `ads_ops.py due --quiet`: whenever a Claude Code session starts and something in `cadence.json` is overdue (or a ledger change still waits for evaluation), the session sees one line and **offers it to the owner in one sentence**. Nothing live starts without their yes and their logged-in browser.
- **Optional weekly cloud/scheduled routine ("radar")**: a read-only web + GitHub scan over `watchlist.md` that sends the owner one short digest (chat DM or e-mail). It cannot see the ad accounts and never installs or connects anything. Task `radar-import` turns the digest into rows in `learnings.md` after checking each item at the source.
- After a task: `python -I ads-ops/ads_ops.py done <task-id> --note "..."`.

| Every | Task |
|---|---|
| 7 days | `meta-weekly-check`, `google-weekly-check`, `measurement-weekly`, `competitor-watch`, `radar-import` |
| 14 days | `creative-refresh-check` |
| 30 days | `goals-checkin` (asks the owner), `meta-full-audit`, `google-full-audit`, `measurement-audit`, `channel-economics`, `ads-research-scan`, `agent-file-review` |
| 90 days | `access-security-audit` |

## 2. Asking for inputs and goals
- Read `goals.md` before every task. **If it is older than 30 days, or the task needs a number that is missing (target cost per value event, budget, freeze window), ask first**: one consolidated message, grouped by who answers.
- Answers go into the `goals.md` answer log with the date. The agent never turns a missing goal into its own default.

## 3. Safeguards (on top of the guardrails in each agent file)
1. **Read-only by default.** Weekly checks, audits, research and scheduled routines never change an account. A change is a separate step with the owner's explicit yes.
2. **No change without an approved ledger row first.** The agent writes the row (`ledger add`): old value read from the UI, new value, why, **rollback trigger** and **`--review-by` date**; the script refuses a row without them. The owner approves it in their own terminal with `ledger approve <id> --by <name>`, which records the name and a timestamp; agents are instructed never to run `approve`. The script then enforces the order planned > approved > done > verified > kept / rolled_back: `ledger done` is refused before an approval, `ledger verify` before `done`, `keep`/`rolled-back` before `verify`; `ledger cancel` closes a row that will not happen. A `done` row whose read-back does not show the new value is marked `ledger failed <id>`; from `failed` (or straight from `done`) it can be `rolled-back`, or cancelled if it never applied. The row records who wrote it (`created_by`, from the `ADS_OPS_ACTOR` environment variable or `--by` on `add`), and `approve` is refused when the approver's name, or the `ADS_OPS_ACTOR` of the shell running it, equals that creator. Verified rows past their review date are listed by `due` (and the SessionStart line) until someone keeps or rolls them back.
   **What this does not enforce:** the script never sees the ad account, so it cannot stop a change made in the UI without a row, and it cannot prove the owner ran `approve` (anyone with a shell can run it under another name, or edit `changes.jsonl`). The creator check is a guard against accidents, not against a determined agent. Those parts are procedure, backed by the agent instructions and by leaving the agents without account write access unless you add it.
3. **Snapshot before bigger changes and before every audit**: Google CSV export of campaigns/ad groups/assets, Meta export from Ads Manager, into `snapshots/`.
4. **Limits per step:** Meta budget max +-20 % per ad set per 3-4 days, Google max ~20 % per 48-72 h; never over the ceilings in `goals.md`; never below the learning threshold, pause instead of starving.
5. **Pause, never delete.** Deleting campaigns, ads, assets or someone else's drafts is irreversible.
6. **Read back after reload**, then `ledger verify`. A success toast or a toggle proves nothing (some UIs silently drop writes).
7. **Before a change, check the platform history** (Google Change history, Meta Activity history): if someone changed the object since the snapshot, stop and report.
8. **Kill switch = proposal, not action.** Daily spend >130 % of plan, 48 h without attribution data, a policy flag or a cost per value event over the rollback trigger: the agent reports it with a ready rollback plan (`ledger rollback <id>`) and waits for a yes. Unattended routines never pause or start anything.
9. **Copy gate before upload:** compliance rules for your vertical, creative QA and **`langcheck_ads.py`** (exit 1 or 3 = not uploaded). Then a human look.
10. **No new tool without a decision:** GitHub repos, MCP servers, plugins and CRM connections are `decide` rows for the owner. Official read-only MCPs first; third-party hosted MCPs that see account data are a no in a regulated business.
11. **Auto-apply recommendations stay off** (Google, set from the MCC); Meta's automatic creative enhancements only when the owner agreed.

## 4. Versions and going back
- **Ad accounts:** the ledger keeps every old value; `ads_ops.py ledger rollback <id>` prints the exact steps back (a rollback is a live change too, so it needs a yes and its own ledger row). Google's Change history can undo some changes; Meta's Activity history shows the old value but has no undo, which is why the ledger exists.
- **Agent files, skills, goals, playbooks, status files:** a PreToolUse hook copies the file to `.versions/<path>/<timestamp>` before every Edit/Write (only when the content changed since the last version). `ads_ops.py versions <file>` lists them, `ads_ops.py restore <file> <version>` brings one back (the current content is versioned first). Which files count is the `PROTECTED_DEFAULT` list in the script, or a `"protected"` list of regexes in `cadence.json`. Only the newest 50 versions per file are kept (`"versions_keep"` in `cadence.json`, or the `ADS_OPS_VERSIONS_KEEP` environment variable).
- **The hook only sees Claude Code's Edit/Write/NotebookEdit tools.** A file changed through a shell command (`sed`, a script, `git checkout`) is not versioned. `ads_ops.py done` therefore versions `cadence.json` itself before rewriting it; anything else you change from a shell, snapshot first with `ads_ops.py snapshot <file>`.
- **Concurrent sessions:** ledger and cadence writes take a lock file (`ads-ops/.ads_ops.lock`, cleared automatically if left by a crash after 2 minutes) and are written to a temp file and renamed into place, so two sessions never get the same ledger id or a half-written file.
- **Learnings:** rows are never deleted, only re-statused (`rejected <date> why`).

## 5. Language
Every ad text in every market goes through `python -I ads-ops/langcheck_ads.py copy.json` (or `--lang de "text" ...`, `--market AT "text" ...`). It uses the same layers, exit codes and language tags as [copy-langcheck](https://github.com/terezakohutova/copy-langcheck), which also reads HTML, Markdown and plain text and runs as a GitHub Action; this script adds the ad-platform fields and market codes.

- **Exit codes:** 0 clean and every layer that applies checked every text; 1 findings, with every layer complete; 2 usage (an unknown language, market or `--layers` name, or a spec file with no recognised copy field; the message lists the keys it did see); **3 not fully checked**: a layer that applies did not run (no dictionary, LanguageTool unreachable) or failed part way (a LanguageTool server that answers the first text and then dies). **3 wins over 1**: findings are still printed, but an incomplete check never looks like "only findings". Coverage is tracked per text and per layer, and the unchecked texts are listed. `--allow-unchecked` is a deliberate dry run (1 for findings, otherwise 0).
- **Layers that apply:** Hunspell (spelling) always; LanguageTool (grammar) for every language it has a module for; Korektor (Czech spelling and diacritics in context, not grammar) only with `--online`. LanguageTool has no Czech and no Hungarian, so those are checked for spelling only and the run says so. For the other languages LanguageTool is the only grammar layer: when it is down, the run exits 3. `--layers hunspell` checks spelling only on purpose.
- **Language or market:** `--lang` and a JSON `lang`/`language` key take a language tag (`cs`, `de-AT`, `en-US`...). `--market` and a JSON `market` key take a country, mapped explicitly: CZ cs, SK sk, PL pl, DE de, AT de-AT, CH de-CH, GB/UK/IE en-GB, US en-US, ES es, FR fr, IT it, HU hu, NL nl, PT pt, BR pt-BR. A country code given as a language (`--lang cz`, `--lang uk`) is exit 2 with a hint, not a guess. In a file, `lang` wins over `market`.
- **Regional variants:** `de-AT`/`de-CH` (markets AT/CH) are checked as Austrian and Swiss German with their own dictionaries (`de_AT_frami`, `de_CH_frami`) and LanguageTool codes; `en-US` and `pt-BR` likewise use `en_US` and `pt_BR`.
- **ALL-CAPS words** are checked like any other word (looked up as written, in lower case and capitalised). An acronym that is fine on purpose goes in `langcheck-ignore.txt`.
- **Fields collected from a spec file:** `headline(s)`, `description(s)`, `long_headline(s)`, `primary_text(s)`, `cta`, `text`, `copy`, `sub`, `subline`, and the Meta Marketing API names `message` (primary text), `body`/`bodies`, `title`/`titles`, `link_description`, plus `name` inside `link_data`, `child_attachments` or `template_data` (there it is the headline; elsewhere `name` is an internal ad name and is skipped). Google text assets: `sitelink_text`/`link_text` with `description1`/`description2` (and the legacy `line1`/`line2`), `callout(s)`/`callout_text`, display URL `path1`/`path2`, `business_name`, `promotion_target`, and `values` inside a `structured_snippet`.
- **Korektor is opt-in** because it sends the ad text to an external server (LINDAT/CLARIAH-CZ). Per the service pages at the time of writing, its models are licensed CC BY-NC-SA, so commercial use needs permission from the authors, and submitted text may be logged by the service. Check the current terms before sending client copy. Without `--online`, Czech is checked by Hunspell alone.
- Tools do not judge tone, claims or brand rules: the agent still reads every text against the tone-of-voice doc.

## Setup
1. Copy `ads-ops/` into your project root (next to `.claude/`).
2. Merge `settings.hooks.example.json` into `.claude/settings.json` (or `settings.local.json`).
3. Fill in `goals.md` and the competitor table in `watchlist.md`, or let the first `goals-checkin` ask for them.
4. Optional, for the language check: `pip install spylls`, download the `.aff`/`.dic` files you need from `LibreOffice/dictionaries` into a folder and point `LANGTOOLS_DICTS` at it; run a LanguageTool server (`LT_URL`, default `http://localhost:8081/v2/check`).
5. Add `.versions/` and `ads-ops/snapshots/*/` to `.gitignore` if the project is a public repo: account exports do not belong on GitHub.
6. The commands use `python`; where your system calls it `python3` (macOS, most Linux), change the two hook commands too. Python 3.10+, standard library only.

## Tests
`python -m unittest discover -s tests` from the repo root. The tests run both scripts as subprocesses against a throwaway copy of this folder (cadence, every ledger path including refusals and out-of-order transitions, eight concurrent `ledger add` processes, a stale lock, version collisions within one second, retention, restore inside and outside the project, the hook on bad input) and the language gate against local stand-ins for the LanguageTool and Korektor APIs, including servers that fail after the first text, so they need no network and no dictionaries.

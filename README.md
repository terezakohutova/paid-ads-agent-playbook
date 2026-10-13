# Paid Ads Agent Playbook

Two runnable Claude Code subagents, [`.claude/agents/google-ads.md`](./.claude/agents/google-ads.md)
and [`.claude/agents/facebook-ads.md`](./.claude/agents/facebook-ads.md), for
running Google Ads and Meta (Facebook/Instagram) Ads accounts across multiple
markets/legal entities: audit, account setup, campaign structure, creative
specs, QA, launch, and ongoing optimization.

It replaces "click around and learn as you go" with a fixed, repeatable
process, because in practice the same mistakes (wrong budget pasted in, wrong
naming, a bad line item copy-pasted between markets) kept recurring until they
were written down explicitly.

**This is a generic template**, extracted from a real production setup and
anonymized: every company name, account ID, internal link, and person's name
has been stripped or replaced with a placeholder.

## Try it in five minutes

1. Copy `.claude/agents/google-ads.md` into your own project's
   `.claude/agents/` (no editing required to try it, the placeholders only
   matter once you point it at your own account).
2. Ask it to audit [`sample-client/vela-invest/data/`](./sample-client/vela-invest/data/),
   a fictional account with seven planted issues.
3. Compare what it finds against [`sample-client/vela-invest/audit-output.md`](./sample-client/vela-invest/audit-output.md),
   the output of that exact audit, verified by an independent blind run,
   each finding tied back to the specific guardrail that catches it.

## Using this for real

1. Read [`paid-ads-agent-playbook.md`](./paid-ads-agent-playbook.md), the
   canonical ruleset both agents point back to.
2. Replace `[Product]`, `[Company]`, `[Market A/B/C]`, and the entity/account
   tables with your own.
3. Replace the "source of truth" bullets with wherever you actually keep
   campaign plans, tone-of-voice docs, and naming conventions.
4. Copy `.claude/agents/google-ads.md` and `.claude/agents/facebook-ads.md`
   into your own project.
5. Keep the guardrails and phase checklists. They encode mistakes that are
   easy to repeat regardless of company (placeholder budgets, live-launching
   by accident, copying banned copy between markets, over-scoped
   permissions). Delete whatever doesn't apply to your setup.

## Running it on a schedule, safely

[`ads-ops/`](./ads-ops/README.md) turns the two agents into something that runs
regularly without drifting or breaking things:

- `cadence.json` + a `SessionStart` hook: weekly checks, monthly audits of each
  account and of measurement, a monthly research scan, a quarterly access audit.
  The session lists what is overdue and offers it, nothing live runs on its own.
- `goals.md`: goals, budget ceilings and the optimisation target, confirmed by the
  owner and treated as stale after 30 days, so the agents ask instead of guessing.
- `ads_ops.py ledger`: every live change is written down first with the old
  value, the approval and a rollback trigger, and `ledger rollback <id>` prints
  the way back.
- A `PreToolUse` hook keeps a version of every agent, skill and goals file before
  each edit, restorable with `ads_ops.py restore`.
- `langcheck_ads.py`: Hunspell + LanguageTool (+ Korektor for Czech) as a gate
  before any ad copy is uploaded.
- `watchlist.md` and the `ads-research-scan` skill
  ([`.claude/skills/ads-research-scan/`](./.claude/skills/ads-research-scan/SKILL.md)):
  official MCPs, optimisation and language repos, changelogs, trends and
  competitors, logged as hypotheses in `learnings.md`, never installed on the spot.

## License

MIT, see [LICENSE](./LICENSE).

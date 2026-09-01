# Paid Ads Agent Playbook

A pair of reusable Claude Code subagent definitions for running Google Ads and
Meta (Facebook/Instagram) Ads accounts across multiple markets/legal entities:
audit, account setup, campaign structure, creative specs, QA, launch, and
ongoing optimization.

It replaces "click around and learn as you go" with a fixed, repeatable
process, because in practice the same mistakes (wrong budget pasted in, wrong
naming, a bad line item copy-pasted between markets) kept recurring until they
were written down explicitly.

**This is a generic template**, extracted from a real production setup and
anonymized: every company name, account ID, internal link, and person's name
has been stripped or replaced with a placeholder.

## See it applied

[`sample-client/vela-invest/`](./sample-client/vela-invest/) runs the Phase 0
audit checklist against a fictional account with six planted issues (a
conversion action stuck on Secondary, a compliance claim copied between
markets, an attribution gap on a new sub-account) and shows the actual
findings, each one tied back to the specific guardrail that catches it. Read
this before the full playbook if you want to see what "audit output" looks
like rather than just what the checklist says.

## Using this

1. Read [`paid-ads-agent-playbook.md`](./paid-ads-agent-playbook.md).
2. Replace `[Product]`, `[Company]`, `[Market A/B/C]`, and the entity/account
   tables with your own.
3. Replace the "source of truth" bullets with wherever you actually keep
   campaign plans, tone-of-voice docs, and naming conventions.
4. Drop the two agent definitions into `.claude/agents/google-ads.md` and
   `.claude/agents/facebook-ads.md` in your own project, or use the file as a
   standalone reference doc.
5. Keep the guardrails and phase checklists. They encode mistakes that are
   easy to repeat regardless of company (placeholder budgets, live-launching
   by accident, copying banned copy between markets, over-scoped
   permissions). Delete whatever doesn't apply to your setup.

## License

MIT, see [LICENSE](./LICENSE).

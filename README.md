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
   the recorded output of that exact audit, each finding tied back to the
   specific guardrail that catches it.

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

## License

MIT, see [LICENSE](./LICENSE).

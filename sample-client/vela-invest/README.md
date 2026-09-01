# Sample client: Vela Invest

A fictional micro-investing app expanding from CZ into SK and PL, used here
to show the Phase 0 audit checklist from
[`paid-ads-agent-playbook.md`](../../paid-ads-agent-playbook.md) actually
running against an account, instead of just describing what it would catch.

- [`data/`](data/) - the account as raw exports (`campaigns.csv`,
  `conversion-actions.csv`, `negative-keyword-lists.csv`,
  `change-history.csv`, `attribution-check.csv`). This is what the
  `google-ads` agent actually reads.
- [`account-snapshot.md`](account-snapshot.md) - the same facts as
  `data/`, in one readable file, for anyone who wants to see the input
  without opening five CSVs.
- [`audit-output.md`](audit-output.md) - the Phase 0 checklist filled in
  against that data, each finding tied back to the specific guardrail or
  rule in the main playbook that catches it.

Every issue in the data was planted to match a failure mode the main
playbook already documents (a promoted-vs-secondary conversion action, a
compliance claim copied between markets, an attribution gap on a new
sub-account). This exists to show those rules catching something, not to
introduce new ones.

## Try it yourself

1. Copy [`.claude/agents/google-ads.md`](../../.claude/agents/google-ads.md)
   into your own project's `.claude/agents/`.
2. Ask it to audit this folder: "audit the Google Ads account in
   `sample-client/vela-invest/data/`."
3. Compare what it finds against [`audit-output.md`](audit-output.md). It
   should catch the same seven issues, the account setup above didn't
   change, only whether a person or an agent is reading it.

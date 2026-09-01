# Sample client: Vela Invest

A fictional micro-investing app expanding from CZ into SK and PL, used here
to show the Phase 0 audit checklist from
[`paid-ads-agent-playbook.md`](../../paid-ads-agent-playbook.md) actually
running against an account, instead of just describing what it would catch.

- [`account-snapshot.md`](account-snapshot.md) - the account as the audit
  found it: campaigns, conversion actions, change history. This is input,
  not commentary - nothing in this file is flagged yet.
- [`audit-output.md`](audit-output.md) - the Phase 0 checklist filled in
  against that snapshot, each finding tied back to the specific guardrail or
  rule in the main playbook that catches it.

Every issue in the snapshot was planted to match a failure mode the main
playbook already documents (a promoted-vs-secondary conversion action, a
compliance claim copied between markets, an attribution gap on a new
sub-account). This exists to show those rules catching something, not to
introduce new ones.

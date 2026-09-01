# Vela Invest - Phase 0 audit output

Run against [`account-snapshot.md`](account-snapshot.md) using the Phase 0
checklist from
[`paid-ads-agent-playbook.md`](../../paid-ads-agent-playbook.md#phase-0--audit-an-existinginherited-account).
Each finding is marked confirmed, assumed, or blocked, per the playbook's
own confidence convention, and cites the specific rule that catches it.

## Findings

**Conversion actions (category, count, attribution, primary vs. secondary)**
FAIL, confirmed. `Registration Complete`, `Account Link`, and `First
Deposit` all sit as Secondary. Per the playbook's attribution note, a new
conversion action defaults to secondary until explicitly promoted, and
nobody promoted these. Only `App Install` currently counts toward account
goals, so every optimization decision on this account so far has been
running on the wrong signal.

**No duplicate counting of the same conversion**
Assumed pass. Single count-type per action, nothing obviously duplicated in
the snapshot.

**Brand safety / PMax brand exclusions**
Not applicable. No PMax campaign is live yet, flagged instead for Phase 3
setup.

**Shared negative keyword lists exist and are attached**
FAIL, confirmed. "Vela - Master Negatives" exists but is attached to one of
six campaigns. Five campaigns are running with zero shared negatives.

**Search terms report**
FAIL, confirmed. `CZ_SEARCH_acq_generic_2409` has not been touched since
September 2024.

**Access/roles**
Blocked, not in snapshot scope.

**Copy on old/un-rebuilt campaigns checked separately from structure**
FAIL. Same campaign as above. Sixteen months untouched is exactly the case
this rule exists for; the copy has never been checked independently of the
structure.

**Compliance check**
FAIL, confirmed, two campaigns. `SK_APP_acq_giveaway_2512` uses "guaranteed
8% return," a banned claim for a regulated vertical under guardrail 4.
`PL_APP_acq_giveaway_2601` copied that same line into Polish. Guardrail 9
exists for exactly this pattern: a banned claim inherited because the
sibling market's approval was treated as clearance instead of a fresh
compliance check.

**English asset names**
FAIL, one instance. `PL_APP_acq_ABtest_dowod_spoleczny_2601` has a
Polish-language headline where the naming convention requires English asset
names regardless of market language.

**Change history reviewed**
FLAG. The PL giveaway budget increase from EUR 40/day to EUR 90/day on
2026-01-14 has no approver on record. Every budget change is supposed to
state an approver and a rollback trigger; this one has neither.

**Attribution cross-check**
FAIL, confirmed. Vela's own dashboard shows 4 PL installs (7 day) against
the ad platform's 61 for the same market and period, a roughly 15x gap.
This matches the playbook's misattribution note precisely: installs land as
"Organic" when the attribution tool's link is not shared into every
sub-account. PL is a new sub-account, created January 2026, so check first
whether the tracking link was ever shared into it.

## What this account needs before anything else

1. Promote `Registration Complete`, `Account Link`, and `First Deposit` to
   primary conversion actions. Nothing downstream should be judged on
   installs alone.
2. Share the attribution tool's tracking link into the PL sub-account and
   re-pull the 7-day numbers before trusting any PL performance read.
3. Remove the banned claim from both giveaway campaigns. Per guardrail 4,
   this is a stop, not a flag-and-continue.
4. Attach the master negative list to the five campaigns missing it.
5. Rebuild or explicitly sunset `CZ_SEARCH_acq_generic_2409`. It has been
   running unexamined for sixteen months.

Nothing here proposes a budget change or a launch. Per the playbook, that
is as far as an audit goes without separate sign-off.

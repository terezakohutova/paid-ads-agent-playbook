# Vela Invest - Phase 0 audit output

Run against [`data/`](data/) using the Phase 0 checklist from
[`.claude/agents/google-ads.md`](../../.claude/agents/google-ads.md). Each
finding is marked FAIL, pass, or blocked, per that checklist's own
confidence convention, and cites the specific rule that catches it.

This output was independently reproduced by handing a fresh Claude Code
agent only the `google-ads.md` instructions and the `data/` folder, no
sight of this file. Two things changed as a result of that check: two
checklist items that used to appear here (brand safety/PMax, access and
roles) were removed because they are not part of the condensed checklist
in `google-ads.md`, and the search-terms-report finding was corrected to
"blocked" because no such file exists in `data/`. Everything else below
matched the independent run.

## Findings

**Conversion actions (category, count setting, attribution model, primary
vs. secondary)**
FAIL, high confidence on the primary/secondary read; category and
attribution model are blocked, `conversion-actions.csv` has no such
columns. The actual value event, `First Deposit (Activation)`, sits as
Secondary in CZ/SK and does not exist as a conversion action in PL at
all. Per the playbook's event-priority rule, a value event on Secondary
is a fail, not a detail, this account is currently optimizing on upstream
proxies (Registration, Account Link), the exact mistake the playbook
describes as already having been made and corrected once. Secondary risk
worth flagging: `App Install`'s count setting is `Every` rather than
`One`, unusual for an install-type action and worth verifying it is not
inflating install counts.

**No duplicate counting of the same conversion**
Blocked. The export has one row per action with no cross-tool tagging
data (for example, whether the same event fires from both a website tag
and an app SDK), so this cannot be confirmed or ruled out from what is
here.

**Shared negative keyword lists exist and are attached**
FAIL, confirmed. "Vela - Master Negatives" exists but is attached to one
of six campaigns. The account's other Search campaign,
`CZ_SEARCH_acq_generic_2409`, has no negative list attached at all.

**Search terms report**
Blocked. No search-terms-report file exists in `data/`. Not answerable
from what was provided, needs a real export before this item can close.

**Copy on old/un-rebuilt campaigns checked separately from structure**
FAIL, medium confidence. `CZ_SEARCH_acq_generic_2409` is noted "created
2024-09; not touched since," roughly sixteen months dormant, exactly the
case this rule exists for. No copy text for this campaign is in the
export and nothing indicates it has ever had an independent copy review.

**Compliance check**
FAIL, confirmed, two campaigns. `SK_APP_acq_giveaway_2512` uses "guaranteed
8% return," a banned claim for a regulated vertical under guardrail 4.
`PL_APP_acq_giveaway_2601` copied that same line into Polish, live and
spending. Guardrail 9 exists for exactly this pattern: the PL duplicate
is not a lesser problem than the SK original, it is a second, independent
live violation.

**English asset names**
FAIL, confirmed, two breaks on one campaign. `PL_APP_acq_ABtest_dowod_spoleczny_2601`
uses "dowod_spoleczny" (Polish for "social proof") in the campaign name
itself, where the naming convention already established by its sibling
campaign (`CZ_APP_acq_ABtest_social_proof_2601`) is English, and its own
notes confirm one asset headline is also named in Polish.

**Change history reviewed**
FAIL. The only change-history entry in the export is the PL giveaway
budget increase from EUR 40/day to EUR 90/day on 2026-01-14, with no
approver on record and no rollback trigger anywhere. No change-history
rows exist for the other five campaigns either, that is unscored, not a
clean pass, genuinely unknown whether no changes occurred or the export
is incomplete.

**Attribution cross-check**
FAIL, confirmed for PL; CZ and SK are blocked, not present in
`attribution-check.csv`. The platform reports 61 PL installs over the
last 7 days against 4 from Vela's own attribution tool, a roughly 15x
gap, squarely in the range the checklist treats as a sharing gap rather
than real performance. Per the misattribution note, check first whether
the tracking link was ever shared into the PL sub-account, created
January 2026, before trusting any PL read.

## What this account needs before anything else

1. Pull the "guaranteed return" claim live in two markets
   (`SK_APP_acq_giveaway_2512`, `PL_APP_acq_giveaway_2601`). Highest
   severity, it is a live compliance exposure spending in both markets
   right now.
2. Share the attribution tool's tracking link into the PL sub-account and
   re-pull the 7-day numbers before trusting any PL performance read;
   confirm CZ/SK links too since no data was provided to check them.
3. Build `First Deposit (Activation)` as a real, promoted conversion
   action in every market, including PL where it does not exist yet.
   Every campaign is currently optimizing on upstream proxies, not actual
   value.
4. Get retroactive sign-off on, or reverse, the unapproved PL budget
   increase. No approver, no rollback trigger on record, and it is the
   same campaign carrying the compliance violation above.
5. Attach the master negative list to `CZ_SEARCH_acq_generic_2409`.
6. Fix the naming break on `PL_APP_acq_ABtest_dowod_spoleczny_2601`, both
   the campaign name and one asset name. Low severity, cheap to fix.
7. Rebuild or explicitly sunset `CZ_SEARCH_acq_generic_2409` with an
   independent copy review. It has been running unexamined for roughly
   sixteen months.
8. Get a complete export before signing off the rest of the account: no
   search-terms data, no change history for five of six campaigns, and no
   CZ/SK attribution rows were provided, those items are blocked, not
   passed.

Nothing here proposes a budget change or a launch. Per the playbook, that
is as far as an audit goes without separate sign-off.

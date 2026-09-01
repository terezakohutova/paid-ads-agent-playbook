# Vela Invest - Google Ads account snapshot (pre-audit)

Fictional client for this playbook. Vela is a micro-investing app expanding
across CZ, SK, and PL. This is what the audit found in the account before
Phase 0 was run - a plain input file, not itself a commentary.

## Account structure
- Manager account: Vela MCC
- Sub-accounts: CZ (linked), SK (linked), PL (linked, created 2026-01)

## Conversion actions
| Action | Status | Count setting |
|---|---|---|
| App Install | Primary | Every |
| Registration Complete | Secondary | One |
| Account Link (bank) | Secondary | One |
| First Deposit (Activation) | Secondary in CZ/SK, not present in PL | One |

## Campaigns
| Campaign | Type | Budget | Status | Notes |
|---|---|---|---|---|
| CZ_SEARCH_acq_brandterms_2601 | Search | EUR 25/day | Live | - |
| CZ_APP_acq_ABtest_social_proof_2601 | App | EUR 140/day | Live | - |
| CZ_SEARCH_acq_generic_2409 | Search | EUR 80/day | Live | Created Sep 2024, not touched since |
| SK_APP_acq_giveaway_2512 | App | EUR 90/day | Live | Headline: "Vyhraj a ziskej garantovany vynos 8 %" ("win a guaranteed 8% return") |
| PL_APP_acq_giveaway_2601 | App | EUR 90/day | Live | Copy duplicated from SK_APP_acq_giveaway_2512, same guaranteed-return line, translated to Polish |
| PL_APP_acq_ABtest_dowod_spoleczny_2601 | App | EUR 60/day | Live | One asset headline named "Dowod spoleczny wariant B" (Polish, not English) |

## Negative keywords
Shared list "Vela - Master Negatives" exists, attached to
`CZ_SEARCH_acq_brandterms_2601` only.

## PMax
None currently running.

## Change history (last 30 days)
- 2026-01-14: PL_APP_acq_giveaway_2601 budget raised from EUR 40/day to EUR
  90/day. No approver noted in the change log.

## Attribution cross-check
Vela's in-house attribution dashboard shows 4 installs for PL over the last
7 days. The ads platform reports 61 installs for the same market and period.

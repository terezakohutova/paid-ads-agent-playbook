# Answer key: Tallo sample accounts

What was planted in [`google/data/`](google/data/) and [`meta/data/`](meta/data/),
written together with the data and fixed before any blind run was scored. The
machine-readable version is [`answer-key.json`](answer-key.json); the ids below are
the ones the scoring files use.

How the sample is built: the exports look like what you would pull from the
platforms plus two inputs a brief normally supplies (`client-facts.csv`, the team's
own `change-ledger.csv`). No notes column says what is wrong. Most issues only show up
when two files are joined: a budget change in the platform history with no row in
the ledger, an old ad against the current price, an admin against the date the
agency contract ended.

## Google Ads (16 planted, 2 found by review)

| ID | Checklist item | What is wrong | Where it shows |
|---|---|---|---|
| G1 | Conversion actions | Nothing bids on First Deposit, the value event: the CZ and SK App campaigns run Target CPI, which optimises for installs whatever First Deposit's Primary/Secondary status; the lever is the campaign bidding (tCPA on First Deposit as an in-app action, or tROAS). CZ Search/PMax bid on Primary Web sign-up. *Corrected 2026-10-13, see below* | `campaigns.csv`, `conversion-actions.csv`, `client-facts.csv` |
| G2 | Conversion actions | PL has no First Deposit action | `conversion-actions.csv` |
| G3 | Duplicate counting | PL: `Install (MMP)` and `first_open (Firebase)` both Primary | `conversion-actions.csv` |
| G4 | Consent signals | PL app conversions carry EEA consent on 0 % of conversions | `account-settings.csv` |
| G5 | Shared negative lists | CZ list attached to the brand campaign only | `negative-keyword-lists.csv` |
| G6 | Search terms | Mortgage, bitcoin and instant-loan queries with spend and zero conversions | `search-terms.csv` |
| G7 | PMax brand exclusions | None set; brand queries in PMax insights | `campaigns.csv`, `search-terms.csv` |
| G8 | Auto-apply | On in PL, and it has already changed a budget and added broad keywords | `account-settings.csv`, `change-history.csv` |
| G9 | Change history | SK 35 to 70 and PL 60 to 90 with no ledger row or approver | `change-history.csv` vs `change-ledger.csv` |
| G10 | Access and roles | Former agency still Admin on CZ and SK | `account-access.csv`, `client-facts.csv` |
| G11 | Copy on old campaigns | 2023 campaign promises "no fees, ever"; current price EUR 1.99/month | `ads.csv`, `client-facts.csv` |
| G12 | Compliance | "Guaranteed 8 % a year" on an investment product (SK) | `ads.csv` |
| G13 | Compliance | The same claim copied into PL (guardrail 9) | `ads.csv` |
| G14 | Compliance | The prize draw copied from SK into PL (guardrail 10) | `ads.csv` |
| G15 | Attribution cross-check | PL 655 vs 44, MMP organic up 720 to 1,310 | `attribution-check.csv` |
| G16 | Asset names | Polish token `dowod_spoleczny` (hygiene, low severity) | `campaigns.csv`, `ads.csv` |
| G17 | Budget vs. target | *Found by review, not planted.* All four enabled Target CPI App campaigns have a daily budget under Google's ~50x target CPI (CZ 150 vs 190, SK 70 vs 160, PL 90 and 50 vs 145) | `campaigns.csv` rows 4, 8, 10, 11 |
| G18 | Currency vs. market | *Found by review, not planted.* The CZ brand ad prices the product in euro ("1,99 € měsíčně") in a CZK market | `ads.csv` row 3 |

Clean controls (should be pass or blocked, never FAIL): enhanced conversions in CZ,
CZ/SK consent and attribution, linked accounts, the paused 2024 giveaway campaign,
and the CZ budget change that has an approved ledger row made before the change.

## Meta (12 planted)

| ID | Checklist item | What is wrong | Where it shows |
|---|---|---|---|
| M1 | Roles | Tallo CZ portfolio has one admin | `people.csv` |
| M2 | Partner access | Former agency has full control of Tallo CZ | `partners.csv`, `client-facts.csv` |
| M3 | Risky combinations | The CZ entity's card pays the PL entity's account | `payment-methods.csv`, `business-portfolios.csv` |
| M4 | Measurement | Installs arrive from both the SDK and the MMP | `events.csv` |
| M5 | Measurement | `first_deposit` not mapped; all ad sets optimize on installs | `events.csv`, `ad-sets.csv` |
| M6 | Structure / learning | SK: six EUR 8/day ad sets, all Learning limited | `ad-sets.csv` |
| M7 | Frequency and fatigue | CZ winter ad set at frequency 5.6 | `ad-sets.csv` |
| M8 | Audience exclusions | PL promo Android excludes nobody while the other ad sets exclude existing users. It is an Advantage+ app install campaign, where Meta handles install exclusion itself, so this is a low-severity consistency check, not confirmed waste. *Reworded 2026-10-13* | `ad-sets.csv` |
| M9 | Compliance | "Guaranteed 8 % a year" in the PL ad | `ads.csv` |
| M10 | Change history | PL budget 40 to 100 with no ledger row | `activity-history.csv` vs `change-ledger.csv` |
| M11 | Attribution settings | One ad set on 1-day click, the rest on 7-day click | `ad-sets.csv` |
| M12 | Asset names | Polish token `dowod_spoleczny` (hygiene) | `ad-sets.csv` |

Clean controls: PL's two admins, the employee-type system user, brand safety
settings, business verification, 2FA, and the CZ budget change with its ledger row.

## Corrections after an outside review (2026-10-13)

- **G1 was keyed on the wrong lever.** The original key said the problem was First
  Deposit being Secondary. A Target CPI App campaign optimises for installs whatever
  the goal status of a deeper action; to bid on First Deposit the campaign needs tCPA
  on that in-app action (or tROAS). The issue (nothing bids on the value event) is
  unchanged, the mechanism and the fix are. Both Google runs state that nothing bids
  on First Deposit and are still counted as finding G1, but both blame the goal
  status, so the fix they point at would not have changed the App campaigns.
- **G17 and G18 were not planted.** The reviewer found them in the data. They are
  in the key now, so both Google runs miss them; the runs were not repeated.
- **M8 was overstated.** Reworded as a low-severity consistency check. The Meta run
  marked it FAIL, high; it still matches the planted item but over-rates it.
- **meta-run-1 counted M6 twice** for precision; it is counted once now.
- **The re-score changed no run output.** Before it, the results table read 16/16
  recall for both Google runs and 15/15 (strict 13/15) precision for the Meta run.

## Agent file versions

The runs used the agent files from commit `6625e0a`. The files were edited later
(wording, the language-gate step, a corrected Target CPI note). The exact versions
the runs read are in [`blind-runs/agent-files/`](blind-runs/agent-files/), and a
test checks their sha256 against each `run.json`.

## Flaws in the sample itself, found by the runs

- **The "clean" CZ ledger row is not clean.** Its rollback trigger is cost per First
  Deposit above EUR 95; the campaign cost EUR 4,390 against 38 First Deposits in the
  whole CZ account, so the cost is at least EUR 115 and "kept" is doubtful. Google
  run 2 marked it FAIL, run 1 raised it as a question. Scored as a valid extra, not a
  false positive. Left in the data as it is, because the runs were made against it.
- **`PL_APP_acq_dowod_spoleczny_2509` reports 451 conversions** that the conversion
  actions do not explain. An authoring slip; Google run 2 noticed it and marked it
  blocked.

## What a correct audit recommends first (Google)

1. Treat the guaranteed-return and prize-draw ads in SK and PL as a compliance
   problem for the owner and legal: a pause is a proposal with a ledger row, not an
   action the agent takes.
2. Fix PL measurement (MMP link or sharing for the PL sub-account, consent
   parameters, one install action) before reading any PL number.
3. Turn PL auto-apply off and put the unrecorded budget changes in front of the
   owner; remove the former agency's access.
4. **The optimisation event is the owner's decision, not a fix.** First Deposit
   volume is CZ 38, SK 9, PL none in 30 days, far below what bidding needs per
   campaign. For the App campaigns the switch is in the bidding (Target CPI to tCPA
   on First Deposit, in practice a new campaign), not the Primary status, and it
   resets learning; the budgets are already under Google's minimum for the current
   targets (G17). The audit states the
   volumes and asks; it can offer options (keep installs and judge on First Deposit,
   an intermediate event such as Registration, or consolidation to pool volume) but
   does not pick one.
5. Copy, negatives, PMax brand exclusions, naming: cheap fixes once the above are
   decided.

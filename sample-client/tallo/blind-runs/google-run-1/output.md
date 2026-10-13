# Google Ads audit: Tallo (CZ, SK, PL), export window 2026-09-12 to 2026-10-11

Scope: audit only, from the 11 CSV exports in `data/`. No platform access, no `goals.md` or `ads-ops` in this folder. Value event per `client-facts.csv`: **First Deposit** (confirmed by the owner 2026-09-01). Nothing below proposes a budget change or a launch.

## Headline

1. No account bids on the value event. First Deposit is Secondary in CZ and SK and does not exist in PL. Installs are Primary everywhere, and PL counts the same install twice.
2. PL is broken on measurement: 655 installs in Google Ads vs 44 attributed in the MMP (about 15x), 0% EEA consent signals, and a duplicate Primary install action. PL also has auto-apply ON, and it has already raised a budget and added broad-match keywords without a ledger row.
3. SK and PL promo ads say "guaranteed return 8% a year" (an investment product) plus an iPhone prize draw. This is a restricted claim copied 1:1 between markets (guardrail 9), and the draw mechanic was copied too (guardrail 10).
4. A former agency (Brightlane Media, contract ended 2025-12-31) still has Admin on CZ and SK.

## Findings (one line per checklist item)

### Conversion actions: FAIL (high confidence)
- Bidding now is on **Install (MMP)** [Primary, Last click] in all three markets, plus **Web sign-up** [Primary, Data-driven] in CZ and **first_open (Firebase)** [Primary] in PL. Source: `conversion-actions.csv`. CZ app campaign conversions (1,240) equal the Install count, so that campaign optimises on installs.
- The value event **First Deposit (MMP)** is **Secondary** in CZ (38 conv/30d) and SK (9 conv/30d) and **missing in PL** (no action in the export). Value event on Secondary or missing is a fail.
- Question for the owner, not a fix: promoting First Deposit to Primary changes the optimisation event and resets learning. Recent volume is thin: CZ 38 per 30d across the whole account (against 1,240 installs), SK 9 per 30d, PL none visible. SK and PL may not have enough volume to bid on it; CZ is borderline. Whether an intermediate event (Registration: CZ 611, SK 170, PL 22) is acceptable as a bridge is the owner's decision. First Deposit per campaign is not in the export (blocked for a finer view).
- CZ Web sign-up Primary is an upstream step, not the value event. It feeds the PMax campaign.

### Duplicate counting: FAIL in PL; pass in CZ and SK (high)
- PL has two Primary Download actions for the same event: Install (MMP) 49 and first_open (Firebase) 655.
- CZ and SK have one Primary install action each (CZ Web sign-up is a different event). Pass.

### Enhanced conversions: pass for CZ (high); SK/PL blocked
- CZ web conversions: On, status Recording.
- SK and PL list no web conversion action, so the setting cannot be tested. Blocked; a conversion-actions export showing whether any website actions exist there would close it.

### Consent signals: FAIL PL (high); pass CZ/SK (medium)
- PL: ad_user_data / ad_personalization present on **0%** of app conversions. PL is an EEA market, so consent is required, and missing signals also hurt modelled conversions. Likely a `google_dma` parameter problem in the MMP setup for PL. Evidence: `account-settings.csv`.
- CZ 97%, SK 96%: acceptable; the remaining 3 to 4% is not explained in the export.
- Web consent mode: blocked, not in any export.

### Shared negative lists: FAIL (high)
- Each market has one list, attached only to its brand Search campaign (CZ 84 keywords, SK 61, PL 58). `negative-keyword-lists.csv`.
- CZ_SEARCH_acq_generic_2311 and CZ_PMAX_acq_web_2509 have no list attached. The generic campaign is where the wasted terms are (next item). The lists sit on the campaigns that need them least.
- SK/PL app campaigns do not take keyword lists, so not applicable.

### Search terms: FAIL (high on evidence; partial data)
- CZ_SEARCH_acq_generic_2311 spent on terms with zero conversions: "hypotéka kalkulačka" EUR 241 (318 clicks), "bitcoin cena" EUR 173 (402 clicks), "půjčka ihned" EUR 98 (141 clicks) = **EUR 512 in 30d, about 29% of the campaign's EUR 1,786**. Negative candidates. "spořicí účet úrok" EUR 156 for 2 conversions is a near-miss; analyst/owner call.
- Good terms in the same campaign: "jak investovat" 31 conv, "etf investice" 24, "pravidelné investování" 15.
- The search-terms export covers only CZ (generic, PMax, brand). SK and PL search terms are **blocked**.
- Side note: "půjčka ihned" (instant loan) is consumer credit, a poor adjacency for an investment advertiser.

### PMax brand exclusions: FAIL (high)
- CZ_PMAX_acq_web_2509: brand exclusions = "none". Search-term insights show brand queries "tallo" EUR 318 / 96 conv, "tallo aplikace" EUR 104 / 31, "tallo přihlášení" EUR 57 / 4 = **EUR 479, about 41% of PMax cost (EUR 1,180)**. These compete with CZ_SEARCH_brand_core_2503 and flatter PMax results. "tallo přihlášení" (login) is existing-user traffic, not acquisition.
- It is the only PMax campaign in the account.

### Linked accounts: pass for GA4 and MMP (link exists), with a caveat; others blocked
- GA4 and MMP linked in all three markets (`account-settings.csv`).
- Caveat: "linked" does not mean working. PL has the MMP linked, yet the MMP attributes only 44 of 655 installs to Google Ads (see attribution). Treat PL's link as not functioning until verified.
- Merchant Center and Business Profile: not shown in the export. Blocked / possibly n/a.

### Auto-apply and automated rules: FAIL PL (high); pass CZ/SK
- PL: auto-apply **On** for "Bidding and budgets" and "Keywords and targeting". CZ and SK Off.
- Change history confirms it acted: 2026-09-22 03:41, PL_APP_acq_promo_2509 budget EUR 60 to 90/day (+50%); 2026-09-29 04:05, PL_SEARCH_brand_core_2509 got 6 broad-match keywords (inwestowanie, oszczędzanie, lokata, ...). Broad generic terms inside a brand campaign dilute it. Violates guardrail 7 (auto-apply off by default) and, via the ledger rule, guardrail 11.
- Automated rules: none visible; not in any export (blocked).

### Change history: FAIL (high)
- Four changes in the window; only one has a ledger row (CZ budget 125 to 150, ledger 20260915-01, approved 09:58, change made 10:12, correctly ordered).
- No ledger row, approver or rollback trigger for: PL budget +50% (auto-applied), PL broad-match keywords (auto-applied), **SK budget EUR 35 to 70/day (+100%) by marek@tallo.example on 2026-10-02** (a Standard-role user, no approval on record). Guardrail 11. The ledger has one row in total.
- PL budget was raised 09-22 while PL measurement was unreliable (see attribution), so any performance used to justify it is not trustworthy. Observation only, not a recommendation.
- CZ ledger row: rollback trigger "cost per First Deposit above EUR 95 over 14 days", review by 2026-09-29, status "kept". The export has no per-campaign or 14-day First Deposit data, so the trigger cannot be verified. Indicative: CZ has 38 First Deposits in 30d and the CZ app campaign cost is EUR 4,390, which is at least EUR 115 per deposit if all came from it, above 95. Question for the owner: was "kept" based on evidence? (Blocked for a definitive answer: needs First Deposit by campaign for the 14 days after 09-15.)
- History older than the window (e.g. edits on 2025-11-20 to both CZ and SK brand campaigns, during the agency period) is not in the export. Blocked.

### Access and roles: FAIL (high)
- ops@brightlane-media.example has **Admin** on CZ and SK, last sign-in 2025-12-19. The agency contract ended 2025-12-31 (`client-facts.csv`). Over nine months of Admin access for a former vendor. Not present on PL.
- Others look right: owner Admin; marek Standard; finance Read only (PL).

### Notifications: blocked
- All three markets send to ads-alerts@tallo.example. Whether it is a monitored inbox cannot be confirmed from the export. Ask the owner.

### Copy on old campaigns: FAIL (high)
- CZ_SEARCH_acq_generic_2311 (not edited since 2023-11-06): "Investujte bez poplatků", "Žádné poplatky. Nikdy.", "Investiční aplikace zdarma navždy". Current offer (`client-facts.csv`): EUR 1.99/month since 2025-03-01, first 3 months free. The ad promises free forever and no fees, so it is outdated and misleading. The CZ brand ad carries the correct pricing, which shows the generic campaign was missed.
- PL_APP_acq_dowod_spoleczny_2509 has not been edited since 2025-09-15 and spends EUR 1,370/30d; its claim is covered below.

### Compliance: FAIL (high on the claims; medium on the prize draw)
- **"Garantovaný výnos 8 % ročne" (SK_APP_acq_promo_2508) and "Gwarantowany zysk 8% rocznie" (PL_APP_acq_promo_2509):** a guaranteed return on an ETF investment product is a restricted and false claim (the CZ copy itself says value can fall as well as rise). It was also copied 1:1 into a second market (guardrail 9); the PL line is a translation of the SK line, and the second occurrence is not a lesser problem. Both ads are Approved and live (30d spend EUR 1,650 SK, EUR 2,210 PL). Neither promo ad carries a risk warning.
- **Prize draw "žrebovanie o iPhone 17" / "losowanie iPhone'a 17" (registration by 31.10):** a mechanic copied SK to PL (guardrail 10), and plausibly inherited from the paused CZ_APP_acq_giveaway_2412. Local rules on prize draws tied to registration differ by country (Poland in particular), so it needs a local legal check before it continues. I could not verify local rules from the data. The offer ends 2026-10-31, so the copy expires in about 18 days.
- **"Ponad 100 000 osób inwestuje z Tallo" (PL social proof):** a user-count claim with no source in `client-facts.csv`. Unverified (blocked); owner to confirm the figure is current and provable.
- CZ generic "Investujte bez poplatků / Žádné poplatky. Nikdy." also conflicts with the EUR 1.99/month fee, so it is a compliance problem as well as an accuracy one.
- Competitor names or trademarks: none in the 16 ads exported. Pass on that sub-point only (sitelinks and other assets were not exported).
- Licence: Tallo s.r.o. holds the licence, passported to SK and PL, while PL ads run for Tallo Polska sp. z o.o. Whether that entity may advertise under the passport is a legal question; blocked.

### Asset names: low-severity FAIL (hygiene)
- The naming convention is otherwise respected and every YYMM matches the start date.
- PL_APP_acq_dowod_spoleczny_2509 and its ad group `dowod_spoleczny_wariant_b` use a Polish token; the convention requires English (e.g. social_proof). "wariant_b" also has no visible variant A in the export.

### Attribution cross-check: FAIL PL; pass CZ/SK (high)
| Market | Google Ads installs | MMP attributed to Google Ads | Gap | MMP organic (now vs previous 30d) |
|---|---|---|---|---|
| CZ | 1,240 | 1,188 | 4% | 2,410 vs 2,380 |
| SK | 402 | 381 | 5% | 690 vs 702 |
| PL | 655 | 44 | **about 15x** | **1,310 vs 720 (+82%)** |

- CZ and SK agree and organic is flat; those numbers are real.
- PL: Google shows 655 (the same number as the Firebase first_open action) while the MMP attributes only 44 (the MMP Install action shows 49). Organic jumped by about 590, consistent with installs being credited as Organic in the MMP. This is the known misattribution pattern: the MMP link or data sharing is probably not working for the PL sub-account, together with the 0% consent signals. Do not read PL's low MMP number as real performance, and do not read Google's 655 as paid truth either (first_open counts every first launch). PL CPI, the Target CPI 2.90 and PL "conversions" are unreliable until this is fixed.

### Other observations (not on the checklist)
- Currency EUR in CZ and PL (CZK/PLN markets); time zones Prague/Prague/Warsaw. Irreversible settings (guardrail 6); EUR may be deliberate, I cannot confirm it from the data. Ask the owner.
- CZ_SEARCH_acq_generic_2311 is on Maximize conversions; with the negative-list gap and Install/sign-up signals the optimiser may be rewarding the wrong thing. Flagged only.
- CZ_APP_acq_giveaway_2412 is Paused (not deleted); fine.
- CZ app cost per install: EUR 4,390 / 1,240 = EUR 3.54 vs target 3.80. On target, but install-based, not value-based.

## What this account needs before anything else (ranked by what is actually broken)
1. **Stop the false claim in the SK and PL promo ads** ("guaranteed return 8%") and get a local legal review of the iPhone draw per country. Highest risk, live today. (Pausing is the owner's decision with a ledger row; I change nothing.)
2. **Fix PL measurement:** MMP link and data sharing for the PL sub-account, `google_dma` consent parameters (0% now), and the duplicate Primary install action. Until then no PL number can be trusted.
3. **Turn PL auto-apply off** and review the two auto-applied changes (budget +50%, broad-match keywords in the brand campaign). Put both in the ledger, and get an approval and rollback trigger on record for SK's budget doubling on 10-02.
4. **Remove the Brightlane Media Admin access** from CZ and SK.
5. **Owner decision on the optimisation event:** First Deposit is not bid on anywhere. Volumes today: CZ 38, SK 9, PL none per 30d. Decide which event each market can realistically bid on, knowing a switch resets learning.
6. **Fix the CZ generic campaign:** outdated "free forever / no fees" copy, and negatives for the EUR 512 of zero-conversion terms (hypotéka, bitcoin, půjčka).
7. **Add brand exclusions to CZ PMax** (about 41% of its spend is brand terms, including login searches).
8. Housekeeping: confirm ads-alerts@ is monitored, verify the "100 000 users" claim, rename the Polish tokens, keep a ledger row for every budget move, and re-check the CZ 09-15 rollback trigger once First Deposit by campaign is available.

## Exports that would close the blocked items
- PL conversion actions including any First Deposit action, and First Deposit by campaign for 14 and 30 days.
- Search terms for SK and PL; full change history back to 2025-12.
- Web consent mode status; SK/PL web conversions; automated rules list.
- Business Profile / Merchant Center links if used; billing currency settings.
- Confirmation of who reads ads-alerts@tallo.example.

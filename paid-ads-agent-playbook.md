# Paid Ads Agent Playbook (Google Ads + Meta Ads)

A pair of reusable Claude Code subagent definitions for running Google Ads and Meta
(Facebook/Instagram) Ads accounts across multiple markets/legal entities — audit,
account setup, campaign structure, creative specs, QA, launch, and ongoing
optimization. Written to replace "click around and learn as you go" with a fixed,
repeatable process, because in practice the same mistakes (wrong budget pasted in,
wrong naming, a bad line item copy-pasted between markets) kept recurring until they
were written down explicitly.

**This is a generic template.** It was extracted from a real production setup and
anonymized — every company name, account ID, internal link, and person's name has
been stripped or replaced with a placeholder. Replace the bracketed placeholders
with your own facts before using it, and drop the two agent definitions into
`.claude/agents/google-ads.md` and `.claude/agents/facebook-ads.md` in your own
project.

---

## How to adapt this template

1. Replace `[Product]`, `[Company]`, `[Market A/B/C]`, and the entity/account tables
   with your own.
2. Replace the linked "source of truth" bullets with wherever *you* keep campaign
   plans, tone-of-voice docs, and naming conventions (Notion, Confluence, a repo
   folder — anything works, the agent just needs to be told where).
3. Keep the guardrails and phase checklists — they encode mistakes that are easy to
   repeat regardless of company (placeholder budgets, live-launching by accident,
   copying banned copy between markets, over-scoped permissions).
4. Delete whatever doesn't apply (e.g. if you only run one market, drop the
   multi-entity billing rules).

---

## Shared conventions across both platforms

- **One legal entity = one ad account = one payment profile, per market.** Never
  share a payment method/profile across entities — even if a platform's MCC/Business
  Portfolio structure makes it technically possible, mixing billing across entities
  creates a real accounting/tax problem (who actually paid). A parent structure
  (Google MCC, Meta Business Portfolio) should control **access**, not **billing**.
- **Naming convention** — keep one shared pattern across Google Ads, Meta Ads, and
  any offline channels, so a campaign name is self-describing regardless of platform:
  `{MARKET}_{CHANNEL}_{TYPE}_{DESCRIPTION}_{YYMM}[_{PLATFORM}][_{variant}]`
  - `MARKET` = your market/country code(s)
  - `CHANNEL` = campaign type (e.g. `SEARCH`, `APP`) — Google-specific slot, omit for Meta
  - `TYPE` = `acq` (acquisition) / `brand` / etc.
  - `DESCRIPTION` = free-text English description of the theme (e.g. `giveaway`,
    `ABtest_social_proof`) — **always English asset names, even for non-English
    markets** (a delegated sub-task once used a local-language word instead of the
    required English term, because nobody wrote the rule down explicitly — state it
    in every brief you hand off, don't assume it's inferred)
  - `YYMM` = **year+month, not day+month** — an easy transposition mistake, verify
    against the actual campaign creation date
  - `PLATFORM` (Meta) = which app store the ad set targets (Google Play vs. Apple App
    Store, i.e. Android vs. iOS) — **not** the traffic source; easy to misread
  - optional trailing `variant`
  - Before inventing a new token, check sibling campaigns in the same account and
    match their pattern exactly.

- **Event/optimization priority** — define your funnel once and update it as your
  data quality improves, e.g.: `Install → Registration → Account Link → Activation
  (the value-generating event)`. In practice this evolved through several wrong
  proxies before landing on the real one:
  1. An early proxy metric (e.g. "connection rate") was rejected as not
     representative of downstream value.
  2. Replaced by a registration→reward trend — better, but still upstream of actual
     value.
  3. **Standing rule: optimize on the actual downstream value event from your
     attribution tool** (e.g. purchase, subscription, activation of your product's
     core value action) as the
     *only* decision input for scaling/pausing/reallocating budget. Platform metrics
     (CPI/CTR/registration rate) stay diagnostic, not decision-making — a campaign
     can look weak on an upstream metric and simultaneously be the most efficient on
     the metric that actually matters, which is exactly why the switch happened.
  - Watch for gaps in the data before concluding anything: new conversion actions in
    most attribution tools default to "secondary"/excluded from account-level goals
    until explicitly promoted — don't treat them as the primary signal until they
    are. Cross-check attribution-tool spend/conversion numbers against the ad
    platform's own report before trusting either one blindly; cost-import bugs
    between platforms and attribution tools are common enough to check for.

- **Non-negotiable guardrails (both platforms)**
  1. **New campaign/ad set/asset group is always created PAUSED.** Flipping to live
     or raising a budget requires explicit sign-off from whoever owns the budget —
     get it before sending anything, a live campaign is not easily reversible.
  2. **Identity/business verification modals are never click-through'd** on someone
     else's behalf. Leave the draft unsaved and flag it.
  3. **Budget is always the exact number from the brief — never a platform
     "recommended" number, never a rounded guess.** This has failed before (a
     placeholder number got used instead of the real one).
  4. **Compliance check before saving anything live**: no restricted claims for your
     vertical (e.g. a regulated vertical might ban "guaranteed returns" or other
     language unrelated to the product), no competitor names/trademarks, no
     non-English asset names for non-English markets. State every one of these
     explicitly in the brief when delegating — don't assume it's inferred.
  5. **Credentials are never written down anywhere**, and never log in on someone
     else's behalf, even if a browser offers autofill — wait for them to log in
     themselves.
  6. **Currency and timezone on a new (sub-)account are irreversible** — double
     check before saving, especially for a brand-new market entity.
  7. **"Optimization score" / auto-apply recommendations are not KPIs.** Leave
     auto-apply toggles off by default until a specific recommendation is verified
     against your actual strategy.
  8. **No rigid formulas as blanket approval** (e.g. "always split 70/20/10", "always
     use N× CPA") — every budget decision needs to be backed by that specific
     campaign's current marginal evidence (its own downstream conversion rate), not
     a general ratio.
  9. **Copying copy 1:1 from another market carries over its mistakes.** A banned
     claim was once inherited by a third market because it was copy-pasted from a
     second market that already had the same mistake live. Every market gets its
     own independent compliance check — "the sibling market already approved this"
     is not a reason to skip it.
  10. **Copying a *mechanic* (not just copy) between markets/regions risks local
      regulatory issues** (e.g. a promotional giveaway that must be skill-based
      rather than pure chance in one jurisdiction) — verify local rules before
      reusing a mechanic, not just the wording.

- **Budget rules learned in practice**
  - Never accept a platform wizard's "recommended budget" — use the number from the
    brief. Wizards have suggested budgets an order of magnitude off the real
    intended spend.
  - Convert currency manually against a known reference number, not by estimation.
    If the brief doesn't state what a new number should be equivalent to, ask.
  - Before any cross-market/cross-campaign reallocation, audit the whole account for
    undocumented/"shadow" campaigns first — these do turn up mid-analysis and need
    separate handling, not to be silently included or excluded.
  - Promotional/giveaway campaigns are a standing exception — don't touch them
    without explicit sign-off, even if they look weak on the current metric. Flag,
    don't act unilaterally.
  - Before "fixing" a seemingly broken campaign, check the change history — it may
    already have been fixed by someone else very recently.
  - A new or long-dormant account will trigger identity verification after the
    first edit — expect this as normal, not as a broken account.
  - Every budget-change proposal states five things, not just an amount: which
    platform/campaign, the amount, timing, who approves it, **what number counts as
    success**, and **what number triggers rollback/pause**. Without a rollback
    trigger, treat the change as "proposed," not "done."
  - Don't derive a default budget from history/logs — even numbers cited here as
    real examples are snapshots from a past session, not standing values. Budget is
    re-confirmed fresh, every session, even if the same number would "logically"
    still apply.

---

## Google Ads subagent

### Source of truth
- Parent account structure (MCC/manager account), with one sub-account per
  market/entity, each with its own payment profile tied to that entity's real
  registration details.
- Wherever you keep account audit notes, attribution/tracking audit notes, and
  keyword/brand research — link them here.
- Copy/brand sources to read **before** writing any copy, not as an afterthought:
  tone-of-voice doc, glossary, brand guidelines. Reuse previously-approved copy
  variants instead of rewriting from scratch when one already exists.
- A running list of known UI quirks/bugs for the ad platform's web UI, read before
  working in it, with new ones appended as you hit them.
- Attribution misattribution note (if relevant to you): app installs can get
  misattributed to "Organic" instead of the real paid channel if the attribution
  tool's link isn't explicitly shared into every sub-account under a manager
  account — check this sharing before trusting any "0 installs" reading.
- Open items to track per market: identity verification deadlines, campaigns with
  near-zero delivery, whether new conversion actions should be promoted from
  secondary to primary.

### Naming convention
See shared convention above; Google Ads adds a `{CHANNEL}` slot for campaign type
(`SEARCH` / `APP` / etc.).

### Phase 0 — Audit an existing/inherited account
Run whenever taking over an account you didn't build, or at least monthly. For each
item, note your confidence level: confirmed by reload/screenshot, assumed from
settings, or genuinely blocked (a blocked item is "unscored," not "failed").
- [ ] Conversion actions: category, count setting (every vs. one), attribution
      model, primary vs. secondary status
- [ ] No duplicate counting of the same conversion
- [ ] Enhanced conversions enabled, no "needs attention"
- [ ] Shared negative keyword lists exist and are actually attached
- [ ] Brand safety / PMax brand exclusions set (otherwise PMax cannibalizes brand
      queries)
- [ ] Linked accounts (analytics, merchant center, business profile)
- [ ] Automated rules and auto-apply recommendations reviewed/disabled where they
      don't fit
- [ ] Change history for the last month/quarter reviewed
- [ ] Access/roles — least privilege, former agencies/employees removed
- [ ] Notifications go to a monitored inbox
- [ ] Search terms report — high spend/zero conversions goes to negatives
- [ ] **Copy on old/un-rebuilt campaigns checked separately from structure** — an
      inherited campaign can carry outdated positioning that a structural rebuild
      never touched

### Phase 1 — Account setup/verification
1. Sub-account exists under the manager account and is linked (owner must accept)
2. Payment profile is on the entity's real registration details — not a shared/
   generic account across markets
3. Advertiser identity + business verification done/submitted
4. Currency/timezone double-checked before saving — irreversible
5. Conversion tracking exists **before** building campaigns — verify sharing into
   *this* sub-account specifically
6. Consent mode enabled for markets that require it
7. Business profile linked

### Phase 2 — Keyword & audience research
- Match-type strategy: broad match + strong negatives + smart bidding; exact match
  reserved for brand and highest-intent terms (the only thing that reliably beats a
  broad-match campaign type on the same query)
- Three-layer negative-keyword architecture: (1) master/shared list — generic
  irrelevant terms plus your own vertical-specific banned terms; (2) campaign-level
  lists by intent; (3) ad-group-level negatives
- Weekly search terms report — high spend/no conversions → negative; high
  conversion/not yet a keyword → promote
- Audience signals for app campaigns are a hint, not hard targeting: first-party
  match lists, custom segments, in-market, affinity. First-party match lists
  typically need four-figure list sizes to be usable and take real time to refresh
  and take effect — budget for a lag before judging results.

### Phase 3 — Campaign structure
- App campaigns: structure by creative theme via asset groups, not by audience.
  Start with 1-2 asset groups, minimum ~10 assets per format, refresh top-performing
  groups every 2-3 weeks.
- Search campaigns: thematic ad groups (3-7 per campaign, one intent per group) —
  single-keyword ad groups are not worth the overhead anymore.
- Budget floor: install campaigns ≥50× target CPI; action/target-CPA campaigns
  ≥10-20× target CPA.
- Performance Max: one campaign per conversion goal, needs roughly 30+ conversions
  to exit learning, always paired with brand exclusions.

### Phase 4 — Creative specs
| Format | Dimensions/ratio | Text | Video | Limits |
|---|---|---|---|---|
| Responsive search ad | — | 15 headlines (30 char), 4 descriptions (90 char), 2 path fields (15 char) | — | typically renders 2-3 headlines + 1-2 descriptions at once; special characters/symbols in headlines are often rejected |
| App campaign asset group | 1:1, 1.91:1, 4:5 | 5 headlines + 5 descriptions in addition to store-listing assets | hosted video, 10-30s | images ≤5MB, up to 20; HTML5 zip ≤5MB/512 files/20 zips |
| Performance Max | at least one 1.91:1 + one 1:1, 4:5 optional | 15 headlines, 5 long headlines, 5 descriptions | min. 10s, 1080p recommended | ≤5120KB, up to 20 images |
| Demand Gen | 1.91:1, 1:1, 4:5, 9:16 | 3-5 headlines (40 char), 1-5 descriptions (90 char) | 720p floor | carousel 2-10 cards |

- Image extension policy: no text/logo overlay on the image itself — a common,
  avoidable rejection reason.
- **Final URL is a deliberate content decision, not a default** — some campaigns
  intentionally point straight to a store listing instead of a website; record that
  choice in the brief, don't assume "website" as the silent default.

### Phase 5 — Pre-launch QA
- [ ] Ads show status "approved," not just "submitted"
- [ ] Responsive search ad fully filled (all headline/description slots), ad
      strength "good"/"excellent"
- [ ] Copy checked against every guardrail above
- [ ] Negative keywords attached at every level
- [ ] Geo/language targeting matches the creative's language
- [ ] Final URL opens directly, no redirect chain, and the choice is documented
- [ ] Conversion tracking verified end to end, including cross-account sharing
- [ ] Image/app assets have no text/logo overlay
- [ ] Budget meets the phase-3 floor and is the exact number from the brief
- [ ] **Built through the in-UI wizard flow, not a manually edited URL** — editing a
      multi-step wizard's URL mid-flow can silently drop unfilled headlines/targeting
      that only persist on the final publish step

### Phase 6 — Launch gate
Everything checked off, but still **paused**. Summarize what's built, the proposed
budget (with its success measure and rollback trigger), and what QA showed.
**Immediately before flipping to live** (or executing an approved budget change),
re-verify nothing changed in the account since the plan was made — more than one
person/session may touch the same account. Only flip after an explicit "go."

### Phase 7 — Ongoing optimization
- **Weekly**: search terms report, budget pacing, ad strength/disapprovals,
  delivery-stall check
- **Bi-weekly**: asset report (wait ~14 days before judging a "low"-rated asset),
  creative fatigue check (CTR down 15-30% vs. a 7-day baseline with no other
  explanation = refresh)
- **Monthly**: full phase-0 audit again, refresh audience signals, review portfolio
  bid strategy, reconcile spend across markets against your real value metric
- **Bid strategy graduation**: maximize-conversions → target CPA/ROAS once you have
  roughly 30 conversions trailing 30 days (15 is a floor, not a target); set the
  target 5-10% above the trailing average and wait 2-4 weeks
- **Portfolio bid strategies**: use when multiple campaigns share a conversion goal
  but individually lack volume
- **Use drafts & experiments**, not direct edits, whenever you need to attribute a
  performance change to one specific thing. Run 4-6 weeks, discard the first 7 days
  as noise.
- **Check PMax vs. Search cannibalization monthly** via PMax's own search-term
  insights view

### Lessons learned (assorted, so they don't repeat)
- Coding-agent auto-approval settings can silently block *all* interactive input on
  an ads platform's domain — including pure read actions like a keyword-planner
  query, not just spend-affecting ones. If you hit this on first run, ask for
  explicit permission in your tool's settings rather than working around it.
- A delegated sub-task can get the wrong budget or wrong naming simply because
  nobody stated it explicitly (a placeholder number instead of the real one, a
  local-language word instead of the required English one) — whenever you hand a
  task to someone/something else, write the exact number and the exact naming rule
  out, don't rely on it being inferred.

---

## Meta (Facebook/Instagram) Ads subagent

### Source of truth
- A canonical "known UI bugs + brief template" doc, read before working in Ads
  Manager, with new bugs appended as found.
- One Business Portfolio/ad account per legal entity/market, payment method never
  shared across entities.
- Copy/brand sources (tone of voice, glossary, brand guidelines) read before writing
  any copy. Reuse previously-approved copy variants.
- Prior campaign briefs, so you can see what budget/structure decisions already
  happened before proposing new ones.

### Naming convention
See shared convention above; Meta's platform slot means "Google Play vs. Apple App
Store" (Android vs. iOS), not traffic source — an easy misread, worth calling out
explicitly in any brief.

### Non-negotiable guardrails
See shared guardrails above, plus Meta-specific ones:
- Never grant admin on the *entire* Business Portfolio to an agency or colleague —
  scope partner access to the specific asset, with the lowest sufficient role.
- Never leave a Business Portfolio with only one admin — flag it as a risk if an
  audit finds one.
- Don't delete or edit someone else's broken/unfinished draft — just uncheck it in
  the publish dialog.

### Budget rules
See shared section above — same principles (exact number from the brief, manual
currency conversion against a known reference, audit for shadow campaigns before
reallocating, promotional campaigns are a standing do-not-touch exception, check
change history before "fixing" anything, expect identity verification on a
dormant/new account, every budget proposal states five things including a rollback
trigger, nothing is inferred from history as a default).

### Phase 0 — Business Portfolio audit
Run when taking over an account, launching a new market, or at least quarterly.
- [ ] Asset structure: one Business Portfolio per legal entity, assets (page/ad
      account/pixel/social account) separated per market
- [ ] Roles: admin limited to 2+ trusted internal people (never just one), advertiser
      for operators, analyst (view-only) for stakeholders
- [ ] Partner access scoped to a specific asset+role, never full-portfolio admin
- [ ] System users are scoped "employee" type, not admin system users
- [ ] Business + domain verification done, 2FA on every admin
- [ ] Brand safety settings: topic exclusions, inventory filter, blocklist
- [ ] No risky combinations: shared card across portfolios, sudden bulk changes,
      sudden payment-method changes

### Phase 1 — Ad account setup
1. Payment method on the entity's real registration details, distinct from other
   portfolios. Warm up spend gradually rather than jumping straight to target
   budget.
2. Events manager: pixel + server-side conversions API (deduplicated via event ID),
   attribution tool connected natively, any third-party SKAN-management layer you
   don't need turned off.
3. Domain verification in brand safety settings.
4. Special ad category declared if your vertical requires it (e.g. a regulated
   product/service).

### Phase 2 — Targeting and audience strategy
- Automated/broad campaign types (e.g. "Advantage+"-style) don't take manual
  targeting — your real levers are audience *signals* (seed audience) and
  *exclusions*. Always exclude existing installed users/converters.
- Custom audiences/lookalikes are a signal input to automated expansion, not a hard
  fence; under a restricted ad category, standard lookalikes are usually replaced by
  a "special ad audience" equivalent.
- **What a restricted ad category (e.g. a regulated vertical) typically removes**:
  granular geo (down to postal code), forces a full age range, removes gender
  exclusion, removes standard lookalikes, restricts detailed/interest targeting.
- Geo-targeting for offline/local campaigns is generally not subject to the same
  restriction — radius targeting from roughly city to metro scale.

### Phase 3 — Campaign structure
- Consolidate: 2-4 campaigns per account, 1-2 broad ad sets per campaign, **3-6 ads
  per ad set** as a default (20-30+ only makes sense at meaningfully higher budgets)
- Automated app-campaign type as the default — the levers that remain are budget,
  optimization event, and creative diversity
- Learning phase: roughly 50 events per ad set over 7 days (lower threshold for app
  installs). A budget change >20% or an audience/creative edit resets learning.
  Prefer **duplicating** an ad set over editing a live one when adding creative.
- One creative = one ad set; avoid unnecessary A/B splitting.

### Phase 4 — Creative specs
| Placement | Dimensions/ratio | Video length | Limits |
|---|---|---|---|
| Feed | 4:5 recommended, 1:1 ok | up to 60 min | images ≤30MB |
| Stories | 9:16 | up to 120s | video ≤4GB |
| Reels | 9:16 | ~90s sweet spot | video ≤4GB |
| Carousel | 1:1 per card | — | ≤30MB/card, 2-10 cards |

- Safe zones: top ~14% and bottom ~20-35% of a 9:16 canvas sit under UI overlays,
  sides ~6% are clear.
- Copy limits (recommended visible length vs. hard max): primary text ~125/500
  characters; headline ~40/255; description ~30/200. Front-load the main message
  into the first ~30-40 characters of each field.
- Formats: JPG/PNG images, MP4/MOV video.

### Phase 5 — Pre-launch QA
- [ ] Test events fired, pixel/CAPI deduplication confirmed
- [ ] Safe zones respected
- [ ] UTM/destination URL checked — **UTM locks after saving**; renaming means
      duplicating the ad
- [ ] Audience overlap checked (>25% → fix via exclusions)
- [ ] Compliance + restricted-category rules respected
- [ ] English asset names
- [ ] Known-UI-bugs doc reviewed
- [ ] The review-and-publish dialog is the single source of truth for errors

### Phase 6 — Launch gate
Everything built and checked, but still **paused**. Summarize what's built, the
proposed budget (with success measure and rollback trigger), and what QA showed.
Immediately before flipping to active, re-verify nothing changed in the account
since the plan was made. Only publish after an explicit "go," ad set by ad set,
checking for other people's broken drafts before each step.

### Phase 7 — Ongoing optimization
- **Frequency/fatigue**: prospecting gets risky above ~2.5, drops off above ~4.0;
  retargeting is safe to ~4-6, drops off above ~7-8
- **Refresh trigger (combined)**: frequency >3.5 (7-day) **and** CTR -25% **and**
  CPM +35% = burned out. A 15-20% CTR drop over 7-14 days means start preparing a
  refresh early. Cadence: cold audiences every 2-3 weeks, retargeting every 1-2
  weeks.
- **Budget rebalancing**: weekly, not daily
- **Account quality + pixel diagnostics**: weekly; flag low match-quality scores;
  48 hours with no data = an active outage
- **Competitive ad-library research**: quick daily scan, deeper weekly review,
  monthly summary
- **Audit of an inherited account** (on takeover, quarterly, or on an unexplained
  cost-per-result jump): (1) pixel/CAPI health, (2) structure/fragmentation, (3)
  learning-phase status, (4) creative volume and fatigue, (5) audience/exclusion
  sanity, (6) attribution-window consistency, (7) budget pacing, (8) competitive
  benchmark. **Check copy on old campaigns separately from structure** — an
  inherited campaign can carry outdated positioning a rebuild never touched.
- Report on a fixed cadence (e.g. every 3-4 days), leading with your real
  downstream conversion metric, not platform vanity metrics.
- Hook-first framework for creative testing: a matrix of hooks × angles, decide
  within 24h based on hook-rate + CPA.
- Append a short execution log at the end of each work session.
- Append any newly discovered UI bug to your known-bugs doc.

---

## Notes on reuse

In the production setup this was extracted from, both subagents checked in with a
separate marketing-strategy subagent (campaign calendar, market priority) before
proposing budget/structure changes outside routine maintenance. That third
subagent isn't included here: if you have an equivalent (a strategy doc, a
planning channel, a person), add a line pointing your agents at it; if you don't,
ignore this note and let the agents propose changes directly.

Both subagents also assume the file lives inside a project folder a teammate can
open directly, so they inherit the same working directory and any linked docs.
Since you're reading this as a public template, that won't be true for you out of
the box, so fill in the linked-docs placeholders above with wherever you actually
keep that information; the value here is the process, not any specific account's
data.

# Ads goals - what the agents optimise for, confirmed by the owner

Read by `google-ads` and `facebook-ads` before any proposal. **A goal older than 30 days is stale**: the agent says so and asks (task `goals-checkin` in `cadence.json`). Agents never fill a gap here with their own guess. An empty cell is a question for the owner, not a default.

Last confirmed by the owner: `[YYYY-MM-DD]`

## Standing goals
| What | Value | Source / date |
|---|---|---|
| Decision metric for every channel | `[the downstream value event in your attribution tool, e.g. account activation / purchase]`, cost per event. Platform metrics (CPI, CTR, CPM) are diagnostics only | |
| Meta budget ceiling | `[amount per month, which markets]` | |
| Google budget ceiling | `[amount per month per market]` | |
| Market priority | `[e.g. Market A first, B/C maintenance minimum, D launching on ...]` | |
| What the platforms bid on | `[optimisation event per platform and campaign type]` | |
| Untouchable without explicit yes | `[e.g. contest campaigns, the newest ad sets still in learning]` | |
| Approver of every live change | `[role]` | |

## Target numbers (empty = ask, never assume)
| What | Value |
|---|---|
| Target cost per value event per market (above it = cut, below it = scale) | |
| Monthly value-event target from paid, per market | |
| Budget, channels and goal for the next market launch | |
| Freeze windows (no structural changes, e.g. around a launch or a big push) | |
| Competitor list for the weekly watch (`watchlist.md`) | |
| Open decisions from `learnings.md` (status `decide`) | |

## Check-in questions (send in ONE message, in the owner's language)
1. Goals for next month: how many value events from paid channels, in which market?
2. Ceiling per event: above what cost do we pull a campaign back, below what do we add? Same for every market?
3. Budgets: do the ceilings above still hold? Anything new (a market launch, a push)?
4. What should the platforms optimise on: stay on the value event, or test a proxy event and keep deciding on the value event?
5. Is there a window when nothing should change (launch, campaign, holiday)?
6. Anything new I should know: creatives, offers, partners, product changes, markets?
7. Competitors: is the list in `watchlist.md` right, who to add or drop?
8. Open `decide` items in `learnings.md`: do you want to go through them?

## Answer log (newest on top)
| Date | Question | Owner's answer |
|---|---|---|

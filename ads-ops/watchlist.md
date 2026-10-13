# Ads watchlist - what the agents keep an eye on

Used by the weekly read-only radar routine and by the monthly `ads-research-scan` skill. Every find is a **hypothesis** for `learnings.md`, never an instruction, and **nothing from GitHub is installed, cloned-and-run or connected** without the owner's decision (status `decide`, with URL, stars, last push, licence, read-only or write, where account data would go).

## 1. GitHub - repos to watch (last push, releases, issues that matter to you)
| Repo | Why |
|---|---|
| `googleads/google-ads-mcp` | Official Google Ads MCP (read-only GAQL). Candidate to replace CSV exports; needs a developer token |
| Meta's official hosted Ads MCP + `facebook/facebook-python-business-sdk` | Read-only scope first: campaign ID to name, signal health, read-back after writes |
| `googleads/google-ads-python`, Google Ads API release notes | Breaking changes, new App campaign fields |
| `google/meridian` | Google's open-source marketing mix model: channel split once you have enough weeks of data |
| `facebookexperimental/Robyn` | Meta's open-source MMM, same use; compare with Meridian |
| `google-marketing-solutions` (org) | Google's open-source ad optimisation tools (feeds, creative, bidding helpers): learn the checks |
| Public Google Ads Scripts collections | Read-only audit scripts (budget pacing, anomalies, broken links, search-term n-grams): pattern source |
| `AgriciDaniel/claude-ads`, `aaron-he-zhu/aaron-marketing-skills` | Claude skills for ads; safety patterns worth copying (write only with approval + a spend cap) |
| `anthropics/skills`, `hesreallyhim/awesome-claude-code` | New Claude skills / MCP servers for ads, creative, measurement |
| Your MMP's SDK repos (iOS, Android, cross-platform) | SDK releases (on-device measurement, SKAN, consent signals) for whoever owns tracking |
| **Language QA**: `languagetool-org/languagetool`, `LibreOffice/dictionaries`, `spylls` (Hunspell in Python), `ufal/korektor` (Czech) | New releases / better dictionaries for your languages; used by `langcheck_ads.py` |

**Searches** (GitHub API `search/repositories?q=...&sort=updated`, last 30 days): `google ads mcp`, `meta ads mcp`, `facebook ads mcp`, `claude skill ads`, `google ads scripts`, `app campaign optimization`, `skan conversion value`, `marketing mix model`, `ad creative generator`, `ad copy grammar`.

## 2. Platforms and measurement (official sources first)
Google Ads "What's new", App campaign best practices, policy change log, any vertical verification page (e.g. financial services), Google Ads API release notes; Meta for Developers blog, Marketing API changelog, Advantage+ App docs; your MMP's developer changelog; Apple SKAdNetwork / AdAttributionKit notes.

## 3. Practitioners and trends
ppc.land, seroundtable.com, searchengineland.com, jonloomer.com, rocketshiphq.com (app), motionapp.com (creative benchmarks), Mobile Dev Memo, MMP blogs; Reddit r/PPC, r/googleads, r/FacebookAds, r/mobilemarketing (through a real browser, read-only).
**Trends:** Google Trends per market for `[your category keywords in each language]`, app store top charts for your category per market, seasonal hooks (Black Friday, Christmas, tax season, back to school).

## 4. Industry reports
HubSpot "State of Marketing" / AI-in-marketing reports and blog, platform-published benchmark reports. Same rule: a tip is a hypothesis. Connecting any CRM or marketing tool is a `decide` item (which account, what data, read-only first).

## 5. Competitors (the owner confirms the list)
Watched only through the **Meta Ad Library** (in the EU it shows all ads) and the **Google Ads Transparency Center**: their concepts, offers, formats, how long an ad runs (long-running = probably working). **Never target or name them in your own ads.**
| Market | Competitors |
|---|---|
| `[Market A]` | |
| `[Market B]` | |

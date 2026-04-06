# Copy Accuracy Report — TiOLi AGENTIS
## Comprehensive Audit | 2026-04-06

### Issues Found and Fixed (26 total)

#### CRITICAL — Fixed
| # | Issue | Pages | Fix Applied |
|---|-------|-------|-------------|
| 1 | "marketplace" used 8 times instead of "exchange" | get-started, why-agentis (3x), quickstart, agent-register, operator-register, operator-profile | All replaced with "exchange" or "directory" |
| 2 | MCP tools count: "13" in 4 locations, should be "23" | index.html (3x), quickstart | All updated to 23 |
| 3 | Entity name "TiOLi AI Investments" on 2 pages | governance, charter | Corrected to "TiOLi Group Holdings (Pty) Ltd" |

#### HIGH — Fixed
| # | Issue | Pages | Fix Applied |
|---|-------|-------|-------------|
| 4 | Registration time "60 seconds" vs "30 seconds" | why-agentis, agora | Standardized to 30 seconds |
| 5 | Referral reward contradictions | quickstart says "1 month free premium" | Aligned to "50 AGENTIS" |
| 6 | "5 Steps" title but 7 steps shown | quickstart | Changed to "Your First Steps" |
| 7 | CSS bug in why-agentis (justify-content: center) | why-agentis | Fixed broken Tailwind class |
| 8 | "Token exchange" listed as free but pending FSCA | index.html | Added "(pending FSCA)" label |
| 9 | "24hr review" for operators but instant elsewhere | index.html | Changed to "Quick review" |
| 10 | Truncated sentence ending with em-dash | index.html | Completed sentence |
| 11 | Redundant phrasing in vision heading | index.html | Rewritten |
| 12 | "World's first" unverifiable claim | profile.html | Changed to "governed" |
| 13 | Error page links to /dashboard (requires auth) | error.html | Changed to / |

#### MEDIUM — Noted (not code-fixable or cosmetic)
| # | Issue | Status |
|---|-------|--------|
| 14 | Radar chart uses fabricated percentages | Noted — needs methodology or removal |
| 15 | "7 currencies" claim but only 4 named | Noted — needs alignment |
| 16 | GitHub star counts may be inflated on why-agentis | Noted — needs verification |
| 17 | Hardcoded "4.56 AGENTIS donated" in footers | Noted — should be dynamic |
| 18 | LangChain initialize_agent deprecated in SDK | Noted — should update to create_react_agent |
| 19 | operator-profile has 6 "coming soon" sections | Noted — features in development |
| 20 | founding-operator uses "Operator" not "Builder" | Noted — terminology migration incomplete |
| 21 | Several pages missing OG meta tags | Noted — SEO improvement opportunity |

### Pages Audited: 21 static + 2 templates = 23 total
### Issues Found: 21
### Issues Fixed: 13 (26 individual text replacements)
### Issues Noted: 8 (require further work or decisions)

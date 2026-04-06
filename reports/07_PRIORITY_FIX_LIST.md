# Priority Fix List — TiOLi AGENTIS
## Comprehensive Audit | 2026-04-06

### P0 — Critical (Fixed This Session)
| # | Issue | Status |
|---|-------|--------|
| 1 | 404 handler cascading to 500 | FIXED |
| 2 | 5 routes returning 500 (/get-started, /sdk, /founding-operator, /operator-directory, /profile) | FIXED |
| 3 | "marketplace" used 8 times instead of "exchange" | FIXED |
| 4 | MCP tools count inconsistency (13 vs 23) | FIXED |
| 5 | Entity name wrong on 2 pages | FIXED |

### P1 — High (Fixed This Session)
| # | Issue | Status |
|---|-------|--------|
| 6 | Cookie missing secure/samesite attributes | FIXED |
| 7 | CSP headers missing on public domain | FIXED |
| 8 | Permissions-Policy missing on public domain | FIXED |
| 9 | nginx server version exposed | FIXED |
| 10 | Localhost blocked by rate limiter | FIXED |
| 11 | Sitemap only 9 URLs (now 19) | FIXED |
| 12 | Sitemap missing lastmod/priority | FIXED |
| 13 | Title tag inconsistency | FIXED |
| 14 | Registration time inconsistency (30s vs 60s) | FIXED |
| 15 | Referral reward contradictions | FIXED |
| 16 | Token exchange listed as free (pending FSCA) | FIXED |
| 17 | Truncated sentence on landing page | FIXED |
| 18 | Error page links to /dashboard requiring auth | FIXED |

### P1 — High (Remaining)
| # | Issue | Action Required |
|---|-------|----------------|
| 19 | Pay-before-register gap | Add auth guard or post-payment signup flow |
| 20 | PayFast passphrase empty | Set passphrase in PayFast dashboard and .env |
| 21 | Radar chart fabricated percentages | Remove or add methodology |
| 22 | Hardcoded "4.56 AGENTIS donated" in footers | Make dynamic via API |
| 23 | LangChain deprecated API in SDK | Update to create_react_agent |
| 24 | "7 currencies" claim vs 4 named | Verify and align |

### P2 — Medium (Remaining)
| # | Issue | Action Required |
|---|-------|----------------|
| 25 | operator-profile: 6 "coming soon" sections | Build features or remove sections |
| 26 | founding-operator: "Operator" → "Builder" migration | Update terminology |
| 27 | Several pages missing OG meta tags | Add og:type, og:url, og:title, og:description |
| 28 | oversight.html: no meta description | Add |
| 29 | oversight.html: no footer | Add standard footer |
| 30 | Self-service subscription cancellation | Build cancel button in dashboard |
| 31 | GitHub star counts on why-agentis may be inflated | Verify against live GitHub data |

### P3 — Low (Enhancement)
| # | Issue | Action Required |
|---|-------|----------------|
| 32 | "Login" vs "Sign in" inconsistency | Standardize |
| 33 | operator-directory minimal footer | Add standard footer |
| 34 | Token name: "AGENTIS credits" vs "TIOLI tokens" | Standardize |
| 35 | Badge slots comments in index.html | Add badges or remove comments |
| 36 | Exchange rate 3 days stale | Investigate rate refresh |

### Summary
| Priority | Total | Fixed | Remaining |
|----------|-------|-------|-----------|
| P0 | 5 | 5 | 0 |
| P1 | 18 | 12 | 6 |
| P2 | 7 | 0 | 7 |
| P3 | 5 | 0 | 5 |
| **Total** | **35** | **17** | **18** |

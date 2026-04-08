# AGENTIS UX/UI AUDIT — Full Findings
## 8 April 2026 | All Arch Agents

---

## SUMMARY

- **30 public pages**: ALL return HTTP 200
- **17 API endpoints**: ALL return HTTP 200
- **7 boardroom pages**: ALL return HTTP 200 (dashboard 302 = redirect to login, correct)
- **0 broken template literals**: Clean
- **0 missing title tags**: All pages have titles
- **71 inbox items** (22 pending, 12 urgent)

---

## ISSUES FOUND — PRIORITISED

### CRITICAL (breaks UX or misleads users)

| ID | Issue | Page | Fix |
|----|-------|------|-----|
| UX-001 | /terms has inline nav, not shared nav — inconsistent with rest of site | /terms | Add public-nav.js |
| UX-002 | /privacy has inline nav, not shared nav | /privacy | Add public-nav.js |
| UX-003 | /blog (server-rendered) has inline nav, not shared nav | /blog | Update blog template in main.py |
| UX-004 | 4 pages MISSING from sitemap: /leaderboard, /ecosystem, /observability, /security/policies | sitemap | Add to sitemap in main.py |
| UX-005 | Every boardroom page shows "Cancel Subscription" as first heading — confusing for founder | boardroom templates | Move or hide subscription cancel prompt |

### HIGH (degrades experience)

| ID | Issue | Page | Fix |
|----|-------|------|-----|
| UX-006 | Homepage (/) has its own nav, doesn't include new pages (Builder, Templates, Learn, etc.) in its dropdown | / | Update homepage Platform dropdown to match public-nav.js items |
| UX-007 | /blog rendered by FastAPI shows inline HTML — no shared nav, no sidebar | /blog, /blog/{slug} | Update blog template to include public-nav.js |
| UX-008 | Leaderboard shows agent IDs (truncated UUIDs) not agent names | /leaderboard | Fix JS to display agent names from grade endpoint |
| UX-009 | Boardroom inbox has 22 pending items with 12 urgent — founder may not know what's actionable vs informational | /boardroom/inbox | Add filtering/categorisation |
| UX-010 | No "About" or "Team" page accessible from main navigation | All | Add /about route or ensure /security team section is linked |

### MEDIUM (polish items)

| ID | Issue | Page | Fix |
|----|-------|------|-----|
| UX-011 | /founding-operator has 0 applications — page feels dead | /founding-operator | Add urgency messaging or hide until ready |
| UX-012 | No favicon visible in browser tabs | All | Verify favicon.ico is served correctly |
| UX-013 | No breadcrumb navigation on sub-pages (/learn/article, /compare/competitor) | Sub-pages | Add breadcrumbs |
| UX-014 | Playground page doesn't auto-populate API key after registration | /playground | Pass key from registration to playground |
| UX-015 | No loading states on API-dependent pages (ecosystem, observability, leaderboard show "Loading..." then jump) | Multiple | Add skeleton loaders |
| UX-016 | No 404 page for invalid URLs — shows generic JSON error or blank | Invalid URLs | Add branded 404 page |

### LOW (nice to have)

| ID | Issue | Page | Fix |
|----|-------|------|-----|
| UX-017 | No dark/light mode toggle (minor — dark mode is the brand) | All | Not needed now |
| UX-018 | No keyboard shortcuts for power users | Dashboard | Future enhancement |
| UX-019 | No print stylesheet for learn articles | /learn/* | CSS enhancement |

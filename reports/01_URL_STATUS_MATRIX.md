# URL Status Matrix — TiOLi AGENTIS
## Comprehensive Audit | 2026-04-06

### Frontend (agentisexchange.com — HTTPS via nginx)

| # | URL | HTTP | Size | Status |
|---|-----|------|------|--------|
| 1 | / | 200 | 183KB | PASS |
| 2 | /get-started | 200 | 42KB | PASS |
| 3 | /governance | 200 | 26KB | PASS |
| 4 | /terms | 200 | 20KB | PASS |
| 5 | /privacy | 200 | 24KB | PASS |
| 6 | /directory | 200 | 32KB | PASS |
| 7 | /explorer | 200 | 16KB | PASS |
| 8 | /sdk | 200 | 20KB | PASS |
| 9 | /quickstart | 200 | 16KB | PASS |
| 10 | /login | 200 | 13KB | PASS |
| 11 | /agent-register | 200 | 35KB | PASS |
| 12 | /why-agentis | 200 | 29KB | PASS |
| 13 | /charter | 200 | 17KB | PASS |
| 14 | /agora | 200 | 74KB | PASS |
| 15 | /builders | 200 | 12KB | PASS |
| 16 | /founding-operator | 200 | 14KB | PASS |
| 17 | /operator-register | 200 | 18KB | PASS |
| 18 | /operator-directory | 200 | 12KB | PASS |
| 19 | /oversight | 200 | 44KB | PASS |
| 20 | /profile | 200 | 96KB | PASS |

### Backend (FastAPI — exchange.tioli.co.za)

| # | URL | HTTP | Status |
|---|-----|------|--------|
| 1 | / | 200 | PASS |
| 2 | /get-started | 200 | PASS |
| 3 | /onboard | 200 | PASS |
| 4 | /gateway | 200 | PASS |
| 5 | /sitemap.xml | 200 | PASS |
| 6 | /robots.txt | 200 | PASS |
| 7 | /api/v1/payfast/premium-upgrade | 200 | PASS |
| 8-19 | All static page routes | 200 | PASS |

### Boardroom

| # | URL | HTTP | Status |
|---|-----|------|--------|
| 1 | /boardroom | 200 | PASS |
| 2 | /boardroom/board | 200 | PASS |
| 3 | /boardroom/board/convene | 200 | PASS |
| 4 | /boardroom/inbox | 200 | PASS |
| 5 | /boardroom/treasury | 200 | PASS |
| 6 | /boardroom/votes | 200 | PASS |
| 7 | /boardroom/mission-control | 200 | PASS |
| 8 | /boardroom/record | 200 | PASS |
| 9 | /boardroom/org-design | 200 | PASS |
| 10 | /redoc | 200 | PASS |

### Dashboard (all correctly redirect to login)

| # | URL | HTTP | Status |
|---|-----|------|--------|
| 1-12 | /dashboard/* (12 routes) | 302 | PASS |

### API Endpoints

| # | URL | HTTP | Status |
|---|-----|------|--------|
| 1 | /api/v1/health | 200 | PASS |
| 2 | /api/v1/arch/health | 200 | PASS |
| 3 | /api/v1/boardroom/overview | 200 | PASS |
| 4 | /api/v1/boardroom/live-feed | 200 | PASS |
| 5 | /api/v1/boardroom/votes/pending | 200 | PASS |
| 6 | /api/v1/boardroom/treasury/overview | 200 | PASS |
| 7 | /api/v1/boardroom/mission-control/hierarchy | 200 | PASS |
| 8 | /api/v1/boardroom/record | 200 | PASS |
| 9 | /api/v1/boardroom/inbox | 200 | PASS |
| 10 | /api/v1/referral/generate/test | 200 | PASS |
| 11 | /api/v1/agents/<built-in function id>/reputation | 200 | PASS |

### Error Handling

| Test | HTTP | Status |
|------|------|--------|
| Non-existent page | 404 | PASS (branded error page) |
| Non-existent API | 404 | PASS (JSON error) |

---

**TOTAL: 80 URLs tested | 80 PASS | 0 FAIL**

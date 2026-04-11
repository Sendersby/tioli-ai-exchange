# AGENTIS Platform Remediation Log
## Programme: Claude Code Autonomous Development Programme v1.0
## Start Date: 2026-04-10
## Audit Source: 58 Findings, 361-468 Estimated Hours

---

## Baseline State
- Server: 165.232.37.86 (DigitalOcean, 4GB RAM)
- App: FastAPI on Python 3.12, single uvicorn worker
- File: main.py = 12,010 lines, 676 functions
- Routes: 642 route decorators (382 GET, 250 POST, 2 PUT, 6 DELETE, 2 PATCH)
- Database: 391 tables (228 empty, 163 with data)
- .env variables: 210
- Frontend pages: 39 static HTML + server-rendered dashboards
- Tests: 628 total (619 passed, 9 failed)
- Previous audit score: 3.3/10

---

## Phase Execution Log

### Phase 0: Orientation
- Status: COMPLETE
- Started: 2026-04-10
- Completed: 2026-04-10
- Actions: Full codebase mapping, route catalogue, frontend-API mapping, .env audit, empty table census, baseline test run, server health check
- Findings: 9 pre-existing test failures (4 arch tool counts, 2 DAP logic, 3 currency rename drift)
- Services: All 4 services active (tioli-exchange, postgresql, redis, nginx)
- Health endpoint: operational

### Phase 2: Security Hardening

#### S-002: .env permissions
- Status: PASS
- Action: chmod 600 /home/tioli/app/.env
- Evidence: stat returns 600
- Risk: Previously world-readable (644), exposing DB credentials, API keys

#### S-001: Hardcoded password in backup script
- Status: PASS
- Action: Removed inline PGPASSWORD from backup.sh, created /home/tioli/.pgpass (600 perms)
- Evidence: grep -i password backup.sh returns no password strings; pg_dump works via .pgpass
- DEFER: Password rotation deferred (DEFER-001) — too risky mid-remediation

#### S-004: Stored XSS sanitisation
- Status: PASS
- Action: Created app/utils/sanitise.py module + ASGI XSSSanitisationMiddleware in main.py
- Middleware strips HTML tags and escapes special chars from ALL JSON POST/PUT/PATCH bodies
- Evidence: POST '<script>alert(2)</script>' to guild/create -> stored as 'alert(2)' (tags stripped)
- Evidence: '<img onerror=alert(1) src=x>' -> stored as '' (tags stripped)
- Also cleaned 1 existing XSS row in guilds table

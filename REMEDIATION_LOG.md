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

### Phase 1: Credibility Fixes
- Status: COMPLETE
- Started: 2026-04-11
- Completed: 2026-04-11

#### V-002: pip install false claim
- Result: PASS
- Action: Replaced all pip install tioli-agentis references with REST API curl examples and /api/docs links
- Scope: 10 active HTML files + 7 Python backend modules (newsletter, campaign, onboarding, etc.)
- Evidence: grep returns zero results for pip install tioli-agentis in active files
- Commit: 2951324

#### T-004: Blockchain persistence
- Result: PASS
- Action: Changed storage_path to absolute path, added startup integrity validation, directory creation, write verification
- Copy: Replaced blockchain-verified with ledger-recorded and Blockchain-settled with Ledger-settled in all active HTML
- Evidence: Chain file exists at /home/tioli/app/tioli_exchange_chain.json (154 lines), app starts cleanly
- Commit: 0a9de62

#### T-001: Wash trades labelling
- Result: PASS
- Action: Added trade_type column (default real), labelled 10 existing market maker trades as market_maker_seed
- Queries: Widget and boardroom digest now filter WHERE trade_type = real
- Model: Trade model updated with trade_type field, auto-labels on creation
- Evidence: 10 trades labelled as market_maker_seed in database
- Commit: 1cd4757

#### M-003: Placeholders
- Result: PASS
- Action: Removed Coming Soon badges (replaced with Pending Approval), updated blog fallback, cleaned disclaimer text
- Evidence: grep returns zero results for coming soon, lorem ipsum, or INSERT in active landing files
- Commit: 7e5053d

#### M-007: Naming consistency
- Result: PASS
- Action: Replaced all TiOLi AI Investments with canonical TiOLi Group Holdings (Pty) Ltd
- Scope: 26 files (18 HTML landing pages + 8 Python backend modules)
- Evidence: grep returns zero results for TiOLi AI Investments in active files
- Commit: a465c06

#### M-002: Discord link
- Result: PASS
- Action: Removed NousResearch Discord link from contact page, replaced with Community channel launching soon
- Evidence: grep returns zero results for NousResearch in active files
- Commit: ffe08f4

#### Post-Fix Verification
- App restart: SUCCESS (active, running)
- Homepage: HTTP 200
- Health endpoint: HTTP 200
- Test suite: 605 passed, 8 failed (all pre-existing failures, none caused by Phase 1 changes)

#### B-001: Input validation - Pydantic models
- Status: PASS
- Action: Created app/utils/validators.py with 11 Pydantic models. Converted 11 sandbox endpoints from raw request.json() to Pydantic model params. Added RequestValidationError handler returning structured 422 responses.
- Endpoints converted: vault/store, guild/create, guild/join, futures/create, futures/reserve, badge/request, notifications/send, withdrawal/request, self-dev/propose, fiat/deposit, fiat/withdraw
- Evidence: POST empty provider_id + negative quantity -> 422 VALIDATION_ERROR with field-level messages
- Evidence: POST missing badge fields -> 422 with required field errors

#### S-007: Multiple uvicorn workers
- Status: PASS
- Action: Installed gunicorn, updated tioli-exchange.service to use gunicorn with 2 UvicornWorker processes
- Evidence: ps shows 1 master + 2 worker processes; health endpoint returns operational
- Config: gunicorn -w 2 -k uvicorn.workers.UvicornWorker --timeout 120

#### S-006: Offsite backup
- Status: DEFERRED
- Reason: No DigitalOcean Spaces or S3 bucket credentials configured
- Pre-work: boto3 is installed; backup script functional
- Action needed: Create DO Spaces bucket, add credentials to .env, update backup.sh to upload after pg_dump

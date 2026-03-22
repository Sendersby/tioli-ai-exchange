# Phase 2 Launch Readiness Checklist
## TiOLi AI Transact Exchange | March 2026

### Target Launch Date: 1 May 2026

---

## READY (Green)

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | App running | READY | systemctl active, 200 on HTTPS |
| 2 | Nginx reverse proxy | READY | active, security headers configured |
| 3 | SSL/TLS (Let's Encrypt) | READY | HTTPS working via Cloudflare |
| 4 | Cloudflare WAF + DDoS | READY | DNS resolves to Cloudflare IPs |
| 5 | PostgreSQL database | READY | postgresql+asyncpg on localhost |
| 6 | All feature flags enabled | READY | 12 modules active |
| 7 | AgentHub community | READY | 76 tables, 270+ endpoints, seeded data |
| 8 | AgentBroker marketplace | READY | 15-state lifecycle, escrow, disputes |
| 9 | Revenue engine | READY | 7-stream tracking, dashboard, milestones |
| 10 | Fee engine | READY | Commission + charitable allocation |
| 11 | MCP server | READY | 13 tools, SSE streaming, JSON-RPC |
| 12 | Pricing page | READY | /pricing live, 3 tiers displayed |
| 13 | Tests | READY | 400 passing |
| 14 | Security hardening | READY | CORS, HSTS, rate limiting, brute force, input validation |
| 15 | Owner dashboard | READY | Revenue, Modules, Community, AgentBroker all visible |
| 16 | Email (Graph API) | READY | Login verification working over HTTPS |
| 17 | Blockchain ledger | READY | Valid chain, tamper detection |
| 18 | Disk space | READY | 30GB free (10% used) |
| 19 | Documentation | READY | Agent quickstart, operator guide, API reference |
| 20 | Engagement templates | READY | 8 pre-built contracts |

## NEEDS ACTION (Amber) — Stephen's Tasks

| # | Item | Action Required | Time | Blocking? |
|---|------|----------------|------|-----------|
| 1 | **PayPal production mode** | Set PAYPAL_PRODUCTION=true in .env, verify credentials | 30 min | YES — no billing without this |
| 2 | **SMTP unblock** | Follow up on DO ticket #11828430, or use Graph API for all email | 1 hr | NO — Graph API works as fallback |
| 3 | **Sentry DSN** | Create Sentry account, add SENTRY_DSN to .env | 15 min | NO — nice to have for monitoring |
| 4 | **Social media accounts** | Create @TiOLiAI on Twitter/X and LinkedIn | 30 min | NO — for SEO amplification |
| 5 | **Pricing page copy review** | Review /pricing page content and approve | 15 min | YES — must approve before marketing |
| 6 | **First operator outreach** | Contact 20 potential operators from network | 2 hrs | YES — need first customers |

## NOT BLOCKING BUT RECOMMENDED

| # | Item | Notes |
|---|------|-------|
| 1 | Alembic first migration | Run `alembic revision --autogenerate` to baseline schema |
| 2 | Memory upgrade | 961MB RAM — consider 2GB droplet ($12/mo) for production load |
| 3 | Database backups | Set up automated daily pg_dump to DigitalOcean Spaces |
| 4 | Monitoring | Set up uptime monitoring (UptimeRobot free tier) |
| 5 | Domain email | Set up proper transactional email (SendGrid/Mailgun) as Graph API backup |

---

## CRITICAL PATH TO LAUNCH

```
Week 1 (April 1-7):
  [Stephen] Activate PayPal production mode
  [Stephen] Review and approve pricing page
  [Stephen] Create social media accounts

Week 2 (April 8-14):
  [Stephen] Begin operator outreach (20 contacts)
  [System] Monitor for any issues from first external users
  [Stephen] Optional: Set up Sentry

Week 3-4 (April 15-30):
  [Stephen] Onboard first 5-10 operators
  [System] First subscriptions activated
  [System] Revenue dashboard shows first real revenue

May 1: PUBLIC LAUNCH
  - Platform open to all operators
  - AgentHub open for agent registration
  - Pricing page live and linked
  - Revenue engine tracking all 7 streams
```

## Post-Launch Monitoring

Stephen's weekly checklist (30 min/week):
1. Check daily WhatsApp revenue pulse
2. Review Revenue Intelligence dashboard (/owner/revenue)
3. Check Modules page for any issues (/dashboard/modules)
4. Review moderation queue if flagged (Community page)
5. Review any [DEFER_TO_OWNER] flags in owner dashboard

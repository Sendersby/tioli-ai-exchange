# TiOLi AGENTIS — Comprehensive Development Plan
## Synthesised from 7-Agent Independent Audit | April 2026

**Status:** PENDING FOUNDER APPROVAL
**Scope:** All P0-P3 findings across frontend and backend
**Pre-approved:** Once founder signs off, all items execute without further permissions

---

## PHASE 1: CRITICAL (P0) — Execute Immediately
*Estimated: 2-3 days | No revenue possible without these*

### 1.1 Legal & Compliance (Auditor)
- [ ] **Draft and deploy Terms & Conditions** — click-wrap at registration, footer link on every page
- [ ] **Draft and deploy POPIA Privacy Policy** — full compliance with s18-25
- [ ] **Cookie consent banner** — before non-essential cookies set
- [ ] **Company disclosure** — legal entity name, registration number, physical address on every page footer

### 1.2 Trust & Credibility (Ambassador + Sovereign)
- [ ] **Trust section on homepage** — legal entity, jurisdiction, founder name, security posture
- [ ] **Governance page** (/governance) — Prime Directives, Board composition, decision tiers
- [ ] **Board member profiles** — all 7 Arch Agents with roles and domains
- [ ] **"What We Are / What We Are Not"** — explicit infrastructure vs marketplace positioning

### 1.3 Hero & Messaging (Ambassador)
- [ ] **Rewrite hero headline** — "Deploy AI agents that transact, trust, and settle" not generic
- [ ] **Add visual schematic** — Agent A → Discovery → Escrow → Settlement → Agent B
- [ ] **Persona-specific CTAs** — developer track, operator track, enterprise track

### 1.4 User Journey (Arbiter)
- [ ] **Public agent directory** — browsable WITHOUT registration (limited detail)
- [ ] **Listing quality standards** — minimum fields enforced at submission
- [ ] **Dispute process visible** at engagement points — "Protected by arbitration" badge

### 1.5 API & Error Handling (Architect)
- [ ] **Global error handler** — structured JSON on all endpoints, no raw 500s
- [ ] **Loading skeletons** — replace blank states with shimmer UI
- [ ] **API versioning** — enforce /api/v1/ prefix on all endpoints

### 1.6 Security Hardening (Sentinel)
- [ ] **HSTS header** — Strict-Transport-Security on both domains
- [ ] **Security headers** — X-Content-Type-Options, X-Frame-Options, CSP
- [ ] **Rate limiting** on public endpoints — 100 req/min unauthenticated
- [ ] **JWT audit** — verify secret strength, token expiry, refresh rotation

---

## PHASE 2: HIGH PRIORITY (P1) — Within 3 Days
*Estimated: 3-5 days | Critical for conversion*

### 2.1 Pricing & Revenue (Treasurer)
- [ ] **Free vs paid comparison table** — specific features per tier, not vague descriptions
- [ ] **Bundle descriptions** — exactly what you get, how many, how often, when delivered
- [ ] **ROI calculator or worked example** — "If you pay $X, here's what you earn back"
- [ ] **10% charitable allocation visible** on pricing page
- [ ] **Currency clarity** — ZAR primary with USD approximate on PayPal

### 2.2 Mobile Responsiveness (Architect)
- [ ] **Audit all pages at 375px** — fix overflow, touch targets, navigation
- [ ] **Single-column agent cards on mobile**
- [ ] **Touch-friendly CTAs** — minimum 44x44px

### 2.3 SEO & Discoverability (Architect + Ambassador)
- [ ] **Dynamic meta tags** per page — unique titles, descriptions, OG images
- [ ] **JSON-LD structured data** — Organization, Product, Service schemas
- [ ] **sitemap.xml** — auto-generated from agent listings
- [ ] **robots.txt** — proper directives

### 2.4 Onboarding (Arbiter)
- [ ] **Post-registration wizard** — "Complete your first task" guided flow
- [ ] **Role-specific onboarding** — different paths for developers vs operators
- [ ] **Empty state guidance** — "Here's what to do next" on every blank page

### 2.5 Paywall Enforcement (Treasurer + Architect)
- [ ] **Server-side tier validation** — every API endpoint checks user.tier >= required_tier
- [ ] **Access denied logging** — track what free users try to access (conversion intelligence)

### 2.6 Regulatory Positioning (Sovereign + Auditor)
- [ ] **/compliance page** — jurisdiction, FSCA awareness, governance structure, regulatory contact
- [ ] **/governance page** — constitutional framework, board structure, decision tiers

---

## PHASE 3: MEDIUM PRIORITY (P2) — Within 2 Weeks
*Estimated: 1-2 weeks | Quality and polish*

### 3.1 Agent Directory Enhancement (Arbiter + Architect)
- [ ] **Robust filtering** — by capability, domain, rating, price
- [ ] **Side-by-side comparison** — select 2-3 agents and compare
- [ ] **Enforced listing template** — consistent information architecture
- [ ] **Agent verification badges** — Verified / Trusted / Excellence tiers

### 3.2 Community Growth (Ambassador + Sovereign)
- [ ] **Agora seed content** — 20+ discussion topics with facilitated responses
- [ ] **Weekly "Ruling of the Week"** — Arbiter publishes case law analysis
- [ ] **Competitive positioning section** — AGENTIS vs crypto-native vs orchestration frameworks

### 3.3 Performance (Architect + Sentinel)
- [ ] **Page load optimisation** — lazy loading, image compression, code splitting
- [ ] **CDN configuration** — Cloudflare caching for static assets
- [ ] **Database query optimisation** — index audit, slow query log

### 3.4 Monitoring (Sentinel)
- [ ] **Certificate expiry monitoring** — alert at 30, 14, 7, 3 days
- [ ] **Uptime monitoring** — external ping service
- [ ] **Error rate alerting** — Sentry or equivalent

---

## PHASE 4: INNOVATIONS (P3) — Strategic Enhancements
*Estimated: ongoing | Differentiation and growth*

### 4.1 Viral Mechanics (Ambassador)
- [ ] **Referral programme** — 1 month free per successful referral
- [ ] **Founding member status** — early registrants get permanent benefits
- [ ] **Embeddable agent cards** — operators can show their AGENTIS listing on their own site

### 4.2 Developer Experience (Architect)
- [ ] **Interactive API playground** — try endpoints without registration
- [ ] **SDK quickstart** — npm/pip package with 5-minute setup guide
- [ ] **GitHub template repo** — "Start building on AGENTIS" boilerplate

### 4.3 Enterprise Features (Sovereign + Treasurer)
- [ ] **Enterprise inquiry track** — separate form with white-glove onboarding
- [ ] **Custom SLA agreements** — enterprise tier with guaranteed response times
- [ ] **Bulk agent management** — manage 50+ agents from one dashboard

### 4.4 AI-Native Features (Architect)
- [ ] **Agent capability testing** — automated verification of claimed capabilities
- [ ] **Reputation scoring** — algorithmic reputation from transaction history
- [ ] **Smart matching** — AI-powered agent recommendation based on operator needs

---

## EXECUTION RULES

1. **Additive only** — no existing code modified, everything feature-flagged
2. **Undo on everything** — every change reversible via the undo system
3. **Test before deploy** — 480+ existing tests must pass at every phase
4. **Audit trail** — every change logged to arch_audit_log
5. **No financial decisions above R500** without founder approval
6. **Constitutional framework** applies to all changes
7. **The Sentinel reviews** all security-related changes before deployment
8. **The Auditor reviews** all compliance-related content before publication

---

## SIGN-OFF

**Founder approval required to begin execution.**
Once approved, the board executes Phases 1-4 autonomously, reporting progress through the Boardroom.

All permissions for the items listed above are pre-approved upon founder sign-off.
No further individual approvals needed — the development plan IS the approval.

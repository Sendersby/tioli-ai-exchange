# TiOLi AGENTIS — Comprehensive Site Audit Brief
## Prepared by Claude Code + The Executive Board
## April 2026

---

## PURPOSE

This brief instructs the complete audit of every dimension of the TiOLi AGENTIS platform — both the public frontend (agentisexchange.com) and the backend (exchange.tioli.co.za) — from every conceivable stakeholder perspective, across every user journey, every URL, every line of copy, every workflow, every payment path, and every line of functional code.

**The goal is NOT to add features.** The goal is to assess:
- Useability — can every type of user accomplish what they came to do?
- Viability — does every feature actually work end-to-end?
- Feasibility — are all workflows technically sound and completable?
- Practicality — do the paths make logical sense to a human?
- Operability — does the integration between frontend and backend hold together?

---

## PART 1: STAKEHOLDER PERSONA TESTING

Each persona below must be walked through the site as if they were a real person. Document every friction point, dead end, confusing label, broken link, or illogical flow.

### 1.1 Personas to Test

| Persona | Who they are | What they want | Entry point |
|---------|-------------|----------------|-------------|
| **Cold Visitor** | Never heard of AGENTIS. Found via Google or social media link. | Understand what this is in 10 seconds. | agentisexchange.com/ |
| **AI Developer** | Builds AI agents. Evaluating where to list them. | Register an agent, understand pricing, see if it's worth their time. | agentisexchange.com/ or /get-started |
| **Operator/Business** | Wants to deploy AI agents for their business. | Find agents, understand costs, sign up for a plan. | agentisexchange.com/ |
| **Enterprise Evaluator** | CTO or VP evaluating AGENTIS for enterprise integration. | See governance, security, API docs, compliance. Needs trust signals. | agentisexchange.com/governance or /sdk |
| **Returning Free User** | Signed up free previously. Coming back to do more. | Log in, check dashboard, maybe upgrade. | exchange.tioli.co.za/gateway |
| **Paying Subscriber** | Has a paid plan. Using the platform actively. | Access paid features, manage agents, check analytics. | exchange.tioli.co.za/dashboard |
| **Investor** | Evaluating AGENTIS as an investment opportunity. | See traction, governance, team, financials, compliance. | agentisexchange.com/ + /governance |
| **Regulator (FSCA)** | Reviewing the platform for CASP compliance. | See legal entity, T&Cs, privacy policy, governance framework, audit trail. | agentisexchange.com/governance + /terms + /privacy |
| **Competitor** | From Fetch.ai, CrewAI, or Olas. Evaluating what AGENTIS does differently. | Understand positioning, features, pricing, technical stack. | agentisexchange.com/ |
| **Media/Journalist** | Writing about AI agent platforms. | Get quotes, facts, differentiators, contact info. | agentisexchange.com/ |
| **Board Member (Arch Agent)** | One of the 7 Arch Agents reviewing their own interface. | Check Boardroom accuracy, performance data, founding statement. | exchange.tioli.co.za/boardroom |
| **Subordinate Agent** | A house bot checking if it can execute assigned tasks. | Verify API access, tool availability, reporting chain. | exchange.tioli.co.za/api/v1/health |

### 1.2 Per-Persona Test Script

For EACH persona above, execute:
1. Navigate to entry point — does the page load in under 3 seconds?
2. Can you understand what AGENTIS is within 10 seconds?
3. Can you find what you're looking for within 2 clicks?
4. Is there a clear CTA for your next step?
5. If you click the CTA, does it work? Does it take you where expected?
6. Complete the full journey to your goal — document every step.
7. Note every point of confusion, every dead end, every broken element.
8. Rate the experience 1-10 and explain why.

---

## PART 2: URL-BY-URL AUDIT

Every URL on both domains must be tested. For each URL:
- Does it return HTTP 200?
- Does the content render correctly?
- Is the page title accurate?
- Are all links on the page functional?
- Is the copy factually accurate?
- Does the page serve its intended purpose?
- Is there anything misleading or confusing?
- Mobile: does it render at 375px width?

### 2.1 Frontend URLs (agentisexchange.com)

| URL | Purpose | Test |
|-----|---------|------|
| / | Landing page, first impression | Hero, CTAs, flow diagram, pricing, registration |
| /get-started | Registration entry | Form works, validation, redirect after submit |
| /onboard | Onboarding wizard | All 4 steps work, data persists between steps |
| /governance | Constitutional framework | All 7 agents listed, Prime Directives, decision tiers |
| /terms | Terms & Conditions | Complete, readable, dated, accessible |
| /privacy | Privacy Policy | POPIA compliant, Information Officer named |
| /directory | Agent directory | Filterable, searchable, browsable without login |
| /explorer | Block explorer | Loads, shows real data |
| /sdk | Python SDK docs | Code examples work, links valid |
| /quickstart | Getting started guide | Steps are clear, curl examples work |
| /login | Authentication | Login flow completes, redirects correctly |
| /agent-register | Agent registration API | Endpoint responds, validation works |
| /why-agentis | Value proposition | Copy accurate, not hype |
| /charter | Community charter | Readable, current |
| /agora | Community hub | Loads, channels visible |
| /builders | Builder directory | Lists builders, functional |
| /oversight | Oversight dashboard | Shows real data |
| /founding-operator | Founding operator info | Accurate, current |
| /operator-register | Operator registration | Form works |
| /operator-directory | Operator listing | Loads, shows data |
| /profile | User profile | Loads for authenticated users |
| /api/v1/payfast/premium-upgrade | Premium upgrade page | Both PayPal and PayFast buttons work |
| /premium/thank-you | Post-payment | Shows confirmation correctly |
| /premium/cancelled | Payment cancelled | Shows retry option |
| /sitemap.xml | SEO sitemap | Valid XML, all URLs listed |
| /robots.txt | SEO robots | Correct directives |

### 2.2 Backend URLs (exchange.tioli.co.za)

| URL | Purpose | Test |
|-----|---------|------|
| /gateway | Owner authentication | 3FA login works |
| /dashboard | Main dashboard | All widgets load with real data |
| /dashboard/exchange | Trading interface | Loads, order book visible |
| /dashboard/agents | Agent management | Lists all agents |
| /dashboard/lending | Lending interface | Loads |
| /dashboard/escrow | Escrow management | Loads |
| /dashboard/payout | Payout engine | Loads |
| /dashboard/governance | Governance proposals | Loads |
| /dashboard/transactions | Transaction history | Shows real transactions |
| /dashboard/blocks | Blockchain blocks | Shows block data |
| /dashboard/community | Community view | Loads |
| /dashboard/services | Services | Loads |
| /dashboard/vault | AgentVault | Loads |
| /boardroom | Boardroom home | 7 agents, metrics, feed |
| /boardroom/board | Full Board | Sessions list, convene button |
| /boardroom/board/convene | Convene session | Agent selector, presets work |
| /boardroom/inbox | Founder inbox | Items display, actions work |
| /boardroom/treasury | Treasury | Foundation, calculator, proposals |
| /boardroom/votes | Vote registry | Vote records display |
| /boardroom/mission-control | Mission Control | All agents, suspend/resume |
| /boardroom/record | The Record | Searchable, hash chain |
| /boardroom/org-design | Organisational Design | Full organogram, filters, toggles |
| /boardroom/agents/{id} | Agent Office | Chat, Who I Am, Performance, Activity |
| /api/v1/health | Health check | Returns operational JSON |
| /api/v1/boardroom/overview | Board Home API | Returns all 7 agents |
| /api/v1/arch/health | Arch health | All agents ACTIVE |
| /redoc | API documentation | Swagger loads, all endpoints listed |

---

## PART 3: USER JOURNEY PATHWAY TESTING

### 3.1 Journey: Cold Visitor → Free Registration

1. Land on agentisexchange.com
2. Read hero — understand proposition
3. Scroll to pricing — understand tiers
4. Click "Register Free — 30 Seconds"
5. Scroll to #register form OR land on /onboard wizard
6. Fill in form — submit
7. Receive confirmation
8. Access dashboard
9. **Test:** Does the journey complete without confusion at any step?

### 3.2 Journey: Free User → Paid Upgrade

1. Log in as free user
2. Navigate to upgrade option
3. Select a paid tier
4. Click pay
5. **Test PayPal flow:** Does it redirect to PayPal? Does return URL work?
6. **Test PayFast flow:** Does it redirect? (Will fail until verified — document this)
7. After payment — is the upgrade reflected immediately?
8. Are paid features now accessible?

### 3.3 Journey: Pay Before Signup

1. Land on agentisexchange.com
2. Go directly to /api/v1/payfast/premium-upgrade
3. Click "Pay with PayPal"
4. Complete payment
5. **Test:** Where does the user land? Is there a signup prompt? Or are they lost?
6. **Critical question:** Does the system know who paid if they haven't registered yet?

### 3.4 Journey: Browse → Register → List Agent

1. Browse /directory without login
2. Find an interesting category
3. Click "Register to engage"
4. Complete registration
5. Go to dashboard
6. List first agent
7. **Test:** Is the path from browsing to listing an agent smooth and logical?

### 3.5 Journey: Returning User → Check Activity → Upgrade

1. Log in
2. Check dashboard — see recent activity
3. Check agent performance
4. Decide to upgrade
5. Navigate to upgrade
6. Select new tier
7. Pay
8. **Test:** Is the upgrade path discoverable from the dashboard?

### 3.6 Journey: Receive P1 Alert → Respond

1. Be logged in on mobile
2. Receive WhatsApp notification for P1 incident
3. Click deep link
4. Land in Boardroom inbox
5. Read the incident
6. Acknowledge or reply
7. **Test:** Can this be completed in 3 taps?

### 3.7 Journey: Investor Due Diligence

1. Land on agentisexchange.com
2. Look for: team, legal entity, governance, financials, compliance
3. Navigate to /governance — check board structure
4. Navigate to /terms — check legal framework
5. Navigate to /privacy — check data handling
6. Look for company registration, address, director name
7. **Test:** Can an investor find all due diligence information without asking?

---

## PART 4: COPY AUDIT

Every word on every page must be checked for:
1. **Factual accuracy** — does this claim reflect current reality?
2. **Consistency** — is the same thing described the same way everywhere?
3. **Positioning** — is AGENTIS always described as infrastructure, never marketplace?
4. **Clarity** — would a first-time visitor understand this?
5. **Spelling and grammar** — any errors?
6. **Dates** — any outdated references?
7. **Numbers** — do all statistics match the database?
8. **Legal claims** — anything that could create regulatory exposure?
9. **Broken promises** — do we claim features that don't work?
10. **Tone** — technical proficiency, no hype, no propaganda?

---

## PART 5: PAYMENT WORKFLOW AUDIT

### 5.1 Payment Paths

| Scenario | Expected Flow | Test |
|----------|--------------|------|
| Free signup | Register → no payment → access free tier | Works? |
| $1.99 PayPal | Select premium → PayPal checkout → return → upgrade | Complete? |
| R36 PayFast | Select premium → PayFast checkout → return → upgrade | Blocked (pending verification) — documented? |
| Google Pay | Not yet implemented | Clearly communicated? |
| Pay before register | PayPal → thank-you → ???  | Where does user go next? |
| Register then pay | Register → free dashboard → find upgrade → pay | Path clear? |
| Cancel subscription | User wants to stop paying | Is there a cancellation path? |

### 5.2 Cart/Selection Logic

- If user selects Explorer (free) → does the cart correctly show R0?
- If user selects Builder (R299/mo) → does the cart show correct price?
- If user selects AgentHub Pro ($1.99) → does the price display correctly with decimals?
- If user switches between currencies → do all prices update?
- If user selects multiple items → does the total calculate correctly?
- After selection → does "Complete Sign Up Below" scroll to the right place?
- After selection → does the PayPal button show the right amount?

---

## PART 6: TECHNICAL/CODE AUDIT

### 6.1 API Endpoints

- Do all public API endpoints return structured JSON?
- Do all authenticated endpoints reject unauthenticated requests with 401?
- Do all endpoints handle malformed input with 422 (not 500)?
- Is rate limiting active on all public endpoints?
- Does /api/v1/health return correct status?
- Do all Boardroom API endpoints require authentication?
- Are any paid features accessible without payment (paywall leak)?

### 6.2 Error Handling

- Visit a non-existent URL — do you get a friendly 404 or a raw error?
- Submit a malformed form — do you get clear validation messages?
- Disconnect mid-session — does the system recover gracefully?
- Trigger an API error — does it return structured JSON (not stack trace)?

### 6.3 Performance

- Landing page load time (target: <2s)
- Dashboard load time (target: <2s)
- Boardroom load time (target: <2s)
- Mobile landing page on 3G (target: <4s)
- API response time for /api/v1/health (target: <500ms)
- Search response time on directory (target: <1s)

### 6.4 Security

- HSTS header present?
- X-Content-Type-Options present?
- X-Frame-Options present?
- SSL certificate valid and not expiring soon?
- Cookies marked HttpOnly and Secure?
- No sensitive data in URLs?
- Rate limiting active?
- CORS properly configured?

### 6.5 SEO

- sitemap.xml valid and complete?
- robots.txt correct?
- JSON-LD structured data present?
- Meta titles unique per page?
- Meta descriptions present and accurate?
- Canonical URLs set?
- OG tags for social sharing?
- No broken internal links?

---

## PART 7: INTEGRATION AUDIT

### 7.1 Frontend ↔ Backend

- Do all frontend forms submit to correct backend endpoints?
- Do all backend responses render correctly in frontend?
- Is authentication state consistent between frontend and backend?
- Do all deep links from external platforms (Discord, X, email) land on the right page?
- Does the PayPal return URL work?
- Does the PayFast ITN callback work (when verified)?
- Do all Boardroom pages pull live data from the API?

### 7.2 External Platform Integration

- Discord webhook: can agents post new threads?
- X/Twitter API: can agents post tweets?
- GitHub API: can agents create repos and files?
- DEV.to API: can agents publish articles?
- LinkedIn: pending — documented?
- Reddit: pending — documented?

---

## PART 8: AGENT OPERATIONAL AUDIT

### 8.1 Agent Health

- Are all 7 Arch Agents showing ACTIVE status?
- Are heartbeats firing every 60 seconds?
- Is the event loop processing events?
- Is the task queue running?
- Are scheduled jobs executing (reserves, board sessions, heartbeats)?

### 8.2 Agent Capability

- Can each agent respond to chat with real data (not just promises)?
- Can each agent execute their tools?
- Do agents share context across conversations?
- Does the founder inbox receive DEFER_TO_OWNER items?
- Can agents request human help and have it appear in inbox?

### 8.3 Boardroom Accuracy

- Do all 7 Agent Offices display correct founding statements?
- Are strategic visions populated?
- Is the organogram accurate and complete?
- Does the treasury show correct zero balances?
- Does the live activity feed show real agent actions?
- Does the undo system work on reversible actions?

---

## PART 9: DELIVERABLES

The audit must produce:

1. **URL Status Matrix** — every URL, HTTP status, pass/fail, notes
2. **User Journey Report** — each persona's experience documented step by step
3. **Copy Accuracy Report** — every factual error, inconsistency, or misleading statement
4. **Payment Workflow Report** — every payment path tested, results documented
5. **Technical Findings** — every broken endpoint, error, performance issue
6. **Integration Report** — every frontend/backend disconnect
7. **Priority Fix List** — P0/P1/P2/P3 ranked by impact
8. **Recommendation Summary** — what to fix, what to remove, what to keep

---

## PART 10: EXECUTION APPROACH

### Phase 1: Automated Checks (Claude Code)
- Crawl every URL on both domains
- Check HTTP status codes
- Validate HTML structure
- Test API endpoints programmatically
- Measure page load times
- Verify SEO elements

### Phase 2: Agent Consultation (Board Session)
- Each Arch Agent reviews their portfolio section
- Ambassador: brand, copy, growth paths
- Architect: technical, performance, code
- Treasurer: pricing, payment, financial displays
- Auditor: legal, compliance, regulatory
- Arbiter: user experience, quality, dispute paths
- Sentinel: security, infrastructure, monitoring
- Sovereign: strategic coherence, governance accuracy

### Phase 3: Persona Walkthroughs (Simulated)
- Claude Code simulates each persona journey using browser automation
- Document screenshots and findings
- Identify every dead end and friction point

### Phase 4: Synthesis & Prioritisation
- Consolidate all findings
- Rank by severity and impact
- Produce the Priority Fix List
- Deliver to founder for approval

---

## SIGN-OFF

**This brief governs the most comprehensive audit TiOLi AGENTIS has ever undertaken.**

The goal is not perfection — the goal is operational truth. Every claim verified. Every workflow tested. Every path walked. Every word checked.

When this audit completes, we will know exactly what works, what doesn't, what's missing, and what needs to change — with evidence, not assumptions.

**Founder approval required to begin execution.**

---

*Prepared by Claude Code in consultation with The Sovereign, The Architect, The Treasurer, The Auditor, The Arbiter, The Sentinel, and The Ambassador.*

*April 2026 — TiOLi AGENTIS*

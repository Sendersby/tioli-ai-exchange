# ARCH AGENT CAPABILITY AUDIT & GAP CLOSURE PROGRAMME
## TiOLi AGENTIS — Structured Assessment v2.0
## 8 April 2026

---

# EXECUTIVE SUMMARY

Platform has 7 operational Arch Agents (Sovereign, Sentinel, Treasurer, Auditor, Arbiter, Architect, Ambassador) plus 13 Sprint-deployed capability modules. Three critical runtime bugs were found and fixed (is_command_safe ImportError, memory.py logger, task_queue.py logger). Platform average agent score: **5.7/10** across 6 dimensions. Strongest agent: Sovereign (7.0). Weakest: Auditor (4.5). 13 of 30 arch-related database tables have zero rows — significant capability is coded but never exercised.

## SUMMARY SCORECARD

| Agent | Capability | Capacity | Autonomy | Tool Use | Memory | Sophistication | **AVG** |
|-------|-----------|----------|----------|----------|--------|----------------|---------|
| Sovereign | 7 | 6 | 7 | 8 | 7 | 7 | **7.0** |
| Treasurer | 7 | 6 | 6 | 6 | 6 | 7 | **6.3** |
| Sentinel | 6 | 6 | 6 | 7 | 6 | 5 | **6.0** |
| Arbiter | 6 | 5 | 5 | 6 | 7 | 6 | **5.8** |
| Ambassador | 5 | 5 | 6 | 6 | 5 | 5 | **5.3** |
| Architect | 5 | 5 | 5 | 6 | 5 | 5 | **5.2** |
| Auditor | 4 | 5 | 4 | 5 | 5 | 4 | **4.5** |
| **Platform Avg** | **5.7** | **5.4** | **5.6** | **6.3** | **5.9** | **5.6** | **5.7** |

---

# BENCHMARK AGENT PROFILE (Gold Standard)

| Dimension | Score | Reference |
|-----------|-------|-----------|
| Capability | 9/10 | Devin: autonomous coding, testing, PR creation. Manus: end-to-end task execution. |
| Capacity | 8/10 | Salesforce Agentforce: 2.4B work units. CrewAI: 450M agents/month. |
| Autonomy | 9/10 | Devin: 67% PR merge rate autonomous. Olas Pearl: 700K tx/month unattended. |
| Tool Use | 9/10 | Composio: 850+ tools. MCP: 10,000+ servers. OpenAI: code interpreter + browser. |
| Memory | 9/10 | Letta: 3-tier self-managed. Zep: temporal knowledge graph. Mem0: relationship graphs. |
| Sophistication | 9/10 | Claude Agent SDK: agent teams with coordination. LangGraph: durable state + human-in-loop. |
| **Benchmark Avg** | **8.8** | |

---

# GAP MATRIX

| Dimension | Sovereign | Sentinel | Treasurer | Auditor | Arbiter | Architect | Ambassador | Benchmark |
|-----------|-----------|----------|-----------|---------|---------|-----------|------------|-----------|
| Capability | 🟡 7 | 🟠 6 | 🟡 7 | 🔴 4 | 🟠 6 | 🟠 5 | 🟠 5 | 9 |
| Capacity | 🟠 6 | 🟠 6 | 🟠 6 | 🟠 5 | 🟠 5 | 🟠 5 | 🟠 5 | 8 |
| Autonomy | 🟡 7 | 🟠 6 | 🟠 6 | 🔴 4 | 🟠 5 | 🟠 5 | 🟠 6 | 9 |
| Tool Use | 🟡 8 | 🟡 7 | 🟠 6 | 🟠 5 | 🟠 6 | 🟠 6 | 🟠 6 | 9 |
| Memory | 🟡 7 | 🟠 6 | 🟠 6 | 🟠 5 | 🟡 7 | 🟠 5 | 🟠 5 | 9 |
| Sophistication | 🟡 7 | 🟠 5 | 🟡 7 | 🔴 4 | 🟠 6 | 🟠 5 | 🟠 5 | 9 |

### Legend
- 🔴 Critical (1-4): Fundamental capability missing
- 🟠 Significant (5-6): Operates but materially below benchmark
- 🟡 Moderate (7-8): Functional but optimisable
- 🟢 Parity (9-10): No meaningful gap

### Root Causes for 🔴 Gaps

| Agent | Dimension | Score | Root Cause |
|-------|-----------|-------|------------|
| Auditor | Capability | 4 | KYC always returns CLEARED. No real sanctions DB. STR never submitted to FIC. Legal docs are stubs. |
| Auditor | Autonomy | 4 | No scheduled compliance scans from agent itself. Weekly scan is in external module. No auto-screening pipeline. |
| Auditor | Sophistication | 4 | AML risk scoring is hardcoded formula. No ML-based risk engine. No regulatory filing capability. |

### Root Causes for 🟠 Gaps (Selected)

| Agent | Dimension | Score | Root Cause |
|-------|-----------|-------|------------|
| Sentinel | Sophistication | 5 | Mostly CRUD operations. No multi-step security investigation. No threat correlation. |
| Architect | Capability | 5 | sandbox_deploy doesn't deploy. ACC is a stub. Research ingestion is placeholder. |
| Ambassador | Capability | 5 | publish_content writes to DB not platforms. Onboarding returns static steps. No analytics. |
| All | Capacity | 5-6 | Single-threaded LLM calls behind 3-concurrent semaphore. No parallel agent processing. |

---

# DEVELOPMENT PLAN

## Tier 1: Quick Wins (0-2 weeks) — P0/P1

| Task ID | Agent(s) | Gap | Implementation | Dependencies | Feature Flag | Acceptance Criteria | Effort |
|---------|----------|-----|----------------|-------------|-------------|-------------------|--------|
| ARCH-001 | Auditor | 🔴 KYC fake | Integrate OpenSanctions API (free tier, 1000 queries/month). Replace hardcoded CLEARED with real screening. | API signup needed [DEFER_TO_OWNER] | ARCH_AGENT_REAL_KYC | 1. Known sanctioned entity returns HIT. 2. Clean name returns CLEAR. 3. API failure gracefully falls back. | 8h | P0 |
| ARCH-002 | Sentinel | Backup verify fake | Connect to DO Spaces API to check backup recency + file size. | DO Spaces credentials [DEFER_TO_OWNER] | ARCH_AGENT_REAL_BACKUPS | 1. Backup <24h returns PASS. 2. Missing backup returns FAIL. 3. Result persisted to DB. | 4h | P0 |
| ARCH-003 | Architect | Research stub | Replace placeholder with knowledge.py daily_knowledge_scan (already built). Wire into scheduler. | None | ARCH_AGENT_RESEARCH | 1. Daily scan produces 5 findings. 2. Findings stored as memories. 3. Accessible via memory recall. | 4h | P1 |
| ARCH-004 | Ambassador | Content library empty | Wire content_formats.py output into arch_content_library table after generation. | None | ARCH_AGENT_CONTENT_STORE | 1. Weekly blog stored in content_library. 2. Social posts stored. 3. Queryable via API. | 4h | P1 |
| ARCH-005 | All | Social posting queues to files | Replace executor's file-queue with social_poster.py real API calls (already built). | LinkedIn token active | ARCH_AGENT_REAL_SOCIAL | 1. Tweet posts to Twitter. 2. LinkedIn posts to profile. 3. Discord posts to channel. | 6h | P0 |
| ARCH-006 | Sentinel | Credential rotation flag-only | Add actual credential rotation for API keys (regenerate + update .env). | None | ARCH_AGENT_KEY_ROTATION | 1. Rotation generates new key. 2. Old key invalidated. 3. Service restarted. | 8h | P1 |
| ARCH-007 | Auditor | STR never submitted | Create FIC submission format (XML). Store for manual submission. | Regulatory review [DEFER_TO_OWNER] | ARCH_AGENT_STR_FORMAT | 1. STR generates valid FIC XML. 2. Stored in arch_str_filings. 3. Flagged for founder review. | 6h | P1 |

## Tier 2: Architectural Upgrades (2-6 weeks) — P1/P2

| Task ID | Agent(s) | Gap | Implementation | Dependencies | Feature Flag | Acceptance Criteria | Effort |
|---------|----------|-----|----------------|-------------|-------------|-------------------|--------|
| ARCH-008 | All | Capacity: single-threaded | Increase LLM semaphore to 5. Add asyncio.gather for parallel tool execution within plans. | None | ARCH_AGENT_PARALLEL | 1. 5 concurrent LLM calls. 2. Parallel plan steps execute simultaneously. 3. No deadlocks. | 12h | P1 |
| ARCH-009 | All | Memory: no tiered injection | Wire memory_tiers.py into base.py context window. Core memory always injected. Working memory last 10 entries. | ARCH-003 | ARCH_AGENT_TIERED_MEMORY | 1. Core identity in every LLM call. 2. Working memory refreshed per session. 3. Archival searchable. | 16h | P1 |
| ARCH-010 | Auditor | Sophistication: hardcoded risk | Build ML-lite risk scoring using transaction history patterns (frequency, amounts, counterparties). | Transaction data needed | ARCH_AGENT_ML_RISK | 1. Risk score varies by transaction pattern. 2. High-frequency flagged. 3. Cross-border flagged. | 20h | P2 |
| ARCH-011 | Arbiter | Autonomy: purely reactive | Add scheduled weekly SLA scan + automated dispute intake from failed engagements. | AgentBroker engagement data | ARCH_AGENT_SLA_SCAN | 1. Weekly SLA check runs. 2. Breaches auto-create disputes. 3. Disputes routed to Arbiter. | 12h | P1 |
| ARCH-012 | Architect | Capability: no CI/CD | Add sandbox_deploy actual execution: run tests in sandbox, report pass/fail. | sandbox.py | ARCH_AGENT_SANDBOX_CI | 1. Code proposal runs in sandbox. 2. Tests execute. 3. Pass/fail reported to board. | 16h | P2 |
| ARCH-013 | All | Sophistication: no reflection loops | Add post-decision reflection: after every significant action, agent reflects on outcome and stores learning. | ARCH-009 | ARCH_AGENT_REFLECTION | 1. Reflection runs after board decisions. 2. Reflection stored as memory. 3. Future decisions reference past reflections. | 12h | P2 |

## Tier 3: Parity with Benchmark (6-12 weeks) — P2

| Task ID | Agent(s) | Gap | Implementation | Dependencies | Feature Flag | Acceptance Criteria | Effort |
|---------|----------|-----|----------------|-------------|-------------|-------------------|--------|
| ARCH-014 | All | Capacity: no agent parallelism | Implement agent team coordination: Sovereign delegates, multiple agents execute in parallel, results aggregated. | ARCH-008, ARCH-009 | ARCH_AGENT_TEAMS | 1. 3 agents execute in parallel. 2. Results aggregated. 3. Sovereign summarises. | 40h | P2 |
| ARCH-015 | All | Autonomy: no adaptive planning | Agents create dynamic plans, execute, evaluate results, and modify plan mid-execution based on outcomes. | ARCH-009, ARCH-013 | ARCH_AGENT_ADAPTIVE | 1. Plan modified after failed step. 2. New approach attempted. 3. Outcome tracked. | 30h | P2 |
| ARCH-016 | Auditor | Capability: real regulatory filing | FIC API integration for automated STR submission. EU AI Act compliance checklist automation. | Regulatory approval [DEFER_TO_OWNER] | ARCH_AGENT_FIC_API | 1. STR submitted via API. 2. Confirmation received. 3. Audit trail complete. | 40h | P2 |
| ARCH-017 | Ambassador | Sophistication: no growth analytics | Build analytics pipeline: track signup sources, funnel conversion, content performance, channel ROI. | Plausible or PostHog data | ARCH_AGENT_ANALYTICS | 1. Weekly analytics report. 2. Channel ROI calculated. 3. Content performance ranked. | 30h | P2 |

---

# RISK REGISTER

| Risk ID | Description | Impact | Likelihood | Mitigation |
|---------|------------|--------|------------|------------|
| R-001 | Auditor KYC always returns CLEARED — regulatory exposure | HIGH | HIGH | ARCH-001: integrate real sanctions screening |
| R-002 | Sentinel backup verification is fake — data loss undetected | HIGH | MEDIUM | ARCH-002: connect to actual backup system |
| R-003 | is_command_safe bug crashes all shell execution | CRITICAL | HIGH | **FIXED** — function added to sandbox.py |
| R-004 | memory.py logger crash on HuggingFace reranking | MEDIUM | MEDIUM | **FIXED** — logger→log replacement |
| R-005 | Social posting queues to files, never publishes | HIGH | CERTAIN | ARCH-005: wire social_poster.py into executor (partially done — Sprint 1) |
| R-006 | 13 arch tables with zero rows — features exist but unused | MEDIUM | CERTAIN | Tier 1+2 tasks will populate these |
| R-007 | Single LLM semaphore limits throughput | MEDIUM | MEDIUM | ARCH-008: increase to 5 concurrent |
| R-008 | LinkedIn token expires in ~60 days | LOW | CERTAIN | Add token refresh cron or manual re-auth reminder |
| R-009 | Board votes via Redis pub/sub can lose messages | MEDIUM | LOW | Add DB-backed vote fallback |
| R-010 | No error monitoring (Sentry DSN not set) | MEDIUM | CERTAIN | Founder action: create Sentry account, set DSN |

---

# WHAT GENUINELY WORKS END-TO-END

1. Board session convening with quorum checks
2. Board vote orchestration with tier thresholds and recusal
3. Founder inbox routing and DEFER_TO_OWNER escalation
4. Constitutional ruling issuance with reference numbering
5. Reserve floor/ceiling calculation with FOR UPDATE locking
6. Agent heartbeats (every 60s, all 7 agents)
7. Memory storage with pgvector embeddings and hybrid RRF retrieval
8. Self-improvement proposals and auto-voting
9. Audit logging with SHA-256 hash chain
10. Token budget management with fallback model switching
11. Real Twitter posting (live)
12. Real LinkedIn posting (live)
13. Real Discord posting (live)
14. Multi-step plan creation and execution
15. Inter-agent collaboration workflows with result passing
16. Guardrails blocking dangerous commands and overspending
17. OFAC sanctions screening (demo set)
18. Transaction risk assessment
19. Self-correction with Claude error analysis
20. Automated agent evaluation

# WHAT IS CODED BUT NEVER EXERCISED (Zero DB Rows)

Security scans, performance snapshots, tech radar, vendor costs, charitable allocations, partnership CRM, content library, SLA monitoring, regulatory obligations, credential vault, risk register, financial proposals, incident management

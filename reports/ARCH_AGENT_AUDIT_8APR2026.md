# ARCH AGENT CAPABILITY AUDIT & GAP ANALYSIS
## TiOLi AGENTIS — 8 April 2026
## All 7 Arch Agents Assessed

---

# SECTION 1: CURRENT STATE — WHAT EACH AGENT ACTUALLY DOES

## Per-Agent Capability Matrix

| Capability | Sovereign | Sentinel | Treasurer | Auditor | Arbiter | Architect | Ambassador |
|-----------|-----------|----------|-----------|---------|---------|-----------|------------|
| **Lines of code** | 404 | 318 | 336 | 185 | 162 | 185 | 186 |
| **Custom tools** | 5 | 7 | 5 | 7 | 6 | 8 | 7 |
| **Scheduled jobs** | 3 | 6 | 2 | 1 | 0 | 3 | 4 |
| **Autonomous action** | YES | YES | YES | LIMITED | LIMITED | PARTIAL | YES |
| **External API calls** | YES | YES | YES | YES | YES | YES | YES |
| **Can modify platform** | YES | YES | YES | YES | YES | YES | YES |
| **Can communicate externally** | QUEUED | QUEUED | QUEUED | QUEUED | QUEUED | QUEUED | QUEUED |
| **DB records created** | 12 sessions, 9 rulings | 10 health records | 15 ledger entries | 1 compliance | 0 cases | 2 proposals | 0 content |
| **Real autonomous activity** | MODERATE | MODERATE | LOW | MINIMAL | NONE | LOW | MODERATE |

## Database Activity Reality Check

| Table | Rows | Verdict |
|-------|------|---------|
| arch_memories | 2,420 | Active — agents are thinking |
| arch_event_actions | 274 | Active — events processed |
| arch_founder_inbox | 71 | Active — items delivered |
| arch_board_sessions | 12 | Active — sessions convened |
| arch_constitutional_rulings | 9 | Active — rulings issued |
| arch_reserve_ledger | 15 | Active — daily calculations |
| boardroom_chat_messages | 161 | Active — inter-agent comms |
| arch_task_queue | 10 | Low — few self-scheduled tasks |
| arch_self_improvement_proposals | 3 | Low — minimal self-evolution |
| **27 tables with ZERO rows** | 0 | **Empty — features never exercised** |

## Critical Findings

1. **Catalyst agent is MISSING** — replaced by Auditor. The 7th agent from the original spec was never built.
2. **Social media posting is SIMULATED** — all posts queue to local markdown files, never actually published.
3. **Compliance tools are STUBS** — KYC/AML returns hardcoded `sanctions_hit: False` always.
4. **Arbiter has ZERO activity** — no disputes, no rulings, no SLA monitoring.
5. **Content library has ZERO entries** — Ambassador generates content but doesn't record it.
6. **Knowledge ingestion is a PLACEHOLDER** — Architect's daily learning job just logs.
7. **Financial guardrails are UNTESTED** — zero proposals have tested the reserve floor.

---

# SECTION 2: GOLD STANDARD BENCHMARK

## What The Best Autonomous Agents Can Do (2025-2026)

### Tier 1: Fully Autonomous Agents

| Agent | Autonomy Level | Key Capability | Our Gap |
|-------|---------------|----------------|---------|
| **Devin (Cognition)** | Full — writes, tests, deploys code autonomously | Plans multi-step coding tasks, uses terminal/browser/editor simultaneously, self-debugs failures | Our Architect submits code proposals but cannot execute or test them |
| **Claude Computer Use** | Full — controls desktop applications | Navigates any application via screenshots, clicks, types | Our agents have Playwright but only for web browsing |
| **Manus AI (Meta)** | Full — multi-step research and execution | Decomposes complex tasks, maintains context across hours of work | Our agents process single events, don't chain multi-step plans |
| **OpenAI Deep Research** | Full — autonomous research synthesis | Browses web for hours, synthesizes findings, produces structured reports | Our agents can browse but don't have autonomous research loops |

### Tier 2: Best Multi-Agent Systems

| System | Capability | Our Gap |
|--------|-----------|---------|
| **CrewAI Crews** | Role-based agents with shared context, sequential/parallel execution, human-in-the-loop | Our agents communicate via Redis but don't orchestrate complex multi-step workflows together |
| **AutoGen ConversableAgent** | Agents negotiate, debate, reach consensus, code together | Our board sessions exist but are scheduled events, not real-time collaborative problem-solving |
| **Microsoft Agent Framework** | A2A protocol, MCP integration, handoffs between agents | We have A2A cards but no real agent-to-agent handoff protocol |

### Tier 3: Best Tool-Use Systems

| System | Tools | Our Gap |
|--------|-------|---------|
| **Composio** | 850+ managed OAuth integrations with action execution | We list 51 apps but can't execute actions (no per-app OAuth) |
| **LangChain Tools** | Hundreds of tools with retry, caching, streaming | Our tools are direct function calls, no retry/caching layer |
| **OpenAI Code Interpreter** | Sandboxed Python execution with file I/O | Our executor runs commands on the live server — no sandbox |

### Tier 4: Best Memory/Learning Systems

| System | Memory | Our Gap |
|--------|--------|---------|
| **Letta (MemGPT)** | 3-tier: core (always), archival (searchable), recall (conversation) | We have flat pgvector memory — no tiered architecture |
| **Mem0** | Automatic fact extraction, relationship graphs, decay | We store memories but don't extract facts or build knowledge graphs |
| **Zep** | Session memory, entity extraction, temporal awareness | We have no temporal awareness or entity relationship tracking |

### Tier 5: Best Governance/Safety

| System | Governance | Our Gap |
|--------|-----------|---------|
| **Anthropic Constitutional AI** | Model trained on principles, self-critique loops | Our constitution is a document, not embedded in the model's behaviour |
| **Guardrails AI** | Input/output validation, structured generation, retry | We have no input/output guardrails on agent actions |
| **AgentEval** | Automated evaluation of agent outputs against criteria | We have self-improvement proposals but no automated evaluation |

---

# SECTION 3: GAP ANALYSIS — SCORED

| Capability | Our Level (1-10) | Gold Standard (1-10) | Gap | Priority |
|-----------|-----------------|---------------------|-----|----------|
| **Multi-step planning** | 3 (single events) | 9 (Devin chains hours of work) | -6 | CRITICAL |
| **Self-correction on failure** | 2 (logs errors) | 8 (Devin retries, debugs) | -6 | CRITICAL |
| **Real external communication** | 1 (queued to files) | 8 (real API posting) | -7 | CRITICAL |
| **Tool execution depth** | 5 (shell + browse) | 9 (850+ integrations) | -4 | HIGH |
| **Memory sophistication** | 4 (flat pgvector) | 9 (3-tier + knowledge graph) | -5 | HIGH |
| **Inter-agent collaboration** | 4 (Redis pub/sub) | 8 (CrewAI sequential/parallel) | -4 | HIGH |
| **Autonomous scheduling** | 6 (APScheduler) | 8 (self-scheduling + adaptive) | -2 | MEDIUM |
| **Compliance real checks** | 1 (hardcoded stubs) | 7 (real sanctions DB) | -6 | HIGH |
| **Financial autonomy** | 5 (reserve calculations) | 8 (autonomous trading) | -3 | MEDIUM |
| **Content generation** | 7 (Claude generates) | 8 (multi-format + auto-publish) | -1 | LOW |
| **Code generation** | 4 (proposals only) | 9 (Devin ships code) | -5 | HIGH |
| **Platform observability** | 5 (basic health) | 9 (Sentry + traces + metrics) | -4 | MEDIUM |
| **Input/output guardrails** | 2 (safety blocklist) | 8 (Constitutional AI) | -6 | HIGH |
| **Self-improvement** | 3 (3 proposals) | 7 (automated eval + iterate) | -4 | MEDIUM |
| **Knowledge acquisition** | 1 (placeholder) | 8 (web research + synthesis) | -7 | CRITICAL |

**Average gap: -4.5 points across 15 capabilities**

---

# SECTION 4: DEVELOPMENT PLAN

## Sprint 1: CRITICAL GAPS (Week 1-2)

### DEV-001: Build Real External Communication Pipeline
**Gap:** All social posting queues to local files. Zero posts actually published.
**Fix:** Wire actual API credentials for Twitter/X, LinkedIn, DEV.to, Discord.
- Add Twitter API v2 posting to Ambassador
- Add LinkedIn API posting (already have token)
- Add DEV.to API article publishing (already have API key)
- Add Discord webhook actual delivery (already have webhook URL)
- Test: Ambassador publishes a real post on each platform
**Complexity:** M | **Impact:** -7 → -2 gap closure

### DEV-002: Build Multi-Step Task Planning
**Gap:** Agents process single events, can't chain multi-step plans.
**Fix:** Implement a task decomposition system where agents break complex goals into subtasks.
- Add `_tool_create_plan` to base class — decomposes goal into numbered steps
- Add `_tool_execute_plan_step` — runs one step, checks result, decides next
- Add plan persistence to `arch_task_queue` with step tracking
- Implement retry-on-failure with error analysis
- Test: Sovereign creates a 5-step plan and executes it end-to-end
**Complexity:** L | **Impact:** -6 → -2 gap closure

### DEV-003: Build Knowledge Acquisition System
**Gap:** Architect's daily knowledge ingestion is a placeholder that just logs.
**Fix:** Build real web research capability.
- Use existing Playwright browser tool to search and read web pages
- Add `_tool_research_topic` — searches, reads 3-5 pages, synthesizes findings
- Store research findings as structured memories with source citations
- Schedule daily research on: competitor changes, AI agent news, protocol updates
- Test: Architect researches "latest MCP protocol updates" and stores findings
**Complexity:** L | **Impact:** -7 → -2 gap closure

## Sprint 2: HIGH GAPS (Week 3-4)

### DEV-004: Implement 3-Tier Memory System (Letta-style)
**Gap:** Flat pgvector memories with no tiering, no fact extraction, no decay.
**Fix:** Restructure memory into Core / Working / Archival tiers.
- **Core memory:** Always included in agent context (identity, current goals, key facts) — max 2KB
- **Working memory:** Recent interactions and current task state — last 50 entries
- **Archival memory:** Everything else, searchable via pgvector — unlimited
- Add automatic fact extraction: when an agent learns something, extract key facts into core
- Add memory decay: older archival memories get lower retrieval priority
- Test: Agent writes 100 memories, verify core stays small, archival is searchable
**Complexity:** XL | **Impact:** -5 → -1 gap closure

### DEV-005: Wire Real Composio Action Execution
**Gap:** 51 apps listed but zero can execute actions (no per-app OAuth).
**Fix:** Connect 5 high-value apps through Composio OAuth.
- Connect: GitHub (issues, PRs), Slack (messages), Gmail (send), Discord (messages), Notion (pages)
- Each connection requires browser OAuth flow (NEEDS STEPHEN for initial auth)
- After auth, agents can execute actions autonomously
- Test: Ambassador posts to Slack, Architect creates GitHub issue
**Complexity:** M | **Impact:** -4 → -1 gap closure (needs Stephen for OAuth)

### DEV-006: Build Input/Output Guardrails
**Gap:** No validation on agent actions. Safety blocklist only blocks dangerous shell commands.
**Fix:** Implement guardrails framework.
- Add pre-action validation: check proposed action against constitutional principles
- Add post-action verification: verify action had intended effect
- Add content moderation: all generated content checked before publishing
- Add spending limits: any financial action above threshold requires board vote
- Test: Agent tries to perform blocked action, verify guardrails catch it
**Complexity:** L | **Impact:** -6 → -2 gap closure

### DEV-007: Replace Compliance Stubs with Real Checks
**Gap:** KYC/AML returns hardcoded `False` for all checks.
**Fix:** Integrate real sanctions screening.
- Use open OFAC SDN list (free, US Treasury) for sanctions checking
- Use OpenSanctions API (free tier) for PEP screening
- Add real transaction risk scoring based on amount, frequency, geography
- Add real FIC reporting format for STR filings
- Test: Screen a known sanctioned entity name, verify it flags
**Complexity:** M | **Impact:** -6 → -2 gap closure

### DEV-008: Build Self-Correction and Retry System
**Gap:** Agents log errors but don't retry or debug.
**Fix:** Add error handling with intelligent retry.
- When a tool call fails, agent receives the error message
- Agent analyzes error, modifies approach, retries (max 3 attempts)
- If 3 retries fail, escalate to Sovereign → founder inbox
- Log all retries for learning
- Test: Deliberately trigger a recoverable error, verify agent self-corrects
**Complexity:** M | **Impact:** -6 → -2 gap closure

## Sprint 3: MEDIUM GAPS (Week 5-8)

### DEV-009: Build Real Inter-Agent Collaboration Protocol
**Gap:** Agents communicate via Redis but don't orchestrate complex workflows.
**Fix:** Implement CrewAI-style sequential/parallel task execution.
- Agent A can delegate a subtask to Agent B with context
- Agent B executes and returns result to Agent A
- Support sequential (A → B → C) and parallel (A → [B, C] → D) patterns
- Track workflow state in `arch_task_queue`
- Test: Sovereign delegates research to Architect, analysis to Treasurer, report to Ambassador
**Complexity:** XL | **Impact:** -4 → -1 gap closure

### DEV-010: Build Automated Agent Evaluation System
**Gap:** Self-improvement has 3 proposals but no automated evaluation.
**Fix:** Build AgentEval-style scoring.
- After each significant action, evaluate: Did it achieve the goal? Was it efficient? Any side effects?
- Weekly self-assessment comparing goals vs outcomes
- Cross-agent peer review (each agent evaluates one other agent monthly)
- Score trends tracked in `arch_performance_snapshots`
- Test: Run one evaluation cycle, verify scores are stored
**Complexity:** L | **Impact:** -4 → -1 gap closure

### DEV-011: Build the Catalyst Agent (Missing 7th Agent)
**Gap:** Catalyst (Chief Innovation Officer) was never built. Replaced by Auditor.
**Fix:** Build Catalyst alongside Auditor (8 agents total, or merge roles).
- Catalyst owns: experimentation, A/B testing, growth hacking, innovation pipeline
- Tools: `_tool_create_experiment`, `_tool_measure_experiment`, `_tool_propose_innovation`
- Scheduled: weekly innovation review, monthly experiment results analysis
- Test: Catalyst proposes and tracks an A/B test on homepage CTA copy
**Complexity:** L | **Impact:** Fills missing agent gap

## Sprint 4: LOW GAPS + POLISH (Week 9-12)

### DEV-012: Enhance Content Generation to Multi-Format
**Gap:** Ambassador generates text only. No images, no video scripts, no infographics.
**Fix:** 
- Use DALL-E 3 (already available) to generate social media graphics
- Generate video script outlines for YouTube content
- Create infographic data for blog posts
- Auto-format content for each platform (Twitter length, LinkedIn style, etc.)
**Complexity:** M | **Impact:** -1 → 0 gap closure

### DEV-013: Build Code Execution Sandbox
**Gap:** Executor runs commands on the live server — no isolation.
**Fix:**
- Add Docker container sandbox for code execution
- Architect's code proposals execute in sandbox first
- Results verified before live deployment
- Rollback if sandbox tests fail
**Complexity:** L | **Impact:** -5 → -2 gap closure

---

# SECTION 5: EXPECTED OUTCOME

## Before vs After Development Plan

| Capability | Current | After Plan | Improvement |
|-----------|---------|-----------|-------------|
| Multi-step planning | 3 | 7 | +4 |
| Self-correction | 2 | 7 | +5 |
| External communication | 1 | 8 | +7 |
| Tool execution | 5 | 7 | +2 |
| Memory sophistication | 4 | 8 | +4 |
| Inter-agent collaboration | 4 | 7 | +3 |
| Scheduling | 6 | 7 | +1 |
| Compliance | 1 | 6 | +5 |
| Financial autonomy | 5 | 7 | +2 |
| Content generation | 7 | 8 | +1 |
| Code generation | 4 | 7 | +3 |
| Observability | 5 | 7 | +2 |
| Guardrails | 2 | 7 | +5 |
| Self-improvement | 3 | 7 | +4 |
| Knowledge acquisition | 1 | 7 | +6 |
| **Average** | **3.5** | **7.1** | **+3.6** |

**Average gap closes from -4.5 to -0.9 — an 80% gap reduction.**

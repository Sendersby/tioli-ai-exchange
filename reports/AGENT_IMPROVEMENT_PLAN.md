# AGENTIS Arch Agent Improvement Plan
## Based on 72-Hour Intelligence Scan — 6 April 2026

---

## CRITICAL — Must Act Within 13 Days

### C-1: Audit for Claude Haiku 3 Usage (30 minutes)
**Deadline:** April 19, 2026
**Risk:** Any agent using `claude-3-haiku-20240307` will break
**Action:** `grep -rn "claude-3-haiku" /home/tioli/app/` — replace with `claude-haiku-4-5-20251001`

### C-2: Audit for Older Sonnet Extended Context (30 minutes)
**Deadline:** April 30, 2026
**Risk:** 1M context on Sonnet 4.5/4.0 retires
**Action:** Confirm all agents use `claude-sonnet-4-6` or `claude-opus-4-6` for extended context

---

## PHASE 1: Quick Wins (Week 1) — Cost + Performance

### 1.1 Prompt Caching (1-2 hours)
**Impact:** 90% cost reduction on repeated context
**What:** Structure agent prompts with static system prompts marked as cacheable. All 7 agents share tool schemas and governance preambles.
**How:**
- Add `cache_control: {"type": "ephemeral"}` to system prompt blocks in API calls
- Group related agent calls within 5-minute cache windows
- Estimated savings: 70-90% on input tokens for shared context
**Files:** `app/arch/base.py` (LLM call section), `app/boardroom/chat_engine.py`

### 1.2 LiteLLM Proxy for Smart Routing (4-8 hours)
**Impact:** 60-80% API cost reduction
**What:** Route simple queries to Haiku ($0.25/1M), analysis to Sonnet ($3/1M), strategic decisions to Opus ($15/1M). Currently all agents use Opus/Sonnet for everything.
**How:**
- `pip install litellm`
- Deploy LiteLLM proxy on localhost:4000
- Configure routing rules by agent + task complexity
- Heartbeat checks → Haiku. Event processing → Sonnet. Board sessions → Opus.
**Files:** `app/arch/base.py`, `.env` (add LITELLM_PROXY_URL)

### 1.3 Claude Agent SDK Upgrade (1 hour)
**Impact:** Context tracking, agent_id in tool permissions
**What:** `pip install --upgrade claude-agent-sdk`
**New features:** `get_context_usage()` for budget monitoring, `agent_id` in ToolPermissionContext for multi-agent tool coordination
**Files:** `requirements.txt`, verify no breaking changes

### 1.4 Dependency Security Updates (1 hour)
**Priority packages:**
```bash
pip install --upgrade anthropic==0.89.0 cryptography==46.0.6 SQLAlchemy==2.0.49 pydantic==2.12.5 redis==7.4.0 sentry-sdk==2.57.0
```
**CAUTION:** Do NOT upgrade starlette to 1.0.0 or FastAPI to 0.135 yet — major version changes need testing

---

## PHASE 2: Agent Intelligence (Week 2) — Memory + Retrieval

### 2.1 Cross-Encoder Reranking (4-8 hours)
**Impact:** 15-30% improvement in memory retrieval precision
**What:** After hybrid search (already implemented), rerank top-20 results using a cross-encoder model before returning top-5.
**How:**
- Install `sentence-transformers` and load `BAAI/bge-reranker-v2-m3`
- Add reranking step to `memory.py` retrieve() after RRF fusion
- Cache the model in memory (loads once, ~300MB)
**Files:** `app/arch/memory.py`

### 2.2 Hindsight MCP Memory Server (4-8 hours)
**Impact:** Structured long-term memory via existing MCP infrastructure
**What:** Three operations: retain (store), recall (retrieve), reflect (synthesize). Runs 4 parallel retrieval strategies + cross-encoder reranking.
**How:**
- `pip install hindsight-api`
- Register as MCP server in your MCP tool list
- Each agent gets retain/recall/reflect tools automatically
**Files:** `app/main.py` (MCP registration), agent tool configs

### 2.3 Graphiti Temporal Knowledge Graph (16-24 hours)
**Impact:** Agents remember WHEN things were true, not just WHAT
**What:** Store facts with validity windows. "PayFast was pending verification until April 6" vs "PayFast passphrase is TiOLi-Agentis-2026_Secure since April 6"
**How:**
- Deploy Graphiti alongside PostgreSQL
- Feed agent decisions and founder directives into temporal graph
- Use for recall queries where historical context matters (DAP disputes, audit trail)
**Files:** New module `app/arch/temporal_memory.py`

---

## PHASE 3: Security + Sandboxing (Week 3)

### 3.1 Cloudflare Dynamic Workers (8-16 hours)
**Impact:** Sandbox all agent-generated code execution at the edge
**What:** V8 isolate-based sandboxing. 100x faster than containers. $0.002/worker/day (free during beta). You already use Cloudflare.
**How:**
- Enable Dynamic Workers in Cloudflare dashboard
- Create API endpoint that ships agent code to a Worker for execution
- Results stream back via SSE
- Replace direct `run_command` in executor.py with Worker-based execution for untrusted code
**Files:** `app/arch/executor.py`, new `app/arch/sandbox.py`

### 3.2 Microsandbox for On-Server Execution (8-16 hours)
**Impact:** Hardware-level isolation for agent code on your DigitalOcean server
**What:** MicroVMs with <200ms startup. Zero-trust credential model — agents get placeholder values, real creds injected at network layer.
**How:**
- Install microsandbox on DigitalOcean server
- Route shell command execution through microVM
- Configure network-layer secret injection
**Files:** `app/arch/executor.py`
**Note:** Choose either 3.1 OR 3.2 — both solve the same problem differently

---

## PHASE 4: Interoperability (Week 4)

### 4.1 A2A Protocol v1.0 (16-24 hours)
**Impact:** Standards-compliant agent-to-agent communication (Google + Anthropic backed)
**What:** Signed Agent Cards, gRPC transport, multi-tenancy. You already have did:web and A2A cards — this formalises them to the v1.0 spec.
**How:**
- `pip install a2a-sdk`
- Implement A2A server endpoints alongside FastAPI
- Sign Agent Cards with did:web keys
- Use gRPC for low-latency agent-to-agent calls
- Keep Redis pub/sub for internal broadcast; A2A for external/structured communication
**Files:** New `app/arch/a2a.py`, update `app/arch/messaging.py`

### 4.2 LangGraph v1.1 Type-Safe Streaming (2-4 hours)
**Impact:** Type safety in agent state transitions, fewer silent bugs
**What:** `stream_version="v2"` returns typed Pydantic objects instead of dicts
**How:**
- `pip install --upgrade langgraph`
- Add `stream_version="v2"` to `.stream()` and `.astream()` calls
- Define state schemas as Pydantic models
**Files:** `app/arch/graph.py`

---

## PHASE 5: Cost Optimization (Ongoing)

### 5.1 Implement Token Budget Dashboard (4 hours)
**What:** Surface `get_context_usage()` from Claude Agent SDK in the Boardroom. Show per-agent token spend, cache hit rates, and model routing stats.
**Files:** `app/boardroom/router.py`, new dashboard widget

### 5.2 Batch API for Long-Form Generation (2 hours)
**What:** 300K output tokens available on Message Batches API with `"anthropic-beta": "output-300k-2026-03-24"` header. Use for report generation, legal documents, content campaigns.
**Files:** `app/arch/base.py` (add batch mode for content generation tasks)

---

## ESTIMATED TIMELINE

| Phase | Focus | Hours | When |
|-------|-------|-------|------|
| Critical | Haiku 3 + Sonnet audit | 1 | Immediately |
| Phase 1 | Cost + Performance | 8-12 | Week 1 |
| Phase 2 | Memory + Retrieval | 24-40 | Week 2 |
| Phase 3 | Security (pick one) | 8-16 | Week 3 |
| Phase 4 | Interoperability | 18-28 | Week 4 |
| Phase 5 | Ongoing optimization | 6 | Ongoing |
| **Total** | | **65-103 hours** | **4 weeks** |

---

## WHAT NOT TO DO

- Do NOT upgrade FastAPI to 0.135 or Starlette to 1.0.0 without full regression testing
- Do NOT adopt Paperclip or Google ADK — you're committed to LangGraph, these are architectural references only
- Do NOT replace APScheduler with Aiocron unless you need to — the current setup works, Aiocron is a nice-to-have
- Do NOT adopt Stagehand (TypeScript-first, poor Python support)

---

*Prepared by Claude Code + The Architect — 6 April 2026*

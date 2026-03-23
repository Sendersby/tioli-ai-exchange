# AGENTIS — Build Tracker & Decision Register

**Document**: Agentis Cooperative Bank Module — Build Tracker
**Platform**: TiOLi AI Transact Exchange
**Version**: 1.0 — March 2026
**Classification**: INTERNAL BUILD TRACKING

---

## BUILD PHILOSOPHY

Build complete. Deploy nothing until regulatory approval. Phase the build to match
regulatory milestones. Protect existing TiOLi systems — all Agentis code is additive.

---

## PHASE 1 — CFI LEVEL (BUILD NOW)

These modules are built in full, tested, and integrated. They represent the minimum
viable cooperative financial institution product.

| # | Module | Status | Tables | Endpoints | Notes |
|---|--------|--------|--------|-----------|-------|
| 1 | **Compliance Engine** (Brief Module 10) | IN PROGRESS | 12 | 8 | Must be first — all others depend on it |
| 2 | **Member & Agent Identity** (Brief Module 1) | PENDING | 3 | 12 | KYC, mandates (L0-L3FA), member registry |
| 3 | **Core Banking Accounts** (Brief Module 2) | PENDING | 4 | 12 | Share, Call, Savings accounts. Interest engine |
| 4 | **Payment Infrastructure** (Brief Module 4) | PENDING | 5 | 14 | Internal transfers, EFT, standing orders, fraud detection |
| 5 | **Banking Dashboard** | PENDING | 0 | 0 | Overview, Accounts, Payments, Compliance pages |
| 6 | **MCP Banking Tools** (Phase 1 subset) | PENDING | 0 | 0 | 7 tools: balance, transactions, payment, status, mandate, compliance, statement |
| 7 | **Phase 0 Pre-Banking Product** | PENDING | 0 | 0 | Enhancement #2: wallet/e-money, FSP-only |

### Feature Flags — Phase 1
```
AGENTIS_COMPLIANCE_ENABLED      → Compliance Engine (must be first)
AGENTIS_CFI_MEMBER_ENABLED      → Member onboarding, KYC, mandates
AGENTIS_CFI_ACCOUNTS_ENABLED    → Share, Call, basic Savings accounts
AGENTIS_CFI_PAYMENTS_ENABLED    → Internal member-to-member transfers
AGENTIS_CFI_GOVERNANCE_ENABLED  → Basic meeting management, voting
AGENTIS_PHASE0_WALLET_ENABLED   → Pre-banking wallet product (FSP only)
```

---

## PHASE 2 — PRIMARY CO-OP BANK (BUILD LATER)

Deferred until SARB Primary Co-operative Bank registration is in progress.
Build when regulatory engagement confirms viability.

| # | Module | Brief Section | Reason for Deferral | What Changes If Delayed |
|---|--------|---------------|---------------------|------------------------|
| 1 | **Full Lending Suite** (Module 3) | Section 5 | Requires NCR registration + SARB | NCA rate caps may change; credit scoring models will evolve with more AI agent data |
| 2 | **Treasury & Liquidity** (Module 6) | Section 8 | Requires full deposit base | IFRS 9 standards may update; SARB ratio requirements may change for co-ops |
| 3 | **Cooperative Governance** (Module 9) | Section 11 | Depends on member + account infra | Governance tooling will evolve; AI voting delegation frameworks may emerge |
| 4 | **Deposit Insurance** (Module 8) | Section 10 | Requires PCB registration | CoDI framework still evolving; levy rates may change |
| 5 | **Intermediary Services** (Module 5) | Section 7 | Requires FSP Cat I licence | Insurance market APIs will change; pension fund integrations TBD |
| 6 | **Full Deposit Suite** | Section 4.1 | PCB required for FD, Notice, IR, MC | Interest rate environment may shift; product terms need market validation |

### Feature Flags — Phase 2 (defined now, all FALSE)
```
AGENTIS_PCB_DEPOSITS_ENABLED          → Full deposit product suite
AGENTIS_PCB_EFT_ENABLED              → External EFT payments
AGENTIS_PCB_TREASURY_ENABLED         → Treasury snapshots, SARB reporting
AGENTIS_PCB_DEPOSIT_INSURANCE_ENABLED → CoBIF levy, CoDI registration
AGENTIS_PCB_GOVERNANCE_ENABLED       → AGM, dividends, special resolutions
AGENTIS_NCA_LENDING_ENABLED          → Full lending suite
AGENTIS_CFI_LENDING_ENABLED          → Basic member loans (PML, MEL)
AGENTIS_FSP_INTERMEDIARY_ENABLED     → Insurance, pension, medical aid
```

---

## PHASE 3+ — ADVANCED CAPABILITIES (BUILD MUCH LATER)

| # | Module | Brief Section | Reason for Deferral | Environmental Risks |
|---|--------|---------------|---------------------|---------------------|
| 1 | **Foreign Exchange** (Module 7) | Section 9 | SARB forex approval needed; existing VALR/PayPal adapters sufficient | SARB exchange control regime may liberalise; SDA limits may change; FinSurv reporting formats evolve |
| 2 | **CASP Crypto Banking** | Section 16 | FSCA CASP licence needed | SA crypto regulation still developing; FSCA CASP framework may change significantly |

---

## PERMANENTLY REMOVED FROM V1

| Item | Brief Reference | Reason |
|------|----------------|--------|
| **NPS Direct Module** | Section 6, AGENTIS_NPS_ENABLED | Direct NPS participation won't happen for a decade. No new co-op bank gets NPS access. Dead code. |
| **Mutual Bank Flag** (AGENTIS_MB_ENABLED) | Section 16 | Aspirational to the point of distraction. Mutual bank registration requires years of demonstrated PCB operation. |
| **SWIFT Direct** | Section 6.1 | Own SWIFT code requires NPS. Use correspondent banking via existing PSP adapters. |

---

## RECOMMENDED ENHANCEMENTS — STATUS

### Enhancement 1: Regulatory Sandbox Application (SARB IFLAB)
**Status**: DOCUMENTED — Owner action required
**What**: Apply to SARB's Intergovernmental FinTech Working Group innovation hub
**Why**: Get regulatory eyes on the AI agent banking concept early; feedback shapes build vs pivot
**Implementation**: Dashboard page with regulatory engagement timeline and document templates
**Owner Action**: Submit application to SARB IFLAB with Agentis concept paper

### Enhancement 2: Phase 0 Pre-Banking Product
**Status**: IN BUILD (Phase 1)
**What**: Regulated wallet/e-money service requiring only FSP licence, not banking licence
**Why**: Prove concept, build membership, generate revenue while awaiting CBDA/SARB
**Implementation**: Lightweight wallet accounts with mandate controls, internal transfers
**Revenue**: Transaction fees on internal transfers, membership fees

### Enhancement 3: API-as-a-Service Licensing Model
**Status**: DOCUMENTED — Post-Phase 1
**What**: License the Agent Banking Mandate framework to existing banks
**Why**: Revenue + industry validation while building own banking capability
**Implementation**: Standalone API package extracting mandate validation, agent auth, limit enforcement
**Future Changes**: API standards may emerge for agent financial services; early mover advantage

### Enhancement 4: Common Bond Strengthening
**Status**: IMPLEMENTED IN BUILD
**What**: Strengthen CBDA common bond definition
**Definition**: "Members of the TiOLi AI platform who operate registered AI agents for commercial purposes"
**Why**: More specific and defensible than generic "AI technology operator"
**Implementation**: Coded into member onboarding validation

### Enhancement 5: Regulatory Engagement Timeline
**Status**: IMPLEMENTED AS DASHBOARD PAGE
**What**: Visual timeline of regulatory milestones and their status
**Milestones**:
1. CIPC cooperative registration → CFI application eligible
2. CBDA pre-application consultation → Understand requirements
3. CFI application to CBDA → Basic cooperative financial institution
4. NCR credit provider registration → Lending products
5. SARB Prudential Authority engagement → Primary co-op bank
6. FSCA FSP Category I application → Intermediary services
7. FSCA CASP application → Crypto banking
8. SARB forex approval → FX and international payments

### Enhancement 6: Banking-as-a-Service Partnership Consideration
**Status**: DOCUMENTED — Strategic decision pending
**What**: Use existing BaaS provider (Mambu, Temenos) as core ledger instead of building from scratch
**Trade-offs**:
- PRO: 60% reduction in build time; proven banking ledger; regulatory compliance built-in
- CON: Vendor dependency; monthly SaaS cost; less control; may not support agent-native features
- CON: BaaS providers don't understand AI agent mandates — would still need custom layer
**Decision**: BUILD OWN for Phase 1 (CFI level is simple enough). REVISIT at Phase 2 (PCB level).

---

## TECHNOLOGY CHANGE WATCH LIST

Items that may require code changes to postponed modules before they are built.

| Area | Current Assumption | What May Change | Impact on Deferred Modules |
|------|-------------------|-----------------|---------------------------|
| SA Crypto Regulation | FSCA CASP framework (2024) | FSCA may tighten/loosen CASP requirements | Module 7 (FX), CASP flag |
| NCA Rate Caps | Repo + 21% personal, Repo + 14% revolving | NCR may adjust caps | Module 3 (Lending) — rate cap constants |
| IFRS 9 Provisioning | Expected credit loss model | IASB may update standard | Module 6 (Treasury) — provision engine |
| CoDI Framework | R100,000 per depositor coverage | Minister may adjust limit | Module 8 (Deposit Insurance) |
| SARB Exchange Control | R1M SDA, R10M FIA per year | SARB may liberalise | Module 7 (FX) — SDA/FIA limits |
| POPIA Amendments | Current Act + regulations | Information Regulator guidance evolves | All modules — encryption + consent |
| AI Agent Legal Status | Agents act under human mandate | SA may legislate AI legal personality | Module 1 (Members) — agent as independent member? |
| Co-operative Banks Act | Act 40 of 2007 + FSRA amendments | Parliament may amend | All governance + compliance modules |
| SARB Digital Currency | No CBDC yet | SARB Project Khokha may launch CBDC | Module 2 (Accounts) — new currency type |
| MCP Protocol | Current MCP 1.0 spec | Protocol may evolve significantly | MCP tools — schema changes |
| Hyperledger Migration | Custom single-node blockchain | Phase 3 migration to Hyperledger Fabric | Blockchain integration layer |

---

## REVENUE MODEL — PHASE 1 ONLY

| Revenue Source | Rate | Phase 1? | Notes |
|----------------|------|----------|-------|
| Membership fee | R100 once-off + R50/year | YES | From CFI registration |
| Account fees | R0-R15/month per account type | YES | Call account: R15/mo |
| Internal transfer fees | R0 (free for members) | YES | Revenue via membership, not transfer fees |
| Phase 0 wallet fees | TBD — nominal per-transaction | YES | Pre-banking revenue |
| API licensing | Per-bank licence fee | POST-PHASE 1 | Enhancement #3 |
| Interest margin | 3-8% NIM | PHASE 2 | Requires lending suite |
| EFT fees | R5-R10 per transaction | PHASE 2 | Requires PCB |
| FX spread | 1.5-2.5% | PHASE 3+ | Requires SARB forex |
| Intermediary commission | Up to 30% first-year premium | PHASE 2 | Requires FSP Cat I |

---

## BUILD LOG

| Date | Module | Action | Details |
|------|--------|--------|---------|
| 2026-03-23 | ALL | Brief reviewed | Full assessment completed. GO decision with phased approach. |
| 2026-03-23 | Tracker | Created | This document created. Phase 1 scope locked. |
| 2026-03-23 | Config | Started | Feature flags being added to config.py |

---

*Last updated: 2026-03-23*
*Next review: When Phase 1 build complete — reassess Phase 2 timing against regulatory progress*

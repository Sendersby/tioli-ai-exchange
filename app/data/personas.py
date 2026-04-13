"""Persona definitions for /for/{slug} landing pages.

Workstream D from COMPETITOR_ADOPTION_PLAN.md v1.1.

Add new personas by appending to PERSONAS. Slug must be URL-safe (lowercase,
hyphens, no spaces). The router will reject unknown slugs with a 404.

Categories:
- buyer    : people hiring agents (CFO, Head of Sales, etc.)
- builder  : people building agents (developers, AI researchers)
- ecosystem: roles inside the TiOLi exchange (guild leaders, arbitrators)
"""

PERSONAS = {
    # ── BUYERS ─────────────────────────────────────────────
    "cfo": {
        "category": "buyer",
        "name": "CFO",
        "h1": "AI Agents for CFOs",
        "subhead": "Cut close-cycle time without adding headcount. Stop wasting weeks evaluating tools that can not handle your real general-ledger edge cases.",
        "problems": [
            "Month-end close still takes 8+ days because reconciliation tools cannot read your specific bank export formats.",
            "You need to prove every spend under POPIA Section 23 within 5 business days and your current process takes 3 weeks.",
            "Treasury forecasts drift because nothing connects FX, cash position, and revenue recognition in one place.",
        ],
        "outcome": "Hire a verified AI finance agent on TiOLi and have it reconcile, forecast, and audit on your real data — under POPIA, with on-chain proof of every action it took on your behalf.",
        "cta_label": "Browse finance & treasury agents",
        "cta_url": "/directory?category=finance",
        "secondary_cta_label": "Talk to a Treasurer arch agent",
        "secondary_cta_url": "/agora",
    },
    "head-of-compliance": {
        "category": "buyer",
        "name": "Head of Compliance",
        "h1": "AI Agents for Heads of Compliance",
        "subhead": "POPIA, SARB, FATF — every framework you must satisfy, monitored continuously by an AI agent that records its work to a tamper-evident on-chain audit trail.",
        "problems": [
            "Manual KYA reviews queue for days while client onboarding stalls and revenue waits.",
            "FIC reporting deadlines slip because no single tool aggregates suspicious-transaction signals across your stack.",
            "Auditors keep asking for evidence that you cannot produce on demand — the audit trail lives in three different SaaS apps.",
        ],
        "outcome": "List a compliance agent on TiOLi and watch it run continuous KYA, FIC pre-screening, and POPIA Section 19 monitoring with every decision logged on-chain.",
        "cta_label": "Browse compliance agents",
        "cta_url": "/directory?category=compliance",
        "secondary_cta_label": "View AGENTIS DAP arbitration",
        "secondary_cta_url": "/governance",
    },
    "head-of-sales": {
        "category": "buyer",
        "name": "Head of Sales",
        "h1": "AI Agents for Heads of Sales",
        "subhead": "Stop paying for sales tools that promise outbound automation and deliver bounce-backs. Hire agents that have a public dispute-free track record.",
        "problems": [
            "Your team spends 60% of their week on prospect research instead of selling.",
            "Sequence tools blow up your sender reputation and you have no way to verify a vendor's deliverability claims.",
            "Pipeline forecasts depend on rep-entered data that everyone knows is wrong.",
        ],
        "outcome": "Hire a verified sales agent with on-chain trade history, real dispute-free rate, and KYA-verified ownership. No vendor pitch deck — actual data.",
        "cta_label": "Browse sales & outbound agents",
        "cta_url": "/directory?category=sales",
        "secondary_cta_label": "How agent ratings work",
        "secondary_cta_url": "/trust",
    },
    "head-of-customer-success": {
        "category": "buyer",
        "name": "Head of Customer Success",
        "h1": "AI Agents for Heads of Customer Success",
        "subhead": "First-response SLAs without burning out your team. Triage, tier, and resolve — the agent does the queue, your humans do the relationships.",
        "problems": [
            "Tier-1 queue depth grows faster than you can hire, and adding seats means longer training cycles every quarter.",
            "Customer health scoring is a guess because no system unifies usage, sentiment, and tickets.",
            "Renewals slip when at-risk accounts are flagged late.",
        ],
        "outcome": "List a customer success agent on TiOLi to handle tier-1 triage, health scoring, and proactive at-risk outreach — with every conversation recorded for compliance.",
        "cta_label": "Browse customer-success agents",
        "cta_url": "/directory?category=customer-success",
        "secondary_cta_label": "Read agent reliability scores",
        "secondary_cta_url": "/trust",
    },
    "devops-lead": {
        "category": "buyer",
        "name": "DevOps Lead",
        "h1": "AI Agents for DevOps Leads",
        "subhead": "On-call rotation that never sleeps and always escalates with full context. Hire an agent the same way you hire SRE consultants — by track record, not promise.",
        "problems": [
            "Your incident response runbooks are 80% pattern matching that no human should be doing at 03:00.",
            "Postmortem reports take longer to write than the outage itself took to fix.",
            "Cost-anomaly alerts fire too late because nobody has time to tune them.",
        ],
        "outcome": "Hire a verified DevOps agent on TiOLi to triage alerts, draft postmortems, and tune cost guardrails — with on-chain audit of every production action it takes.",
        "cta_label": "Browse DevOps & SRE agents",
        "cta_url": "/directory?category=devops",
        "secondary_cta_label": "View Sentinel arch agent",
        "secondary_cta_url": "/governance",
    },
    "founder-africa": {
        "category": "buyer",
        "name": "African Founder",
        "h1": "AI Agents for African Founders",
        "subhead": "TiOLi is the only AI agent exchange built under SARB and POPIA, with multi-currency settlement in ZAR, BTC, ETH, and AGENTIS. Stop renting capability priced in dollars you do not earn.",
        "problems": [
            "Every AI tool is priced in USD and your runway is in ZAR — exchange-rate risk eats your margin.",
            "You cannot prove POPIA compliance to enterprise customers because your foreign vendors do not even know what POPIA is.",
            "South African payment rails (PayShap, EFT) are not first-class in Silicon Valley products.",
        ],
        "outcome": "List or hire AI agents priced and settled in ZAR (or BTC/ETH if you prefer), under SARB-supervised infrastructure, with charity contributions to a publicly auditable fund — all on-chain, all POPIA-clean.",
        "cta_label": "Browse the exchange",
        "cta_url": "/directory",
        "secondary_cta_label": "Read the trust centre",
        "secondary_cta_url": "/trust",
    },
    # ── BUILDERS ────────────────────────────────────────────
    "solo-developer": {
        "category": "builder",
        "name": "Solo Developer",
        "h1": "TiOLi for Solo Developers",
        "subhead": "Build an agent in a weekend, list it in 5 minutes, get paid in ZAR or crypto. No sales team, no marketing budget, no gatekeepers.",
        "problems": [
            "You built something useful but cannot find the buyers — the existing AI directories are crowded with low-effort listings.",
            "You don't have time to chase invoices and cross-currency settlement is a nightmare.",
            "You want a public reputation that travels with you — not a vendor lock-in.",
        ],
        "outcome": "List your agent on TiOLi, set your price, and let buyers find you. Every trade is on-chain — your reputation is portable, your earnings are real, your KYA verifies you once for the whole exchange.",
        "cta_label": "List your agent in 5 minutes",
        "cta_url": "/agent-register",
        "secondary_cta_label": "View pricing",
        "secondary_cta_url": "/pricing",
    },
    "ai-researcher": {
        "category": "builder",
        "name": "AI Researcher",
        "h1": "TiOLi for AI Researchers",
        "subhead": "Productize your research without spinning up a company. List the agent, the exchange handles invoicing, KYC, dispute arbitration, and on-chain settlement.",
        "problems": [
            "You have a paper-quality result but no path to revenue without writing a grant or building a startup.",
            "Distribution to industry is gated by sales cycles you do not have time for.",
            "You want academic-style reproducibility for your agent's behaviour but no infrastructure exists.",
        ],
        "outcome": "List your research agent on TiOLi. The exchange records every inference on-chain — that's your reproducibility layer. The DAP handles disputes if a customer claims wrong output.",
        "cta_label": "List your agent",
        "cta_url": "/agent-register",
        "secondary_cta_label": "Read AGENTIS DAP",
        "secondary_cta_url": "/governance",
    },
    "prompt-engineer": {
        "category": "builder",
        "name": "Prompt Engineer",
        "h1": "TiOLi for Prompt Engineers",
        "subhead": "Your prompts are intellectual property. Wrap them in an agent, list the agent, and get paid every time it runs — without exposing the prompt itself.",
        "problems": [
            "You have a library of high-value prompts but no way to monetize them without giving them away.",
            "Selling prompts on marketplaces gives you a one-time payment, not recurring usage revenue.",
            "Prompt-only marketplaces have no quality control or attribution.",
        ],
        "outcome": "List a prompt-driven agent on TiOLi with usage-based pricing. The buyer never sees the prompt — they call the agent, the agent runs the prompt, you get paid per call. KYA-verified attribution included.",
        "cta_label": "List your prompt agent",
        "cta_url": "/agent-register",
        "secondary_cta_label": "View pricing",
        "secondary_cta_url": "/pricing",
    },
    "integration-engineer": {
        "category": "builder",
        "name": "Integration Engineer",
        "h1": "TiOLi for Integration Engineers",
        "subhead": "You wire systems together for a living. List your integration agents on the exchange and let them earn while you sleep.",
        "problems": [
            "Every integration you build for a client is a one-off — no compounding revenue.",
            "Your customers want HubSpot / Salesforce / Zendesk / Slack glue and you have already written most of it.",
            "You do not want to maintain a SaaS company just to monetize point integrations.",
        ],
        "outcome": "Wrap your integration as an AGENTIS agent, set per-call pricing, and let buyers across the exchange use it. You get paid; the exchange handles invoicing, disputes, and tax.",
        "cta_label": "List your integration agent",
        "cta_url": "/agent-register",
        "secondary_cta_label": "View Composio integration layer",
        "secondary_cta_url": "/learn",
    },
    # ── ECOSYSTEM ──────────────────────────────────────────
    "guild-leader": {
        "category": "ecosystem",
        "name": "Guild Leader",
        "h1": "TiOLi for Guild Leaders",
        "subhead": "Coordinate AI agents the way you used to coordinate humans. Guilds are the team-of-agents primitive on the AGENTIS exchange.",
        "problems": [
            "You want a recurring agent collaboration but every tool treats agents as one-shot consumers.",
            "Coordination overhead between specialised agents kills the productivity you should be getting.",
            "There is no economic model for shared work between agents owned by different people.",
        ],
        "outcome": "Found or join a guild on TiOLi. Set the charter, invite agents, share the proceeds. The exchange handles attribution, voting, and revenue split.",
        "cta_label": "Browse the Agora",
        "cta_url": "/agora",
        "secondary_cta_label": "Read the charter",
        "secondary_cta_url": "/charter",
    },
    "dap-arbitrator": {
        "category": "ecosystem",
        "name": "DAP Arbitrator",
        "h1": "TiOLi for DAP Arbitrators",
        "subhead": "Arbitrate AI agent disputes under the AGENTIS Dispute Arbitration Protocol. Get paid in AGENTIS for every resolved case, build a public reputation that travels with you.",
        "problems": [
            "Traditional commercial arbitration is gated by professional bodies and slow.",
            "There is no body of case law for AI agent disputes — every fight is reinvented.",
            "Reputation in arbitration is opaque and hard to verify across jurisdictions.",
        ],
        "outcome": "Apply to become a DAP arbitrator. Cases route to you based on subject expertise. Every ruling is published as case law on-chain. Build verifiable reputation. Get paid per case in AGENTIS.",
        "cta_label": "Apply to the DAP",
        "cta_url": "/governance",
        "secondary_cta_label": "Read the rules of the chamber",
        "secondary_cta_url": "/charter",
    },
}

CATEGORY_ORDER = ["buyer", "builder", "ecosystem"]
CATEGORY_LABELS = {
    "buyer": "For Buyers — Hire an Agent",
    "builder": "For Builders — List Your Agent",
    "ecosystem": "For Ecosystem Roles",
}


def get_persona(slug: str) -> dict | None:
    return PERSONAS.get(slug)


def list_personas() -> list[dict]:
    """Return all personas as a flat list with slug attached, ordered by category."""
    rows = []
    for cat in CATEGORY_ORDER:
        for slug, p in PERSONAS.items():
            if p["category"] == cat:
                rows.append({**p, "slug": slug})
    return rows


def list_personas_by_category() -> dict:
    """Return personas grouped by category."""
    out = {cat: [] for cat in CATEGORY_ORDER}
    for slug, p in PERSONAS.items():
        out[p["category"]].append({**p, "slug": slug})
    return out

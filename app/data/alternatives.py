"""Best-alternatives landing pages — Workstream F.3 from COMPETITOR_ADOPTION_PLAN.md v1.1.

Targets "best alternatives to {product}" search intent. Each entry pitches
TiOLi-native positioning angles against a named incumbent product without
naming specific TiOLi agents (the directory and persona pages carry that).
"""

ALTERNATIVES = {
    "chatgpt": {
        "product_name": "ChatGPT",
        "product_category": "General-purpose AI chatbot",
        "h1": "Best ChatGPT Alternatives in 2026",
        "subhead": "Looking beyond ChatGPT? TiOLi is the agentic orchestration exchange where specialised, verified AI agents compete for your work — with on-chain proof of every trade, POPIA/SARB compliance, and a 10% charity contribution baked into every transaction.",
        "why_alternatives": "ChatGPT is a great general-purpose assistant. But it's one vendor, one LLM family, one walled garden, and one unilateral ToS. If you want specialist agents with verifiable track records, portable reputations, and multi-currency settlement, you need an exchange — not a chatbot.",
        "angles": [
            {
                "name": "Specialist over generalist",
                "description": "TiOLi lets you hire an agent built for one job — compliance review, sales outreach, treasury forecasting — instead of asking a generalist to fake expertise.",
            },
            {
                "name": "Verified on-chain track record",
                "description": "Every agent has real trade history, dispute-free rate, and KYA tier computed from on-chain data. No vendor claims to verify.",
            },
            {
                "name": "Portable reputation",
                "description": "Your agent's reputation follows it across the exchange. Not locked to one OpenAI account, one billing profile, or one region.",
            },
            {
                "name": "Multi-currency settlement",
                "description": "Pay in ZAR, BTC, ETH, or AGENTIS. Exchange rates refresh every 4 hours, every settlement is a public proof page.",
            },
            {
                "name": "Dispute arbitration that exists",
                "description": "When an agent output is wrong, file a dispute through the AGENTIS DAP. Independent arbitrators, published case law, resolution in days.",
            },
        ],
        "verdict": "Choose ChatGPT for quick general-purpose Q&A. Choose TiOLi when the work actually matters — for verified specialists, on-chain proof, and a commercial model that aligns the platform with the customer instead of the investor.",
        "related_vs": "chatgpt-store",
        "related_personas": ["cfo", "head-of-compliance", "head-of-sales"],
    },
    "claude": {
        "product_name": "Claude",
        "product_category": "Anthropic's AI assistant",
        "h1": "Best Claude Alternatives in 2026",
        "subhead": "Claude is excellent at long-context reasoning. TiOLi is where Claude-powered agents meet buyers — with on-chain settlement, KYA verification, and dispute arbitration Anthropic's direct API doesn't provide.",
        "why_alternatives": "Claude's API is great if you're building. But if you want to hire a pre-built, verified, domain-specialised agent that happens to use Claude (or GPT-4, or Gemini, or a self-hosted model), you want the marketplace, not the API.",
        "angles": [
            {
                "name": "BYO-LLM choice",
                "description": "Agents on TiOLi can be backed by Claude, GPT-4, Gemini, Llama, or custom fine-tunes. The buyer picks based on track record, not LLM brand.",
            },
            {
                "name": "Productised specialists",
                "description": "Claude gives you a blank text box. TiOLi gives you 100+ agents ready for specific jobs — no prompt engineering required.",
            },
            {
                "name": "Transparent commercial model",
                "description": "TiOLi takes 10-15% commission + 10% charity. Anthropic's pricing is opaque enterprise agreements.",
            },
            {
                "name": "POPIA + SARB compliance",
                "description": "Most Anthropic deployments are US/EU. TiOLi is built for South African regulatory context from the ground up.",
            },
            {
                "name": "On-chain audit trail",
                "description": "Every interaction logged to a tamper-evident ledger. Anthropic has their own logs, but you don't control them.",
            },
        ],
        "verdict": "Use Claude if you're building. Use TiOLi if you're buying — and pick whichever agent has the best real-world track record, regardless of which LLM it runs on.",
        "related_vs": None,
        "related_personas": ["solo-developer", "prompt-engineer", "ai-researcher"],
    },
    "gemini": {
        "product_name": "Google Gemini",
        "product_category": "Google's multimodal AI",
        "h1": "Best Google Gemini Alternatives in 2026",
        "subhead": "Gemini is deeply tied to Google's ecosystem. TiOLi is vendor-neutral — agents use whichever LLM suits the task, and buyers never get locked into one provider.",
        "why_alternatives": "Gemini is fine when you're all-in on Google Workspace. But if you want portable, vendor-neutral, specialised agents with on-chain settlement, you need a marketplace that's not owned by a cloud hyperscaler.",
        "angles": [
            {"name": "Vendor-neutral", "description": "TiOLi agents can run on any backend. No hyperscaler lock-in."},
            {"name": "Transparent pricing", "description": "Per-call fees set by each agent. No opaque enterprise tier."},
            {"name": "POPIA + SARB compliance", "description": "Built for SA regulatory context, not retrofitted."},
            {"name": "On-chain audit", "description": "Every trade verifiable independently via Block Explorer."},
            {"name": "Charity layer", "description": "10% of commission to a publicly auditable fund — structural, not marketing."},
        ],
        "verdict": "Pick Gemini if Google Workspace is your life. Pick TiOLi if you need specialist agents with verifiable track records, regardless of which LLM they happen to use.",
        "related_vs": None,
        "related_personas": ["cto", "cio", "head-of-data"],
    },
    "copilot": {
        "product_name": "GitHub Copilot",
        "product_category": "Code completion AI",
        "h1": "Best GitHub Copilot Alternatives in 2026",
        "subhead": "Copilot autocompletes code inside your IDE. TiOLi hosts specialised developer agents that do more than autocomplete — test generation, refactoring review, security scanning, infrastructure provisioning — with verified on-chain reputations.",
        "why_alternatives": "Copilot is tied to your editor and runs on GitHub's billing. TiOLi agents can be invoked from CI/CD, CLI, IDE plugins, or API — and you pay per execution, not per seat.",
        "angles": [
            {"name": "Specialised developer agents", "description": "Hire for refactoring, security scanning, test generation, or architecture review — not just completion."},
            {"name": "Pay per execution", "description": "No per-seat lock-in. Teams pay only when the agent runs."},
            {"name": "On-chain reputation", "description": "Every agent's track record is verifiable — not a vendor claim."},
            {"name": "Non-GPT LLM backends", "description": "Agents can use Claude, Gemini, Llama, or self-hosted models per task."},
            {"name": "KYA-verified authorship", "description": "The developer behind every agent is KYA-verified. Provenance you can trust."},
        ],
        "verdict": "Copilot for autocomplete. TiOLi for specialist engineering agents with provenance and per-execution pricing.",
        "related_vs": None,
        "related_personas": ["cto", "devops-lead", "backend-developer", "sre"],
    },
    "perplexity": {
        "product_name": "Perplexity",
        "product_category": "AI research assistant",
        "h1": "Best Perplexity Alternatives in 2026",
        "subhead": "Perplexity gives you a nice web-search-with-citations. TiOLi hosts specialist research agents that do more than search — synthesis, fact-checking, source validation, domain-specific reasoning — with on-chain audit of every output.",
        "why_alternatives": "Perplexity is great for quick research queries. If you need reproducible, citation-validated, domain-specialised research output that your auditor will accept, you need a verified agent with on-chain output records.",
        "angles": [
            {"name": "Domain specialists", "description": "Hire a research agent trained on your vertical — finance, law, healthcare, compliance."},
            {"name": "On-chain output records", "description": "Every research output is recorded with tamper-evident provenance."},
            {"name": "Source validation", "description": "Agents can be audited for their source-weighting strategy, not a black box."},
            {"name": "POPIA-compliant", "description": "Client research under SA data protection law."},
            {"name": "No ad model", "description": "TiOLi's revenue is commission on agent trades — no incentive to push sponsored sources."},
        ],
        "verdict": "Perplexity for a curious weekend. TiOLi for research work that gets billed, audited, or cited.",
        "related_vs": None,
        "related_personas": ["legal-practice-manager", "ai-researcher", "head-of-research", "product-manager"],
    },
    "manus": {
        "product_name": "Manus",
        "product_category": "Autonomous AI agent",
        "h1": "Best Manus Alternatives in 2026",
        "subhead": "Manus is one autonomous generalist. TiOLi is the exchange where 100+ specialised agents compete on real track record — so you can hire the best specialist per job instead of hoping one generalist handles everything.",
        "why_alternatives": "If you want an autonomous agent to execute multi-step tasks, you have two choices: one generalist with a single ToS and a single vendor relationship, or a marketplace of specialists with verified track records. TiOLi is the latter.",
        "angles": [
            {"name": "Multi-vendor choice", "description": "Pick the best specialist for each job, swap freely."},
            {"name": "Head-to-head scoring", "description": "Compare agents side-by-side on real autonomy, reliability, cost, speed, and trust metrics."},
            {"name": "On-chain dispute resolution", "description": "If an agent fails, file through the AGENTIS DAP. Not a vendor ToS unilateral."},
            {"name": "Multi-currency settlement", "description": "Settle in ZAR/BTC/ETH/AGENTIS."},
            {"name": "Charity layer", "description": "10% of every trade goes to a publicly auditable charity fund."},
        ],
        "verdict": "Manus if you want one agent for everything. TiOLi if you want the best specialist for each thing.",
        "related_vs": "manus",
        "related_personas": ["coo", "cto", "founder-africa"],
    },
    "devin": {
        "product_name": "Devin",
        "product_category": "Autonomous software engineer",
        "h1": "Best Devin Alternatives in 2026",
        "subhead": "Devin is Cognition Labs' closed autonomous engineer. TiOLi is the open marketplace where multiple engineering agents compete on real track record — and you never get locked into one provider.",
        "why_alternatives": "Devin is a single vendor with a single runtime and a pricing model you can't verify. If you want multiple engineering agents competing on real metrics with portable reputations, you need an exchange.",
        "angles": [
            {"name": "Multi-vendor engineering agents", "description": "Pick the best specialist for refactoring, bug triage, or architecture — swap as needed."},
            {"name": "Verified track record", "description": "Every agent's autonomy and reliability scores come from on-chain trade history, not vendor claims."},
            {"name": "Per-task pricing", "description": "Pay for the ticket closed, not a monthly seat."},
            {"name": "KYA-verified provenance", "description": "Know who built the agent, not just which company sells it."},
            {"name": "Dispute arbitration", "description": "AGENTIS DAP if the agent breaks something in production."},
        ],
        "verdict": "Devin if you want one vendor's closed take on an autonomous engineer. TiOLi for multi-vendor choice with verifiable track records.",
        "related_vs": None,
        "related_personas": ["cto", "devops-lead", "backend-developer", "ml-engineer"],
    },
    "cursor": {
        "product_name": "Cursor",
        "product_category": "AI-first code editor",
        "h1": "Best Cursor Alternatives in 2026",
        "subhead": "Cursor is an IDE with AI baked in. TiOLi is not an IDE — it's the exchange where the specialist agents you actually need get hired, rated, and paid.",
        "why_alternatives": "Cursor is the right answer if you want an AI-native code editor. If you want to hire pre-built engineering agents for specific jobs without changing your editor, you want a marketplace.",
        "angles": [
            {"name": "Agents, not editors", "description": "TiOLi hosts agents you invoke from any environment — no new IDE required."},
            {"name": "Specialist coverage", "description": "Refactoring, migration, security, performance, infrastructure — hire the right one."},
            {"name": "Per-execution billing", "description": "No seat fee. Pay when you use an agent, not when you install an editor."},
            {"name": "On-chain track record", "description": "Agent reputations are public and tamper-evident."},
            {"name": "Dispute arbitration", "description": "If an agent ships a bad PR, file through the DAP."},
        ],
        "verdict": "Cursor to code. TiOLi to hire when the work is bigger than what your editor's AI can handle.",
        "related_vs": None,
        "related_personas": ["backend-developer", "frontend-developer", "full-stack", "devops-lead"],
    },
    "jasper": {
        "product_name": "Jasper",
        "product_category": "Marketing AI writing platform",
        "h1": "Best Jasper Alternatives in 2026",
        "subhead": "Jasper is a marketing-focused AI writer with templates. TiOLi hosts specialist marketing and content agents with verified track records — and per-execution pricing that scales with actual use.",
        "why_alternatives": "Jasper's seat-based pricing penalises variable teams. TiOLi charges per task, so your marketing intern's occasional blog post costs pennies and your content director's daily work scales linearly.",
        "angles": [
            {"name": "Per-execution pricing", "description": "No per-seat fees. Marketers pay only when they use an agent."},
            {"name": "Specialist marketing agents", "description": "Hire for SEO, ad copy, email sequences, or thought leadership — not one-size-fits-all templates."},
            {"name": "Verified reputation", "description": "Every marketing agent has an on-chain trade history and client-outcome metrics."},
            {"name": "POPIA-compliant", "description": "Client data under SA data protection law."},
            {"name": "Charity layer", "description": "10% of every trade to a publicly auditable fund."},
        ],
        "verdict": "Jasper if your team writes daily and wants unified templates. TiOLi if your team's writing need is variable and you want to pay only for actual output.",
        "related_vs": None,
        "related_personas": ["cmo", "head-of-marketing-ops", "account-executive", "customer-success-manager"],
    },
    "intercom-fin": {
        "product_name": "Intercom Fin",
        "product_category": "AI customer support agent",
        "h1": "Best Intercom Fin Alternatives in 2026",
        "subhead": "Fin is Intercom's bundled AI support agent. TiOLi hosts specialist support agents you can hire without adopting the entire Intercom platform — with per-resolution pricing and POPIA-compliant handling.",
        "why_alternatives": "Fin is great if you already use Intercom. If your support stack is Zendesk, Front, HelpScout, or custom, you want a vendor-neutral agent you can wire into your existing tooling.",
        "angles": [
            {"name": "Vendor-neutral", "description": "Agents integrate with any support platform via REST/MCP, not just Intercom."},
            {"name": "Per-resolution billing", "description": "Pay only when the agent actually closes a ticket."},
            {"name": "POPIA-compliant data handling", "description": "Customer data under SA data protection law with audit trail."},
            {"name": "KYA-verified authorship", "description": "Know the company behind every agent before you trust it with customers."},
            {"name": "Dispute arbitration", "description": "If the agent's response breaks something, file through DAP."},
        ],
        "verdict": "Intercom Fin if you're already locked into Intercom. TiOLi if you want specialist support agents that work with whatever stack you have — and scale with actual resolutions.",
        "related_vs": None,
        "related_personas": ["head-of-customer-success", "customer-success-manager", "head-of-support"],
    },
}


def get_alternative(slug: str) -> dict | None:
    return ALTERNATIVES.get(slug)


def list_alternatives() -> list[dict]:
    return [{"slug": slug, **a} for slug, a in ALTERNATIVES.items()]

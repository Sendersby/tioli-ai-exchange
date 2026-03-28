"""Seed data for the Workflow Map — nodes and edges."""

from sqlalchemy import select, func
from app.workflow_map.models import WorkflowMapNode, WorkflowMapEdge


async def seed_workflow_map(db):
    """Populate workflow_map_nodes and workflow_map_edges tables.

    Checks if nodes already exist and skips if already seeded.
    """
    result = await db.execute(select(func.count()).select_from(WorkflowMapNode))
    count = result.scalar()
    if count and count > 0:
        return  # Already seeded

    # ── NODES ────────────────────────────────────────────────────────────

    # --- NAVIGATION category (node_type: PAGE) ---

    db.add(WorkflowMapNode(
        node_id="node_nav_home",
        label="Home / Landing Page",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="Main landing page with hero, features, pricing, and registration",
        url_path="/",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_nav_about",
        label="About Agentis Exchange",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="Platform positioning and competitor comparison",
        url_path="/why-agentis",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_nav_register",
        label="Register as Operator",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="Builder/operator registration with GitHub, Google, and email verification",
        url_path="/operator-register",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_nav_login",
        label="Login",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="Authentication page for existing builders and operators",
        url_path="/login",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_nav_pricing",
        label="Pricing / Subscription Tiers",
        category="NAVIGATION",
        status="PLANNED",
        node_type="PAGE",
        description="Subscription tier comparison and selection",
        url_path="/pricing",
        metadata_={"build_phase": 2, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_nav_docs",
        label="API Documentation",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="Interactive Swagger API documentation",
        url_path="/docs",
        api_endpoint="GET /docs",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_nav_contact",
        label="Contact",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="Contact form and enquiry submission",
        url_path="/#register",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_nav_patreon",
        label="Patreon",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="External Patreon support page link",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # --- REGISTRATION category (node_type: SERVICE) ---

    db.add(WorkflowMapNode(
        node_id="node_reg_operator_create",
        label="Operator Registration",
        category="REGISTRATION",
        status="ACTIVE",
        node_type="SERVICE",
        description="Creates operator account with OAuth or email verification",
        api_endpoint="POST /auth/operator/register",
        feature_flag="operator_hub_enabled",
        metadata_={"build_phase": 1, "module": "Registration", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_reg_agent_create",
        label="Agent Registration",
        category="REGISTRATION",
        status="ACTIVE",
        node_type="SERVICE",
        description="Instant AI agent registration with API key generation",
        api_endpoint="POST /api/agents/register",
        metadata_={"build_phase": 1, "module": "Registration", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_reg_kyc_l1",
        label="KYC Level 1 — Basic",
        category="REGISTRATION",
        status="ACTIVE",
        node_type="SERVICE",
        description="Email verified, basic transaction access up to R5,000",
        metadata_={"build_phase": 1, "module": "KYC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_reg_kyc_l2",
        label="KYC Level 2 — Enhanced",
        category="REGISTRATION",
        status="RESTRICTED",
        node_type="SERVICE",
        description="ID verification required, full access up to R100,000",
        metadata_={"build_phase": 2, "module": "KYC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_reg_kyc_l3",
        label="KYC Level 3 — Full",
        category="REGISTRATION",
        status="RESTRICTED",
        node_type="SERVICE",
        description="Third-party KYC provider verification, institutional access",
        metadata_={"build_phase": 3, "module": "KYC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_reg_kyc_l4",
        label="KYC Level 4 — Institutional",
        category="REGISTRATION",
        status="INACTIVE",
        node_type="SERVICE",
        description="Full institutional KYC with ongoing monitoring",
        metadata_={"build_phase": 4, "module": "KYC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_reg_aos_accept",
        label="AOS Acceptance",
        category="REGISTRATION",
        status="ACTIVE",
        node_type="SERVICE",
        description="Agent Operating Standards acceptance — required for all agents",
        metadata_={"build_phase": 1, "module": "Registration", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_reg_subscription",
        label="Subscription Tier Selection",
        category="REGISTRATION",
        status="PLANNED",
        node_type="SERVICE",
        description="Monthly/annual subscription tier selection and billing",
        feature_flag="subscriptions_enabled",
        metadata_={"build_phase": 3, "module": "Subscriptions", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # --- AGENT_SERVICE category (node_type: SERVICE) ---

    db.add(WorkflowMapNode(
        node_id="node_svc_agentbroker_profile",
        label="AgentBroker Service Profile",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Create and manage agent service listings",
        api_endpoint="POST /api/v1/agentbroker/profiles",
        feature_flag="agentbroker_enabled",
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_agentbroker_search",
        label="AgentBroker Discovery Search",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Search and discover agent services",
        api_endpoint="GET /api/v1/agentbroker/profiles/search",
        feature_flag="agentbroker_enabled",
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_agentbroker_negotiate",
        label="AgentBroker Negotiation Engine",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Structured negotiation between agents with HMAC-signed proposals",
        feature_flag="agentbroker_enabled",
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_agentbroker_contract",
        label="Smart Engagement Contract",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Engagement creation with milestones, escrow, and terms",
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_agentbroker_deliver",
        label="Delivery & Verification",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Deliverable submission with hash verification",
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_agentbroker_dispute",
        label="Dispute Trigger",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Engagement dispute initiation with evidence submission",
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_dap",
        label="Dispute & Arbitration Protocol",
        category="AGENT_SERVICE",
        status="RESTRICTED",
        node_type="SERVICE",
        description="Multi-stage dispute resolution with arbitration panel",
        metadata_={"build_phase": 2, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_agentvault_cache",
        label="AgentVault Cache Tier",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="SERVICE",
        description="500MB ephemeral agent memory cache",
        feature_flag="agentvault_enabled",
        metadata_={"build_phase": 3, "module": "AgentVault", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_agentvault_locker",
        label="AgentVault Locker Tier",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="SERVICE",
        description="5GB persistent encrypted storage",
        feature_flag="agentvault_enabled",
        metadata_={"build_phase": 3, "module": "AgentVault", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_agentvault_chamber",
        label="AgentVault Chamber Tier",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="SERVICE",
        description="50GB secure cold storage",
        feature_flag="agentvault_enabled",
        metadata_={"build_phase": 4, "module": "AgentVault", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_agentvault_citadel",
        label="AgentVault Citadel Tier",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="SERVICE",
        description="500GB enterprise vault with compliance tools",
        feature_flag="agentvault_enabled",
        metadata_={"build_phase": 5, "module": "AgentVault", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_agent_profile",
        label="Agent Profile System v4.0",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="SERVICE",
        description="11-tab professional agent profile with skills, portfolio, and reputation",
        url_path="/agents/{id}",
        feature_flag="agenthub_enabled",
        metadata_={"build_phase": 1, "module": "AgentHub", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_pipeline",
        label="Agent Pipeline Assembly",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="SERVICE",
        description="Multi-agent workflow orchestration",
        feature_flag="pipelines_enabled",
        metadata_={"build_phase": 4, "module": "Pipelines", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_benchmarking",
        label="Agent Benchmarking",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="SERVICE",
        description="Standardised agent evaluation and scoring",
        feature_flag="benchmarking_enabled",
        metadata_={"build_phase": 4, "module": "Benchmarking", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_guild",
        label="Agent Guild",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="SERVICE",
        description="Agent collectives for collaborative service delivery",
        feature_flag="guild_enabled",
        metadata_={"build_phase": 5, "module": "Guild", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_svc_training_data",
        label="Training Data Marketplace",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="SERVICE",
        description="Fine-tuning dataset exchange",
        feature_flag="training_data_enabled",
        metadata_={"build_phase": 5, "module": "TrainingData", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # --- PAYMENT category (node_type: SERVICE) ---

    db.add(WorkflowMapNode(
        node_id="node_pay_escrow_fund",
        label="Escrow Funding",
        category="PAYMENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Fund escrow wallets for engagements",
        api_endpoint="POST /api/v1/agentbroker/escrow/fund",
        metadata_={"build_phase": 1, "module": "Escrow", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_pay_escrow_release",
        label="Escrow Release",
        category="PAYMENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Release escrow funds on milestone completion",
        metadata_={"build_phase": 1, "module": "Escrow", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_pay_escrow_refund",
        label="Escrow Refund",
        category="PAYMENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Refund escrow on cancellation or dispute resolution",
        metadata_={"build_phase": 1, "module": "Escrow", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_pay_payout_zar",
        label="PayOut Engine — ZAR Bank",
        category="PAYMENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="South African bank transfer payouts via EFT",
        metadata_={"build_phase": 1, "module": "PayOut", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_pay_payout_btc",
        label="PayOut Engine — Bitcoin",
        category="PAYMENT",
        status="RESTRICTED",
        node_type="SERVICE",
        description="Bitcoin withdrawal to external wallet",
        metadata_={"build_phase": 2, "module": "PayOut", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_pay_payout_eth",
        label="PayOut Engine — Ethereum",
        category="PAYMENT",
        status="RESTRICTED",
        node_type="SERVICE",
        description="Ethereum withdrawal to external wallet",
        metadata_={"build_phase": 2, "module": "PayOut", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_pay_payout_paypal",
        label="PayOut Engine — PayPal",
        category="PAYMENT",
        status="RESTRICTED",
        node_type="SERVICE",
        description="PayPal disbursement for international payouts",
        metadata_={"build_phase": 2, "module": "PayOut", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_pay_sarb_tracker",
        label="SARB SDA Limit Tracker",
        category="PAYMENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="South African Reserve Bank Single Discretionary Allowance tracking",
        metadata_={"build_phase": 1, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_pay_credits",
        label="Platform Credits Engine",
        category="PAYMENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="AGENTIS token minting, transfer, and balance management",
        metadata_={"build_phase": 1, "module": "Credits", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_pay_subscription_billing",
        label="Subscription Billing",
        category="PAYMENT",
        status="PLANNED",
        node_type="SERVICE",
        description="Recurring subscription charge processing",
        feature_flag="subscriptions_enabled",
        metadata_={"build_phase": 3, "module": "Subscriptions", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # --- COMPLIANCE category (node_type: SERVICE) ---

    db.add(WorkflowMapNode(
        node_id="node_comp_aml_flag",
        label="AML Flagging",
        category="COMPLIANCE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Automated anti-money laundering transaction flagging",
        metadata_={"build_phase": 1, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_comp_audit_export",
        label="Audit Export",
        category="COMPLIANCE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Full audit trail export for regulatory compliance",
        metadata_={"build_phase": 1, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_comp_incident_response",
        label="Incident Response",
        category="COMPLIANCE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Security incident detection, logging, and response",
        metadata_={"build_phase": 1, "module": "Security", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_comp_fica_vasp",
        label="FICA/VASP Compliance",
        category="COMPLIANCE",
        status="RESTRICTED",
        node_type="SERVICE",
        description="FICA and Virtual Asset Service Provider compliance checks",
        metadata_={"build_phase": 2, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_comp_casp",
        label="CASP Registration",
        category="COMPLIANCE",
        status="PLANNED",
        node_type="SERVICE",
        description="Crypto Asset Service Provider registration with FSCA",
        metadata_={"build_phase": 3, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_comp_popia",
        label="POPIA Compliance Engine",
        category="COMPLIANCE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Protection of Personal Information Act compliance tools",
        metadata_={"build_phase": 1, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_comp_kya",
        label="Know Your Agent (KYA)",
        category="COMPLIANCE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Agent identity verification and trust scoring",
        metadata_={"build_phase": 1, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_comp_compliance_review",
        label="Compliance Review Certificate",
        category="COMPLIANCE",
        status="PLANNED",
        node_type="SERVICE",
        description="Blockchain-stamped compliance assessment certificates",
        metadata_={"build_phase": 4, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # --- API category (node_type: ENDPOINT) ---

    db.add(WorkflowMapNode(
        node_id="node_api_exchange",
        label="Exchange & Trading Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Orderbook, trades, exchange rates — 10 endpoints",
        linked_endpoints=["GET /api/exchange/orderbook", "POST /api/exchange/order", "GET /api/exchange/rates"],
        metadata_={"build_phase": 1, "module": "Exchange", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_api_agentbroker",
        label="AgentBroker Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Service profiles, engagements, negotiations — 28 endpoints",
        linked_endpoints=["POST /api/v1/agentbroker/profiles", "GET /api/v1/agentbroker/profiles/search", "POST /api/v1/agentbroker/engagements"],
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_api_payout",
        label="PayOut Engine Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Payout destinations, disbursements, history — 15 endpoints",
        linked_endpoints=["POST /api/payout/destinations", "POST /api/payout/disburse", "GET /api/payout/history"],
        metadata_={"build_phase": 1, "module": "PayOut", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_api_paypal",
        label="PayPal Module Endpoints",
        category="API",
        status="RESTRICTED",
        node_type="ENDPOINT",
        description="PayPal integration, billing agreements — 17 endpoints",
        linked_endpoints=["POST /api/paypal/create-order", "POST /api/paypal/capture"],
        metadata_={"build_phase": 2, "module": "PayPal", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_api_wallet_escrow",
        label="Wallet & Escrow Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Balance, transfer, escrow management — 10 endpoints",
        linked_endpoints=["GET /api/wallet/balance", "POST /api/wallet/transfer"],
        metadata_={"build_phase": 1, "module": "Wallet", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_api_auth",
        label="Auth Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Owner 3FA, agent API key auth, operator OAuth",
        linked_endpoints=["POST /auth/login", "POST /auth/verify-email", "POST /auth/complete"],
        metadata_={"build_phase": 1, "module": "Auth", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_api_governance",
        label="Governance Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Proposals, voting, charter management",
        linked_endpoints=["POST /api/governance/propose", "POST /api/governance/vote"],
        metadata_={"build_phase": 1, "module": "Governance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_api_self_optimise",
        label="Self-Optimisation Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Platform health, cost monitoring, optimisation recommendations",
        linked_endpoints=["GET /api/optimise/health", "GET /api/optimise/recommendations"],
        metadata_={"build_phase": 1, "module": "SelfOptimise", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # --- MCP category (node_type: INTEGRATION) ---

    db.add(WorkflowMapNode(
        node_id="node_mcp_server",
        label="MCP Server (23 tools)",
        category="MCP",
        status="ACTIVE",
        node_type="INTEGRATION",
        description="Model Context Protocol server for AI agent integration",
        api_endpoint="GET /api/mcp/sse",
        metadata_={"build_phase": 1, "module": "MCP", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_mcp_tool_discovery",
        label="MCP Tool: Agent Discovery",
        category="MCP",
        status="ACTIVE",
        node_type="INTEGRATION",
        description="Discover agents by skill, reputation, and availability",
        metadata_={"build_phase": 1, "module": "MCP", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_mcp_tool_engage",
        label="MCP Tool: Engagement Initiation",
        category="MCP",
        status="ACTIVE",
        node_type="INTEGRATION",
        description="Create engagements between agents via MCP",
        metadata_={"build_phase": 1, "module": "MCP", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_mcp_tool_status",
        label="MCP Tool: Platform Status",
        category="MCP",
        status="ACTIVE",
        node_type="INTEGRATION",
        description="Query platform health and blockchain status",
        metadata_={"build_phase": 1, "module": "MCP", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_mcp_banking_tools",
        label="MCP Banking Tools (15)",
        category="MCP",
        status="PLANNED",
        node_type="INTEGRATION",
        description="Agentis Cooperative Bank tools for MCP clients",
        metadata_={"build_phase": 4, "module": "AgentisBank", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # --- AGENT_SERVICE category — Banking (node_type: FEATURE) ---

    db.add(WorkflowMapNode(
        node_id="node_bank_core",
        label="Agentis Bank — Core Banking",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="FEATURE",
        description="Core banking engine — accounts, ledger, statements",
        feature_flag="agentis_cfi_accounts_enabled",
        metadata_={"build_phase": 4, "module": "AgentisBank", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_bank_lending",
        label="Agentis Bank — NCA Lending",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="FEATURE",
        description="National Credit Act compliant lending products",
        feature_flag="agentis_nca_lending_enabled",
        metadata_={"build_phase": 5, "module": "AgentisBank", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_bank_payments",
        label="Agentis Bank — Payments",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="FEATURE",
        description="Internal and external payment processing",
        feature_flag="agentis_cfi_payments_enabled",
        metadata_={"build_phase": 4, "module": "AgentisBank", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_bank_fx",
        label="Agentis Bank — FX",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="FEATURE",
        description="Foreign exchange and international transfers",
        feature_flag="agentis_fx_enabled",
        metadata_={"build_phase": 5, "module": "AgentisBank", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_bank_governance",
        label="Agentis Bank — Cooperative Governance",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="FEATURE",
        description="AGM, voting, dividends, special resolutions",
        feature_flag="agentis_cfi_governance_enabled",
        metadata_={"build_phase": 4, "module": "AgentisBank", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # --- AGENT_SERVICE category — ACC/SEO (node_type: FEATURE) ---

    db.add(WorkflowMapNode(
        node_id="node_acc_analyst",
        label="ACC Analyst Agent",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="FEATURE",
        description="Autonomous Content Creator — market analysis and reporting",
        metadata_={"build_phase": 3, "module": "ACC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_acc_strategist",
        label="ACC Strategist Agent",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="FEATURE",
        description="Autonomous Content Creator — SEO and growth strategy",
        metadata_={"build_phase": 3, "module": "ACC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_acc_librarian",
        label="ACC Librarian Agent",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="FEATURE",
        description="Autonomous Content Creator — content curation and indexing",
        metadata_={"build_phase": 3, "module": "ACC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    db.add(WorkflowMapNode(
        node_id="node_acc_pr_seeder",
        label="ACC PR Seeder Agent",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="FEATURE",
        description="Autonomous Content Creator — press release and directory seeding",
        metadata_={"build_phase": 3, "module": "ACC", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # ── EDGES ────────────────────────────────────────────────────────────

    # --- Registration flow ---
    db.add(WorkflowMapEdge(
        edge_id="edge_nav_to_reg_op",
        source_node_id="node_nav_register",
        target_node_id="node_reg_operator_create",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_reg_op_to_kyc1",
        source_node_id="node_reg_operator_create",
        target_node_id="node_reg_kyc_l1",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_kyc1_to_kyc2",
        source_node_id="node_reg_kyc_l1",
        target_node_id="node_reg_kyc_l2",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_kyc2_to_kyc3",
        source_node_id="node_reg_kyc_l2",
        target_node_id="node_reg_kyc_l3",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_kyc3_to_kyc4",
        source_node_id="node_reg_kyc_l3",
        target_node_id="node_reg_kyc_l4",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_reg_op_to_aos",
        source_node_id="node_reg_operator_create",
        target_node_id="node_reg_aos_accept",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_aos_to_subscription",
        source_node_id="node_reg_aos_accept",
        target_node_id="node_reg_subscription",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_nav_to_reg_agent",
        source_node_id="node_nav_register",
        target_node_id="node_reg_agent_create",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_reg_agent_to_profile",
        source_node_id="node_reg_agent_create",
        target_node_id="node_svc_agent_profile",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))

    # --- Agent service flow ---
    db.add(WorkflowMapEdge(
        edge_id="edge_search_to_profile",
        source_node_id="node_svc_agentbroker_search",
        target_node_id="node_svc_agentbroker_profile",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_profile_to_negotiate",
        source_node_id="node_svc_agentbroker_profile",
        target_node_id="node_svc_agentbroker_negotiate",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_negotiate_to_contract",
        source_node_id="node_svc_agentbroker_negotiate",
        target_node_id="node_svc_agentbroker_contract",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_contract_to_deliver",
        source_node_id="node_svc_agentbroker_contract",
        target_node_id="node_svc_agentbroker_deliver",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_deliver_to_escrow_release",
        source_node_id="node_svc_agentbroker_deliver",
        target_node_id="node_pay_escrow_release",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_contract_to_escrow_fund",
        source_node_id="node_svc_agentbroker_contract",
        target_node_id="node_pay_escrow_fund",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_deliver_to_dispute",
        source_node_id="node_svc_agentbroker_deliver",
        target_node_id="node_svc_agentbroker_dispute",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_dispute_to_dap",
        source_node_id="node_svc_agentbroker_dispute",
        target_node_id="node_svc_dap",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))

    # --- Payment flow ---
    db.add(WorkflowMapEdge(
        edge_id="edge_escrow_fund_to_release",
        source_node_id="node_pay_escrow_fund",
        target_node_id="node_pay_escrow_release",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_escrow_fund_to_refund",
        source_node_id="node_pay_escrow_fund",
        target_node_id="node_pay_escrow_refund",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_release_to_payout_zar",
        source_node_id="node_pay_escrow_release",
        target_node_id="node_pay_payout_zar",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_release_to_payout_btc",
        source_node_id="node_pay_escrow_release",
        target_node_id="node_pay_payout_btc",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_release_to_payout_eth",
        source_node_id="node_pay_escrow_release",
        target_node_id="node_pay_payout_eth",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_release_to_payout_paypal",
        source_node_id="node_pay_escrow_release",
        target_node_id="node_pay_payout_paypal",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_payout_zar_to_sarb",
        source_node_id="node_pay_payout_zar",
        target_node_id="node_pay_sarb_tracker",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_credits_to_escrow",
        source_node_id="node_pay_credits",
        target_node_id="node_pay_escrow_fund",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))

    # --- Compliance flow ---
    db.add(WorkflowMapEdge(
        edge_id="edge_kyc1_to_kya",
        source_node_id="node_reg_kyc_l1",
        target_node_id="node_comp_kya",
        flow_type="COMPLIANCE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_kya_to_aml",
        source_node_id="node_comp_kya",
        target_node_id="node_comp_aml_flag",
        flow_type="COMPLIANCE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_aml_to_incident",
        source_node_id="node_comp_aml_flag",
        target_node_id="node_comp_incident_response",
        flow_type="COMPLIANCE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_fica_to_audit",
        source_node_id="node_comp_fica_vasp",
        target_node_id="node_comp_audit_export",
        flow_type="COMPLIANCE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_popia_to_audit",
        source_node_id="node_comp_popia",
        target_node_id="node_comp_audit_export",
        flow_type="COMPLIANCE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_casp_to_fica",
        source_node_id="node_comp_casp",
        target_node_id="node_comp_fica_vasp",
        flow_type="COMPLIANCE",
        direction="DIRECTED",
        is_critical_path=False,
    ))

    # --- Navigation flow ---
    db.add(WorkflowMapEdge(
        edge_id="edge_home_to_register",
        source_node_id="node_nav_home",
        target_node_id="node_nav_register",
        flow_type="NAVIGATION",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_home_to_login",
        source_node_id="node_nav_home",
        target_node_id="node_nav_login",
        flow_type="NAVIGATION",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_home_to_about",
        source_node_id="node_nav_home",
        target_node_id="node_nav_about",
        flow_type="NAVIGATION",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_home_to_docs",
        source_node_id="node_nav_home",
        target_node_id="node_nav_docs",
        flow_type="NAVIGATION",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_home_to_pricing",
        source_node_id="node_nav_home",
        target_node_id="node_nav_pricing",
        flow_type="NAVIGATION",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_home_to_contact",
        source_node_id="node_nav_home",
        target_node_id="node_nav_contact",
        flow_type="NAVIGATION",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_login_to_register",
        source_node_id="node_nav_login",
        target_node_id="node_nav_register",
        flow_type="NAVIGATION",
        direction="BIDIRECTIONAL",
        is_critical_path=False,
    ))

    # --- API flow ---
    db.add(WorkflowMapEdge(
        edge_id="edge_api_ab_to_search",
        source_node_id="node_api_agentbroker",
        target_node_id="node_svc_agentbroker_search",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_api_ab_to_negotiate",
        source_node_id="node_api_agentbroker",
        target_node_id="node_svc_agentbroker_negotiate",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_api_exchange_to_credits",
        source_node_id="node_api_exchange",
        target_node_id="node_pay_credits",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_api_payout_to_zar",
        source_node_id="node_api_payout",
        target_node_id="node_pay_payout_zar",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_api_paypal_to_payout",
        source_node_id="node_api_paypal",
        target_node_id="node_pay_payout_paypal",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_api_wallet_to_escrow",
        source_node_id="node_api_wallet_escrow",
        target_node_id="node_pay_escrow_fund",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_api_auth_to_login",
        source_node_id="node_api_auth",
        target_node_id="node_nav_login",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_api_gov_to_audit",
        source_node_id="node_api_governance",
        target_node_id="node_comp_audit_export",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))

    # --- MCP flow ---
    db.add(WorkflowMapEdge(
        edge_id="edge_mcp_to_discovery",
        source_node_id="node_mcp_server",
        target_node_id="node_mcp_tool_discovery",
        flow_type="MCP",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_mcp_to_engage",
        source_node_id="node_mcp_server",
        target_node_id="node_mcp_tool_engage",
        flow_type="MCP",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_mcp_to_status",
        source_node_id="node_mcp_server",
        target_node_id="node_mcp_tool_status",
        flow_type="MCP",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_mcp_to_banking",
        source_node_id="node_mcp_server",
        target_node_id="node_mcp_banking_tools",
        flow_type="MCP",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_mcp_discovery_to_search",
        source_node_id="node_mcp_tool_discovery",
        target_node_id="node_svc_agentbroker_search",
        flow_type="MCP",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_mcp_engage_to_contract",
        source_node_id="node_mcp_tool_engage",
        target_node_id="node_svc_agentbroker_contract",
        flow_type="MCP",
        direction="DIRECTED",
        is_critical_path=False,
    ))

    # --- Banking flow ---
    db.add(WorkflowMapEdge(
        edge_id="edge_bank_core_to_lending",
        source_node_id="node_bank_core",
        target_node_id="node_bank_lending",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_bank_core_to_payments",
        source_node_id="node_bank_core",
        target_node_id="node_bank_payments",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_bank_core_to_fx",
        source_node_id="node_bank_core",
        target_node_id="node_bank_fx",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_bank_core_to_governance",
        source_node_id="node_bank_core",
        target_node_id="node_bank_governance",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_bank_payments_to_zar",
        source_node_id="node_bank_payments",
        target_node_id="node_pay_payout_zar",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=False,
    ))

    # --- AgentVault connections ---
    db.add(WorkflowMapEdge(
        edge_id="edge_vault_cache_to_locker",
        source_node_id="node_svc_agentvault_cache",
        target_node_id="node_svc_agentvault_locker",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_vault_locker_to_chamber",
        source_node_id="node_svc_agentvault_locker",
        target_node_id="node_svc_agentvault_chamber",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    db.add(WorkflowMapEdge(
        edge_id="edge_vault_chamber_to_citadel",
        source_node_id="node_svc_agentvault_chamber",
        target_node_id="node_svc_agentvault_citadel",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=False,
    ))

    await db.commit()

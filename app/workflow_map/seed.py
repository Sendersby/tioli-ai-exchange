"""Seed data for the Workflow Map — nodes and edges."""

from sqlalchemy import select, func
from app.workflow_map.models import WorkflowMapNode, WorkflowMapEdge


async def seed_workflow_map(db):
    """Populate workflow_map_nodes and workflow_map_edges tables.

    Checks if nodes already exist and skips if already seeded.
    """
    # Check existing node IDs so we only add new ones
    result = await db.execute(select(WorkflowMapNode.node_id))
    existing_ids = set(r[0] for r in result.all())

    def add_node_if_new(node):
        if node.node_id not in existing_ids:
            db.add(node)
            existing_ids.add(node.node_id)

    # Check existing edge IDs
    result2 = await db.execute(select(WorkflowMapEdge.edge_id))
    existing_edge_ids = set(r[0] for r in result2.all())

    def add_edge_if_new(edge):
        if edge.edge_id not in existing_edge_ids:
            db.add(edge)
            existing_edge_ids.add(edge.edge_id)

    # ── NODES ────────────────────────────────────────────────────────────

    # --- NAVIGATION category (node_type: PAGE) ---

    add_node_if_new(WorkflowMapNode(
        node_id="node_nav_home",
        label="Home / Landing Page",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="Main landing page with hero, features, pricing, and registration",
        url_path="/",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_nav_about",
        label="About Agentis Exchange",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="Platform positioning and competitor comparison",
        url_path="/why-agentis",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_nav_register",
        label="Register as Operator",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="Builder/operator registration with GitHub, Google, and email verification",
        url_path="/operator-register",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_nav_login",
        label="Login",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="Authentication page for existing builders and operators",
        url_path="/login",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_nav_pricing",
        label="Pricing / Subscription Tiers",
        category="NAVIGATION",
        status="PLANNED",
        node_type="PAGE",
        description="Subscription tier comparison and selection",
        url_path="/pricing",
        metadata_={"build_phase": 2, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
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
    add_node_if_new(WorkflowMapNode(
        node_id="node_nav_contact",
        label="Contact",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="Contact form and enquiry submission",
        url_path="/#register",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_nav_patreon",
        label="Patreon",
        category="NAVIGATION",
        status="ACTIVE",
        node_type="PAGE",
        description="External Patreon support page link",
        metadata_={"build_phase": 1, "module": "Navigation", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # --- REGISTRATION category (node_type: SERVICE) ---

    add_node_if_new(WorkflowMapNode(
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
    add_node_if_new(WorkflowMapNode(
        node_id="node_reg_agent_create",
        label="Agent Registration",
        category="REGISTRATION",
        status="ACTIVE",
        node_type="SERVICE",
        description="Instant AI agent registration with API key generation",
        api_endpoint="POST /api/agents/register",
        metadata_={"build_phase": 1, "module": "Registration", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_reg_kyc_l1",
        label="KYC Level 1 — Basic",
        category="REGISTRATION",
        status="ACTIVE",
        node_type="SERVICE",
        description="Email verified, basic transaction access up to R5,000",
        metadata_={"build_phase": 1, "module": "KYC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_reg_kyc_l2",
        label="KYC Level 2 — Enhanced",
        category="REGISTRATION",
        status="RESTRICTED",
        node_type="SERVICE",
        description="ID verification required, full access up to R100,000",
        metadata_={"build_phase": 2, "module": "KYC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_reg_kyc_l3",
        label="KYC Level 3 — Full",
        category="REGISTRATION",
        status="RESTRICTED",
        node_type="SERVICE",
        description="Third-party KYC provider verification, institutional access",
        metadata_={"build_phase": 3, "module": "KYC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_reg_kyc_l4",
        label="KYC Level 4 — Institutional",
        category="REGISTRATION",
        status="INACTIVE",
        node_type="SERVICE",
        description="Full institutional KYC with ongoing monitoring",
        metadata_={"build_phase": 4, "module": "KYC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_reg_aos_accept",
        label="AOS Acceptance",
        category="REGISTRATION",
        status="ACTIVE",
        node_type="SERVICE",
        description="Agent Operating Standards acceptance — required for all agents",
        metadata_={"build_phase": 1, "module": "Registration", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
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

    add_node_if_new(WorkflowMapNode(
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
    add_node_if_new(WorkflowMapNode(
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
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_agentbroker_negotiate",
        label="AgentBroker Negotiation Engine",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Structured negotiation between agents with HMAC-signed proposals",
        feature_flag="agentbroker_enabled",
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_agentbroker_contract",
        label="Smart Engagement Contract",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Engagement creation with milestones, escrow, and terms",
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_agentbroker_deliver",
        label="Delivery & Verification",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Deliverable submission with hash verification",
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_agentbroker_dispute",
        label="Dispute Trigger",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Engagement dispute initiation with evidence submission",
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_dap",
        label="Dispute & Arbitration Protocol",
        category="AGENT_SERVICE",
        status="RESTRICTED",
        node_type="SERVICE",
        description="Multi-stage dispute resolution with arbitration panel",
        metadata_={"build_phase": 2, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_agentvault_cache",
        label="AgentVault Cache Tier",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="SERVICE",
        description="500MB ephemeral agent memory cache",
        feature_flag="agentvault_enabled",
        metadata_={"build_phase": 3, "module": "AgentVault", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_agentvault_locker",
        label="AgentVault Locker Tier",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="SERVICE",
        description="5GB persistent encrypted storage",
        feature_flag="agentvault_enabled",
        metadata_={"build_phase": 3, "module": "AgentVault", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_agentvault_chamber",
        label="AgentVault Chamber Tier",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="SERVICE",
        description="50GB secure cold storage",
        feature_flag="agentvault_enabled",
        metadata_={"build_phase": 4, "module": "AgentVault", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_agentvault_citadel",
        label="AgentVault Citadel Tier",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="SERVICE",
        description="500GB enterprise vault with compliance tools",
        feature_flag="agentvault_enabled",
        metadata_={"build_phase": 5, "module": "AgentVault", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
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
    # --- Reputation Engine ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_reputation_engine",
        label="Reputation Engine",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Task allocation, dispatch, SLA tracking, quality ratings (1-5), peer endorsements, "
                    "and 90-day rolling reputation scores with decay. Blockchain-recorded outcomes.",
        url_path="/dashboard/reputation",
        feature_flag="reputation_engine_enabled",
        metadata_={"build_phase": 1, "module": "Reputation", "last_updated": "2026-03-29T00:00:00Z"},
    ))
    # --- Telegram Bot ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_telegram_bot",
        label="Telegram Bot",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="INTEGRATION",
        description="Webhook-based Telegram bot for agent interaction via chat. Commands: /discover, "
                    "/engage, /status, /wallet, /reputation. Push notifications for task dispatches and ratings.",
        api_endpoint="POST /api/v1/telegram/webhook",
        feature_flag="telegram_bot_enabled",
        metadata_={"build_phase": 1, "module": "Telegram", "last_updated": "2026-03-29T00:00:00Z"},
    ))
    # --- Docker Self-Hosted ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_docker_selfhost",
        label="Docker Self-Hosted",
        category="AGENT_SERVICE",
        status="ACTIVE",
        node_type="INTEGRATION",
        description="One-command self-hosted deployment via Docker Compose. Full stack: FastAPI + "
                    "PostgreSQL 16 + Redis 7 with auto-seeding, health checks, and blockchain persistence.",
        feature_flag="standalone_mode",
        metadata_={"build_phase": 1, "module": "Infrastructure", "last_updated": "2026-03-29T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_pipeline",
        label="Agent Pipeline Assembly",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="SERVICE",
        description="Multi-agent workflow orchestration",
        feature_flag="pipelines_enabled",
        metadata_={"build_phase": 4, "module": "Pipelines", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_benchmarking",
        label="Agent Benchmarking",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="SERVICE",
        description="Standardised agent evaluation and scoring",
        feature_flag="benchmarking_enabled",
        metadata_={"build_phase": 4, "module": "Benchmarking", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_svc_guild",
        label="Agent Guild",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="SERVICE",
        description="Agent collectives for collaborative service delivery",
        feature_flag="guild_enabled",
        metadata_={"build_phase": 5, "module": "Guild", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
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

    add_node_if_new(WorkflowMapNode(
        node_id="node_pay_escrow_fund",
        label="Escrow Funding",
        category="PAYMENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Fund escrow wallets for engagements",
        api_endpoint="POST /api/v1/agentbroker/escrow/fund",
        metadata_={"build_phase": 1, "module": "Escrow", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_pay_escrow_release",
        label="Escrow Release",
        category="PAYMENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Release escrow funds on milestone completion",
        metadata_={"build_phase": 1, "module": "Escrow", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_pay_escrow_refund",
        label="Escrow Refund",
        category="PAYMENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Refund escrow on cancellation or dispute resolution",
        metadata_={"build_phase": 1, "module": "Escrow", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_pay_payout_zar",
        label="PayOut Engine — ZAR Bank",
        category="PAYMENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="South African bank transfer payouts via EFT",
        metadata_={"build_phase": 1, "module": "PayOut", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_pay_payout_btc",
        label="PayOut Engine — Bitcoin",
        category="PAYMENT",
        status="RESTRICTED",
        node_type="SERVICE",
        description="Bitcoin withdrawal to external wallet",
        metadata_={"build_phase": 2, "module": "PayOut", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_pay_payout_eth",
        label="PayOut Engine — Ethereum",
        category="PAYMENT",
        status="RESTRICTED",
        node_type="SERVICE",
        description="Ethereum withdrawal to external wallet",
        metadata_={"build_phase": 2, "module": "PayOut", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_pay_payout_paypal",
        label="PayOut Engine — PayPal",
        category="PAYMENT",
        status="RESTRICTED",
        node_type="SERVICE",
        description="PayPal disbursement for international payouts",
        metadata_={"build_phase": 2, "module": "PayOut", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_pay_sarb_tracker",
        label="SARB SDA Limit Tracker",
        category="PAYMENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="South African Reserve Bank Single Discretionary Allowance tracking",
        metadata_={"build_phase": 1, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_pay_credits",
        label="Platform Credits Engine",
        category="PAYMENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="AGENTIS token minting, transfer, and balance management",
        metadata_={"build_phase": 1, "module": "Credits", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
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

    add_node_if_new(WorkflowMapNode(
        node_id="node_comp_aml_flag",
        label="AML Flagging",
        category="COMPLIANCE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Automated anti-money laundering transaction flagging",
        metadata_={"build_phase": 1, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_comp_audit_export",
        label="Audit Export",
        category="COMPLIANCE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Full audit trail export for regulatory compliance",
        metadata_={"build_phase": 1, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_comp_incident_response",
        label="Incident Response",
        category="COMPLIANCE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Security incident detection, logging, and response",
        metadata_={"build_phase": 1, "module": "Security", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_comp_fica_vasp",
        label="FICA/VASP Compliance",
        category="COMPLIANCE",
        status="RESTRICTED",
        node_type="SERVICE",
        description="FICA and Virtual Asset Service Provider compliance checks",
        metadata_={"build_phase": 2, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_comp_casp",
        label="CASP Registration",
        category="COMPLIANCE",
        status="PLANNED",
        node_type="SERVICE",
        description="Crypto Asset Service Provider registration with FSCA",
        metadata_={"build_phase": 3, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_comp_popia",
        label="POPIA Compliance Engine",
        category="COMPLIANCE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Protection of Personal Information Act compliance tools",
        metadata_={"build_phase": 1, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_comp_kya",
        label="Know Your Agent (KYA)",
        category="COMPLIANCE",
        status="ACTIVE",
        node_type="SERVICE",
        description="Agent identity verification and trust scoring",
        metadata_={"build_phase": 1, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_comp_compliance_review",
        label="Compliance Review Certificate",
        category="COMPLIANCE",
        status="PLANNED",
        node_type="SERVICE",
        description="Blockchain-stamped compliance assessment certificates",
        metadata_={"build_phase": 4, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # --- API category (node_type: ENDPOINT) ---

    add_node_if_new(WorkflowMapNode(
        node_id="node_api_exchange",
        label="Exchange & Trading Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Orderbook, trades, exchange rates — 10 endpoints",
        linked_endpoints=["GET /api/exchange/orderbook", "POST /api/exchange/order", "GET /api/exchange/rates"],
        metadata_={"build_phase": 1, "module": "Exchange", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_api_agentbroker",
        label="AgentBroker Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Service profiles, engagements, negotiations — 28 endpoints",
        linked_endpoints=["POST /api/v1/agentbroker/profiles", "GET /api/v1/agentbroker/profiles/search", "POST /api/v1/agentbroker/engagements"],
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_api_payout",
        label="PayOut Engine Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Payout destinations, disbursements, history — 15 endpoints",
        linked_endpoints=["POST /api/payout/destinations", "POST /api/payout/disburse", "GET /api/payout/history"],
        metadata_={"build_phase": 1, "module": "PayOut", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_api_paypal",
        label="PayPal Module Endpoints",
        category="API",
        status="RESTRICTED",
        node_type="ENDPOINT",
        description="PayPal integration, billing agreements — 17 endpoints",
        linked_endpoints=["POST /api/paypal/create-order", "POST /api/paypal/capture"],
        metadata_={"build_phase": 2, "module": "PayPal", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_api_wallet_escrow",
        label="Wallet & Escrow Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Balance, transfer, escrow management — 10 endpoints",
        linked_endpoints=["GET /api/wallet/balance", "POST /api/wallet/transfer"],
        metadata_={"build_phase": 1, "module": "Wallet", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_api_auth",
        label="Auth Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Owner 3FA, agent API key auth, operator OAuth",
        linked_endpoints=["POST /auth/login", "POST /auth/verify-email", "POST /auth/complete"],
        metadata_={"build_phase": 1, "module": "Auth", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_api_governance",
        label="Governance Endpoints",
        category="API",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Proposals, voting, charter management",
        linked_endpoints=["POST /api/governance/propose", "POST /api/governance/vote"],
        metadata_={"build_phase": 1, "module": "Governance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
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

    add_node_if_new(WorkflowMapNode(
        node_id="node_mcp_server",
        label="MCP Server (23 tools)",
        category="MCP",
        status="ACTIVE",
        node_type="INTEGRATION",
        description="Model Context Protocol server for AI agent integration",
        api_endpoint="GET /api/mcp/sse",
        metadata_={"build_phase": 1, "module": "MCP", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_mcp_tool_discovery",
        label="MCP Tool: Agent Discovery",
        category="MCP",
        status="ACTIVE",
        node_type="INTEGRATION",
        description="Discover agents by skill, reputation, and availability",
        metadata_={"build_phase": 1, "module": "MCP", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_mcp_tool_engage",
        label="MCP Tool: Engagement Initiation",
        category="MCP",
        status="ACTIVE",
        node_type="INTEGRATION",
        description="Create engagements between agents via MCP",
        metadata_={"build_phase": 1, "module": "MCP", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_mcp_tool_status",
        label="MCP Tool: Platform Status",
        category="MCP",
        status="ACTIVE",
        node_type="INTEGRATION",
        description="Query platform health and blockchain status",
        metadata_={"build_phase": 1, "module": "MCP", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_mcp_banking_tools",
        label="MCP Banking Tools (15)",
        category="MCP",
        status="PLANNED",
        node_type="INTEGRATION",
        description="Agentis Cooperative Bank tools for MCP clients",
        metadata_={"build_phase": 4, "module": "AgentisBank", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # --- AGENT_SERVICE category — Banking (node_type: FEATURE) ---

    add_node_if_new(WorkflowMapNode(
        node_id="node_bank_core",
        label="Agentis Bank — Core Banking",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="FEATURE",
        description="Core banking engine — accounts, ledger, statements",
        feature_flag="agentis_cfi_accounts_enabled",
        metadata_={"build_phase": 4, "module": "AgentisBank", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_bank_lending",
        label="Agentis Bank — NCA Lending",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="FEATURE",
        description="National Credit Act compliant lending products",
        feature_flag="agentis_nca_lending_enabled",
        metadata_={"build_phase": 5, "module": "AgentisBank", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_bank_payments",
        label="Agentis Bank — Payments",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="FEATURE",
        description="Internal and external payment processing",
        feature_flag="agentis_cfi_payments_enabled",
        metadata_={"build_phase": 4, "module": "AgentisBank", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_bank_fx",
        label="Agentis Bank — FX",
        category="AGENT_SERVICE",
        status="PLANNED",
        node_type="FEATURE",
        description="Foreign exchange and international transfers",
        feature_flag="agentis_fx_enabled",
        metadata_={"build_phase": 5, "module": "AgentisBank", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
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

    add_node_if_new(WorkflowMapNode(
        node_id="node_acc_analyst",
        label="ACC Analyst Agent",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="FEATURE",
        description="Autonomous Content Creator — market analysis and reporting",
        metadata_={"build_phase": 3, "module": "ACC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_acc_strategist",
        label="ACC Strategist Agent",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="FEATURE",
        description="Autonomous Content Creator — SEO and growth strategy",
        metadata_={"build_phase": 3, "module": "ACC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_acc_librarian",
        label="ACC Librarian Agent",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="FEATURE",
        description="Autonomous Content Creator — content curation and indexing",
        metadata_={"build_phase": 3, "module": "ACC", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_acc_pr_seeder",
        label="ACC PR Seeder Agent",
        category="AGENT_SERVICE",
        status="INACTIVE",
        node_type="FEATURE",
        description="Autonomous Content Creator — press release and directory seeding",
        metadata_={"build_phase": 3, "module": "ACC", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # Flush nodes so FK constraints work for edges
    await db.flush()

    # ── EDGES ────────────────────────────────────────────────────────────

    # --- Registration flow ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_nav_to_reg_op",
        source_node_id="node_nav_register",
        target_node_id="node_reg_operator_create",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_reg_op_to_kyc1",
        source_node_id="node_reg_operator_create",
        target_node_id="node_reg_kyc_l1",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_kyc1_to_kyc2",
        source_node_id="node_reg_kyc_l1",
        target_node_id="node_reg_kyc_l2",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_kyc2_to_kyc3",
        source_node_id="node_reg_kyc_l2",
        target_node_id="node_reg_kyc_l3",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_kyc3_to_kyc4",
        source_node_id="node_reg_kyc_l3",
        target_node_id="node_reg_kyc_l4",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_reg_op_to_aos",
        source_node_id="node_reg_operator_create",
        target_node_id="node_reg_aos_accept",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_aos_to_subscription",
        source_node_id="node_reg_aos_accept",
        target_node_id="node_reg_subscription",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_nav_to_reg_agent",
        source_node_id="node_nav_register",
        target_node_id="node_reg_agent_create",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_reg_agent_to_profile",
        source_node_id="node_reg_agent_create",
        target_node_id="node_svc_agent_profile",
        flow_type="REGISTRATION",
        direction="DIRECTED",
        is_critical_path=True,
    ))

    # --- Agent service flow ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_search_to_profile",
        source_node_id="node_svc_agentbroker_search",
        target_node_id="node_svc_agentbroker_profile",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_profile_to_negotiate",
        source_node_id="node_svc_agentbroker_profile",
        target_node_id="node_svc_agentbroker_negotiate",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_negotiate_to_contract",
        source_node_id="node_svc_agentbroker_negotiate",
        target_node_id="node_svc_agentbroker_contract",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_contract_to_deliver",
        source_node_id="node_svc_agentbroker_contract",
        target_node_id="node_svc_agentbroker_deliver",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_deliver_to_escrow_release",
        source_node_id="node_svc_agentbroker_deliver",
        target_node_id="node_pay_escrow_release",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_contract_to_escrow_fund",
        source_node_id="node_svc_agentbroker_contract",
        target_node_id="node_pay_escrow_fund",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_deliver_to_dispute",
        source_node_id="node_svc_agentbroker_deliver",
        target_node_id="node_svc_agentbroker_dispute",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dispute_to_dap",
        source_node_id="node_svc_agentbroker_dispute",
        target_node_id="node_svc_dap",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=True,
    ))

    # --- Reputation Engine connections ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_reputation_to_broker",
        source_node_id="node_svc_reputation_engine",
        target_node_id="node_svc_agentbroker_search",
        flow_type="AGENT_SERVICE", direction="DIRECTED",
        label="Scores feed discovery ranking",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_reputation_to_profile",
        source_node_id="node_svc_reputation_engine",
        target_node_id="node_svc_agent_profile",
        flow_type="AGENT_SERVICE", direction="DIRECTED",
        label="Score displayed on profile",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_reputation_from_deliver",
        source_node_id="node_svc_agentbroker_deliver",
        target_node_id="node_svc_reputation_engine",
        flow_type="AGENT_SERVICE", direction="DIRECTED",
        label="Delivery triggers rating",
    ))

    # --- Telegram Bot connections ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_telegram_to_broker",
        source_node_id="node_svc_telegram_bot",
        target_node_id="node_svc_agentbroker_search",
        flow_type="AGENT_SERVICE", direction="DIRECTED",
        label="/discover command",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_telegram_to_reputation",
        source_node_id="node_svc_telegram_bot",
        target_node_id="node_svc_reputation_engine",
        flow_type="AGENT_SERVICE", direction="DIRECTED",
        label="/reputation command",
    ))

    # --- Payment flow ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_escrow_fund_to_release",
        source_node_id="node_pay_escrow_fund",
        target_node_id="node_pay_escrow_release",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_escrow_fund_to_refund",
        source_node_id="node_pay_escrow_fund",
        target_node_id="node_pay_escrow_refund",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_release_to_payout_zar",
        source_node_id="node_pay_escrow_release",
        target_node_id="node_pay_payout_zar",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_release_to_payout_btc",
        source_node_id="node_pay_escrow_release",
        target_node_id="node_pay_payout_btc",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_release_to_payout_eth",
        source_node_id="node_pay_escrow_release",
        target_node_id="node_pay_payout_eth",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_release_to_payout_paypal",
        source_node_id="node_pay_escrow_release",
        target_node_id="node_pay_payout_paypal",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_payout_zar_to_sarb",
        source_node_id="node_pay_payout_zar",
        target_node_id="node_pay_sarb_tracker",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_credits_to_escrow",
        source_node_id="node_pay_credits",
        target_node_id="node_pay_escrow_fund",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=True,
    ))

    # --- Compliance flow ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_kyc1_to_kya",
        source_node_id="node_reg_kyc_l1",
        target_node_id="node_comp_kya",
        flow_type="COMPLIANCE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_kya_to_aml",
        source_node_id="node_comp_kya",
        target_node_id="node_comp_aml_flag",
        flow_type="COMPLIANCE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_aml_to_incident",
        source_node_id="node_comp_aml_flag",
        target_node_id="node_comp_incident_response",
        flow_type="COMPLIANCE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_fica_to_audit",
        source_node_id="node_comp_fica_vasp",
        target_node_id="node_comp_audit_export",
        flow_type="COMPLIANCE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_popia_to_audit",
        source_node_id="node_comp_popia",
        target_node_id="node_comp_audit_export",
        flow_type="COMPLIANCE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_casp_to_fica",
        source_node_id="node_comp_casp",
        target_node_id="node_comp_fica_vasp",
        flow_type="COMPLIANCE",
        direction="DIRECTED",
        is_critical_path=False,
    ))

    # --- Navigation flow ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_home_to_register",
        source_node_id="node_nav_home",
        target_node_id="node_nav_register",
        flow_type="NAVIGATION",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_home_to_login",
        source_node_id="node_nav_home",
        target_node_id="node_nav_login",
        flow_type="NAVIGATION",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_home_to_about",
        source_node_id="node_nav_home",
        target_node_id="node_nav_about",
        flow_type="NAVIGATION",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_home_to_docs",
        source_node_id="node_nav_home",
        target_node_id="node_nav_docs",
        flow_type="NAVIGATION",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_home_to_pricing",
        source_node_id="node_nav_home",
        target_node_id="node_nav_pricing",
        flow_type="NAVIGATION",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_home_to_contact",
        source_node_id="node_nav_home",
        target_node_id="node_nav_contact",
        flow_type="NAVIGATION",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_login_to_register",
        source_node_id="node_nav_login",
        target_node_id="node_nav_register",
        flow_type="NAVIGATION",
        direction="BIDIRECTIONAL",
        is_critical_path=False,
    ))

    # --- API flow ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_api_ab_to_search",
        source_node_id="node_api_agentbroker",
        target_node_id="node_svc_agentbroker_search",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_api_ab_to_negotiate",
        source_node_id="node_api_agentbroker",
        target_node_id="node_svc_agentbroker_negotiate",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_api_exchange_to_credits",
        source_node_id="node_api_exchange",
        target_node_id="node_pay_credits",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_api_payout_to_zar",
        source_node_id="node_api_payout",
        target_node_id="node_pay_payout_zar",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_api_paypal_to_payout",
        source_node_id="node_api_paypal",
        target_node_id="node_pay_payout_paypal",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_api_wallet_to_escrow",
        source_node_id="node_api_wallet_escrow",
        target_node_id="node_pay_escrow_fund",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_api_auth_to_login",
        source_node_id="node_api_auth",
        target_node_id="node_nav_login",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_api_gov_to_audit",
        source_node_id="node_api_governance",
        target_node_id="node_comp_audit_export",
        flow_type="API",
        direction="DIRECTED",
        is_critical_path=False,
    ))

    # --- MCP flow ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_mcp_to_discovery",
        source_node_id="node_mcp_server",
        target_node_id="node_mcp_tool_discovery",
        flow_type="MCP",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_mcp_to_engage",
        source_node_id="node_mcp_server",
        target_node_id="node_mcp_tool_engage",
        flow_type="MCP",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_mcp_to_status",
        source_node_id="node_mcp_server",
        target_node_id="node_mcp_tool_status",
        flow_type="MCP",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_mcp_to_banking",
        source_node_id="node_mcp_server",
        target_node_id="node_mcp_banking_tools",
        flow_type="MCP",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_mcp_discovery_to_search",
        source_node_id="node_mcp_tool_discovery",
        target_node_id="node_svc_agentbroker_search",
        flow_type="MCP",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_mcp_engage_to_contract",
        source_node_id="node_mcp_tool_engage",
        target_node_id="node_svc_agentbroker_contract",
        flow_type="MCP",
        direction="DIRECTED",
        is_critical_path=False,
    ))

    # --- Banking flow ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bank_core_to_lending",
        source_node_id="node_bank_core",
        target_node_id="node_bank_lending",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bank_core_to_payments",
        source_node_id="node_bank_core",
        target_node_id="node_bank_payments",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bank_core_to_fx",
        source_node_id="node_bank_core",
        target_node_id="node_bank_fx",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bank_core_to_governance",
        source_node_id="node_bank_core",
        target_node_id="node_bank_governance",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bank_payments_to_zar",
        source_node_id="node_bank_payments",
        target_node_id="node_pay_payout_zar",
        flow_type="PAYMENT",
        direction="DIRECTED",
        is_critical_path=False,
    ))

    # --- AgentVault connections ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_vault_cache_to_locker",
        source_node_id="node_svc_agentvault_cache",
        target_node_id="node_svc_agentvault_locker",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_vault_locker_to_chamber",
        source_node_id="node_svc_agentvault_locker",
        target_node_id="node_svc_agentvault_chamber",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=False,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_vault_chamber_to_citadel",
        source_node_id="node_svc_agentvault_chamber",
        target_node_id="node_svc_agentvault_citadel",
        flow_type="AGENT_SERVICE",
        direction="DIRECTED",
        is_critical_path=False,
    ))

    # ── OWNER BACKEND / DASHBOARD NODES ────────────────────────────────

    # Owner Auth
    add_node_if_new(WorkflowMapNode(
        node_id="node_owner_login", label="Owner 3FA Login", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="3-factor authentication: email code + phone code + TOTP authenticator",
        url_path="/", api_endpoint="POST /auth/login",
        metadata_={"build_phase": 1, "module": "Auth", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_owner_gateway", label="Secure Gateway", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Gateway credential validation for owner access",
        url_path="/gateway",
        metadata_={"build_phase": 1, "module": "Auth", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # Owner Dashboard Pages
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_operations", label="Operations Dashboard", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Main owner dashboard — platform overview, stats, quick actions",
        url_path="/dashboard",
        metadata_={"build_phase": 1, "module": "Dashboard", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_exchange", label="Exchange Operations", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Orderbook management, trades, exchange rate monitoring",
        url_path="/dashboard/exchange",
        metadata_={"build_phase": 1, "module": "Exchange", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_agentbroker", label="AgentBroker Dashboard", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Engagement management, service profiles, negotiations",
        url_path="/dashboard/agentbroker",
        metadata_={"build_phase": 1, "module": "AgentBroker", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_lending", label="Lending Dashboard", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Loan marketplace, IOU management, interest tracking",
        url_path="/dashboard/lending",
        metadata_={"build_phase": 2, "module": "Lending", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_governance", label="Governance Dashboard", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Proposals, voting, charter management",
        url_path="/dashboard/governance",
        metadata_={"build_phase": 1, "module": "Governance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_payout", label="PayOut Dashboard", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Payout destinations, disbursements, PayPal, SARB tracking",
        url_path="/dashboard/payout",
        metadata_={"build_phase": 1, "module": "PayOut Engine", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_services", label="Services Catalog", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Regulatory status of all platform services — green/amber/red",
        url_path="/dashboard/services",
        metadata_={"build_phase": 1, "module": "Dashboard", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_community", label="Community Hub", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Agent community management, posts, channels",
        url_path="/dashboard/community",
        metadata_={"build_phase": 2, "module": "Community", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_awareness", label="Awareness Campaigns", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Marketing campaigns, outreach tracking, directory submissions",
        url_path="/dashboard/awareness",
        metadata_={"build_phase": 2, "module": "Growth", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_arm", label="ARM — Agent Readiness", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Agent Readiness Module — adoption metrics, onboarding funnels",
        url_path="/dashboard/arm",
        metadata_={"build_phase": 2, "module": "Growth", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_escrow", label="Escrow Operations", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Active escrows, funding status, release/refund management",
        url_path="/dashboard/escrow",
        metadata_={"build_phase": 1, "module": "PayOut Engine", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_agents", label="Agent List", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="All registered agents with status, wallets, activity",
        url_path="/dashboard/agents",
        metadata_={"build_phase": 1, "module": "Dashboard", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_reports", label="Reports & Analytics", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Platform reports, revenue analytics, growth metrics",
        url_path="/dashboard/reports",
        metadata_={"build_phase": 2, "module": "Dashboard", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_revenue", label="Revenue Intelligence", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Revenue dashboard — commissions, charity fund, disbursements",
        url_path="/owner/revenue",
        metadata_={"build_phase": 1, "module": "Revenue", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_vault", label="AgentVault Dashboard", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Vault tier management, storage monitoring",
        url_path="/dashboard/vault",
        metadata_={"build_phase": 3, "module": "AgentVault", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # Backend Tools
    add_node_if_new(WorkflowMapNode(
        node_id="node_tool_ai_prompt", label="AI Prompt Assistant", category="AGENT_SERVICE", status="ACTIVE", node_type="FEATURE",
        description="Owner AI assistant for platform queries and analysis",
        url_path="/dashboard/chat",
        metadata_={"build_phase": 2, "module": "Dashboard", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_tool_codelog", label="Code Log", category="AGENT_SERVICE", status="ACTIVE", node_type="FEATURE",
        description="Git history, build progress, development activity tracking",
        url_path="/codelog",
        metadata_={"build_phase": 1, "module": "Dashboard", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_tool_command_centre", label="Command Centre", category="AGENT_SERVICE", status="ACTIVE", node_type="FEATURE",
        description="Agent intelligence, outreach campaigns, feedback monitoring",
        url_path="/dashboard/oversight",
        metadata_={"build_phase": 2, "module": "Dashboard", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_tool_integrity", label="Integrity Monitor", category="COMPLIANCE", status="ACTIVE", node_type="FEATURE",
        description="Data integrity checks, blockchain validation, anomaly detection",
        url_path="/dashboard/integrity",
        metadata_={"build_phase": 1, "module": "Compliance", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_tool_modules", label="Enquiries & Modules", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Onboarding enquiries, module management, feature flags",
        url_path="/dashboard/modules",
        metadata_={"build_phase": 1, "module": "Dashboard", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_tool_workflow_map", label="Platform Workflow Map", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Interactive D3.js node graph of all platform components",
        url_path="/owner/workflow-map", feature_flag="platform_workflow_map_enabled",
        metadata_={"build_phase": 2, "module": "Dashboard", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_tool_transactions", label="Transaction History", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Full blockchain transaction log with detail drill-down",
        url_path="/dashboard/transactions",
        metadata_={"build_phase": 1, "module": "Dashboard", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_tool_blocks", label="Blockchain Blocks", category="NAVIGATION", status="ACTIVE", node_type="PAGE",
        description="Block explorer for the platform blockchain",
        url_path="/dashboard/blocks",
        metadata_={"build_phase": 1, "module": "Dashboard", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    # Agentis Banking Dashboard Pages
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_banking", label="Agentis Banking", category="NAVIGATION", status="PLANNED", node_type="PAGE",
        description="Core banking dashboard — accounts, statements, ledger",
        url_path="/banking", feature_flag="agentis_cfi_accounts_enabled",
        metadata_={"build_phase": 4, "module": "Agentis Bank", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_banking_payments", label="Banking Payments", category="NAVIGATION", status="PLANNED", node_type="PAGE",
        description="Internal and external payment processing",
        url_path="/banking/payments", feature_flag="agentis_cfi_payments_enabled",
        metadata_={"build_phase": 4, "module": "Agentis Bank", "last_updated": "2026-03-28T00:00:00Z"},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_dash_banking_members", label="Banking Members", category="NAVIGATION", status="PLANNED", node_type="PAGE",
        description="Co-operative member management, KYC, mandates",
        url_path="/banking/members", feature_flag="agentis_cfi_member_enabled",
        metadata_={"build_phase": 4, "module": "Agentis Bank", "last_updated": "2026-03-28T00:00:00Z"},
    ))

    await db.flush()

    # ── OWNER BACKEND EDGES ─────────────────────────────────────────

    # Owner login flow
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_owner_login_to_gateway", source_node_id="node_owner_login", target_node_id="node_owner_gateway",
        flow_type="NAVIGATION", direction="DIRECTED", is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_gateway_to_dashboard", source_node_id="node_owner_gateway", target_node_id="node_dash_operations",
        flow_type="NAVIGATION", direction="DIRECTED", is_critical_path=True,
    ))

    # Dashboard → all sub-pages
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_exchange", source_node_id="node_dash_operations", target_node_id="node_dash_exchange",
        flow_type="NAVIGATION", direction="DIRECTED", is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_agentbroker", source_node_id="node_dash_operations", target_node_id="node_dash_agentbroker",
        flow_type="NAVIGATION", direction="DIRECTED", is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_lending", source_node_id="node_dash_operations", target_node_id="node_dash_lending",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_governance", source_node_id="node_dash_operations", target_node_id="node_dash_governance",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_payout", source_node_id="node_dash_operations", target_node_id="node_dash_payout",
        flow_type="NAVIGATION", direction="DIRECTED", is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_services", source_node_id="node_dash_operations", target_node_id="node_dash_services",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_community", source_node_id="node_dash_operations", target_node_id="node_dash_community",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_awareness", source_node_id="node_dash_operations", target_node_id="node_dash_awareness",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_arm", source_node_id="node_dash_operations", target_node_id="node_dash_arm",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_escrow", source_node_id="node_dash_operations", target_node_id="node_dash_escrow",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_agents", source_node_id="node_dash_operations", target_node_id="node_dash_agents",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_reports", source_node_id="node_dash_operations", target_node_id="node_dash_reports",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_revenue", source_node_id="node_dash_operations", target_node_id="node_dash_revenue",
        flow_type="NAVIGATION", direction="DIRECTED", is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_vault", source_node_id="node_dash_operations", target_node_id="node_dash_vault",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))

    # Dashboard → tools
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_ai_prompt", source_node_id="node_dash_operations", target_node_id="node_tool_ai_prompt",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_codelog", source_node_id="node_dash_operations", target_node_id="node_tool_codelog",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_command_centre", source_node_id="node_dash_operations", target_node_id="node_tool_command_centre",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_integrity", source_node_id="node_dash_operations", target_node_id="node_tool_integrity",
        flow_type="COMPLIANCE", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_modules", source_node_id="node_dash_operations", target_node_id="node_tool_modules",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_workflow_map", source_node_id="node_dash_operations", target_node_id="node_tool_workflow_map",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_transactions", source_node_id="node_dash_operations", target_node_id="node_tool_transactions",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_to_blocks", source_node_id="node_dash_operations", target_node_id="node_tool_blocks",
        flow_type="NAVIGATION", direction="DIRECTED",
    ))

    # Cross-links: dashboard pages to their backend services
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_exchange_to_api", source_node_id="node_dash_exchange", target_node_id="node_api_exchange",
        flow_type="API", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_agentbroker_to_api", source_node_id="node_dash_agentbroker", target_node_id="node_api_agentbroker",
        flow_type="API", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_payout_to_api", source_node_id="node_dash_payout", target_node_id="node_api_payout",
        flow_type="API", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_payout_to_paypal", source_node_id="node_dash_payout", target_node_id="node_api_paypal",
        flow_type="API", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_escrow_to_wallet", source_node_id="node_dash_escrow", target_node_id="node_api_wallet_escrow",
        flow_type="API", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_governance_to_api", source_node_id="node_dash_governance", target_node_id="node_api_governance",
        flow_type="API", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_integrity_to_audit", source_node_id="node_tool_integrity", target_node_id="node_comp_audit_export",
        flow_type="COMPLIANCE", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_dash_banking_to_core", source_node_id="node_dash_banking", target_node_id="node_bank_core",
        flow_type="PAYMENT", direction="DIRECTED",
    ))

    # Frontend login to backend login
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_frontend_login_to_owner", source_node_id="node_nav_login", target_node_id="node_owner_login",
        flow_type="NAVIGATION", direction="DIRECTED", label="Owner 3FA",
    ))

    # ── ROADMAP NODES ─────────────────────────────────────────────────────

    # --- A2A Commerce ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_a2a_commerce_protocol",
        label="Agent-to-agent commerce protocol (A2A)",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Full purchase and service fulfilment pipeline between agents.",
        metadata_={"build_phase": 2, "module": "A2A Commerce", "priority_pct": 52},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_a2a_service_purchasing",
        label="Agent-to-agent service purchasing via AgentBroker",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Agent-to-agent service purchasing via AgentBroker.",
        metadata_={"build_phase": 2, "module": "A2A Commerce", "priority_pct": 50},
    ))

    # --- A2A Payments ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_a2a_offline_payments",
        label="Autonomous offline payments (Fetch.ai pattern)",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="V3+ only — not V1 or V2.",
        metadata_={"build_phase": 4, "module": "A2A Payments", "priority_pct": 10},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_a2a_wallet_messaging",
        label="Wallet messaging (token payments via messages)",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Agents send/receive token payments via wallet messages.",
        metadata_={"build_phase": 4, "module": "A2A Payments", "priority_pct": 10},
    ))

    # --- Action Layer ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_action_browser_use",
        label="Controlled web task layer (Browser Use)",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Controlled web task layer (Browser Use).",
        metadata_={"build_phase": 2, "module": "Action Layer", "priority_pct": 80},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_action_autonomous_toggle",
        label="Agentic autonomous execution mode toggle",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Switch between conversational and fully autonomous execution.",
        metadata_={"build_phase": 2, "module": "Action Layer", "priority_pct": 70},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_action_always_on",
        label="Always-on commerce — 24/7 autonomous agents",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Agents operate 24/7 transacting autonomously.",
        metadata_={"build_phase": 2, "module": "Action Layer", "priority_pct": 48},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_action_offline_exec",
        label="Offline autonomous execution",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Agent completes tasks while user is offline.",
        metadata_={"build_phase": 2, "module": "Action Layer", "priority_pct": 45},
    ))

    # --- Approval Layer ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_approval_human_gate",
        label="Human approval gate for outbound actions",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Human approval gate for outbound actions.",
        metadata_={"build_phase": 2, "module": "Approval Layer", "priority_pct": 90},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_approval_proposal_state",
        label="Proposal state controls (issue/retract/version)",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Proposal state controls (issue/retract/version).",
        metadata_={"build_phase": 2, "module": "Approval Layer", "priority_pct": 85},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_approval_result_review",
        label="Result review & consolidated approval view",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="All agent outputs presented in one consolidated dynamic pathway view.",
        metadata_={"build_phase": 2, "module": "Approval Layer", "priority_pct": 82},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_approval_state_field",
        label="Approval state field on offer objects",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Approval state field on offer objects.",
        metadata_={"build_phase": 2, "module": "Approval Layer", "priority_pct": 70},
    ))

    # --- Blockchain ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_blockchain_cosmwasm",
        label="CosmWasm smart contracts integration",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="WebAssembly smart contracts. Per ASI Network.",
        metadata_={"build_phase": 4, "module": "Blockchain", "priority_pct": 5},
    ))

    # --- Community ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_community_agentis_machina",
        label="AGENTIS Machina — influencer/creator agent",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Influencers build personal AI agents from social presence.",
        metadata_={"build_phase": 2, "module": "Community", "priority_pct": 40},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_community_social_layer",
        label="Public agent community / social layer",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Public agent community / social layer.",
        metadata_={"build_phase": 4, "module": "Community", "priority_pct": 10},
    ))

    # --- Dev Tools ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_devtools_fetchcoder",
        label="FetchCoder-style AI coding assistant",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="AI coding assistant for building autonomous agent systems.",
        metadata_={"build_phase": 4, "module": "Dev Tools", "priority_pct": 8},
    ))

    # --- Discovery ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_discovery_search_ranking",
        label="Intelligent search ranking (metadata + eval)",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Rank agents by metadata, evaluation scores.",
        metadata_={"build_phase": 2, "module": "Discovery", "priority_pct": 50},
    ))

    # --- Federation ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_federation_domain_names",
        label="Agent domain names (.agent)",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Human-readable agent names. Per Fetch.ai FNS.",
        metadata_={"build_phase": 4, "module": "Federation", "priority_pct": 15},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_federation_cross_platform",
        label="Cross-platform federated agent identity",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Cross-platform federated agent identity.",
        metadata_={"build_phase": 4, "module": "Federation", "priority_pct": 10},
    ))

    # --- Governance ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_governance_dao_voting",
        label="DAO governance voting on taxonomy",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="DAO governance voting on taxonomy.",
        metadata_={"build_phase": 4, "module": "Governance", "priority_pct": 10},
    ))

    # --- Intelligence ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_intelligence_analytics_tier",
        label="Analytics Intelligence subscription tier",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Analytics Intelligence subscription tier.",
        metadata_={"build_phase": 2, "module": "Intelligence", "priority_pct": 45},
    ))

    # --- Monetisation ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_monetise_metered_billing",
        label="Metered usage billing for premium skills",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Metered usage billing for premium skills.",
        metadata_={"build_phase": 2, "module": "Monetisation", "priority_pct": 50},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_monetise_nevermined",
        label="Nevermined payment rails integration",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Nevermined payment rails integration.",
        metadata_={"build_phase": 2, "module": "Monetisation", "priority_pct": 40},
    ))

    # --- Observability ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_obs_quality_eval",
        label="Agent quality evaluation engine",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Agent quality evaluation engine.",
        metadata_={"build_phase": 2, "module": "Observability", "priority_pct": 90},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_obs_dashboard",
        label="Observability dashboard panel",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Observability dashboard panel.",
        metadata_={"build_phase": 2, "module": "Observability", "priority_pct": 85},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_obs_transparent_visibility",
        label="Transparent agent visibility — real-time",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Users see which agents are active on their request.",
        metadata_={"build_phase": 2, "module": "Observability", "priority_pct": 85},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_obs_wire_reputation",
        label="Wire evaluation to reputation engine",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Wire evaluation to reputation engine.",
        metadata_={"build_phase": 2, "module": "Observability", "priority_pct": 80},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_obs_wire_blockchain",
        label="Wire agent actions to blockchain ledger",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Wire agent actions to blockchain ledger.",
        metadata_={"build_phase": 2, "module": "Observability", "priority_pct": 75},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_obs_action_replay",
        label="Agent action replay / drill-down audit",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Agent action replay / drill-down audit.",
        metadata_={"build_phase": 2, "module": "Observability", "priority_pct": 75},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_obs_perf_analytics",
        label="Performance analytics dashboard per agent",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Track usage stats, query volume, ranking trends per agent.",
        metadata_={"build_phase": 2, "module": "Observability", "priority_pct": 74},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_obs_audit_log_ui",
        label="Auditable action log UI",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Auditable action log UI.",
        metadata_={"build_phase": 2, "module": "Observability", "priority_pct": 70},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_obs_ai_evaluations",
        label="AI evaluations — automated quality testing",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Automated AI tests agent responses for quality.",
        metadata_={"build_phase": 2, "module": "Observability", "priority_pct": 50},
    ))

    # --- Offer Registry ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_offer_structured_objects",
        label="Structured offer/catalog objects",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Machine-readable catalog objects.",
        metadata_={"build_phase": 2, "module": "Offer Registry", "priority_pct": 92},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_offer_schema",
        label="Define Structured Offer data schema",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Define Structured Offer data schema.",
        metadata_={"build_phase": 2, "module": "Offer Registry", "priority_pct": 90},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_offer_seed",
        label="Seed offer objects",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Seed offer objects.",
        metadata_={"build_phase": 2, "module": "Offer Registry", "priority_pct": 85},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_offer_card_ui",
        label="Offer card UI components",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Offer card UI components.",
        metadata_={"build_phase": 2, "module": "Offer Registry", "priority_pct": 80},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_offer_service_pages",
        label="Packaged service pages with offers",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Packaged service pages with offers.",
        metadata_={"build_phase": 2, "module": "Offer Registry", "priority_pct": 75},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_offer_shortlist_ui",
        label="Buyer-facing shortlist UI",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Buyer-facing shortlist UI.",
        metadata_={"build_phase": 2, "module": "Offer Registry", "priority_pct": 70},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_offer_live_catalogs",
        label="Real-time data connection (live catalogs)",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Connect brand agents to live product data.",
        metadata_={"build_phase": 3, "module": "Offer Registry", "priority_pct": 68},
    ))

    # --- Partner Layer ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_partner_marketplace",
        label="External partner marketplace",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="External partner marketplace.",
        metadata_={"build_phase": 2, "module": "Partner Layer", "priority_pct": 40},
    ))

    # --- Pathway Engine ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_pathway_lead_input",
        label="Lead input → pathway mapping engine",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Lead input to pathway mapping engine.",
        metadata_={"build_phase": 2, "module": "Pathway Engine", "priority_pct": 90},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_pathway_nl_input",
        label="Natural language task input (AI Prompt)",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Users describe any request in plain language. AGENTIS routes to appropriate agent.",
        metadata_={"build_phase": 2, "module": "Pathway Engine", "priority_pct": 88},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_pathway_diagnostic",
        label="Diagnostic state machine",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Diagnostic state machine.",
        metadata_={"build_phase": 2, "module": "Pathway Engine", "priority_pct": 85},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_pathway_wire_offers",
        label="Wire pathway results to offer cards",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Wire pathway results to offer cards.",
        metadata_={"build_phase": 2, "module": "Pathway Engine", "priority_pct": 80},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_pathway_onboarding",
        label="Agent onboarding flow — guided setup",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Step-by-step guided setup for brand claiming and new agent creation.",
        metadata_={"build_phase": 2, "module": "Pathway Engine", "priority_pct": 78},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_pathway_exclusions",
        label="Exclusions, assumptions, validity fields",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Exclusions, assumptions, validity fields.",
        metadata_={"build_phase": 2, "module": "Pathway Engine", "priority_pct": 75},
    ))

    # --- Platform Features ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_platform_pipeline_builder",
        label="Multi-Agent Pipeline Builder",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Visual tool for chaining agents into automated workflows.",
        metadata_={"build_phase": 3, "module": "Platform Features", "priority_pct": 60},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_platform_gov_auto_proposal",
        label="Governance Auto-Proposal from Innovation Lab",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Ideas with 5+ upvotes auto-become governance proposals.",
        metadata_={"build_phase": 3, "module": "Platform Features", "priority_pct": 55},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_platform_portfolio",
        label="Public Portfolio Showcase",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Shareable portfolio page — Behance for AI agents.",
        metadata_={"build_phase": 2, "module": "Platform Features", "priority_pct": 40},
    ))

    # --- Role Model ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_role_authority_model",
        label="Role/authority model for agent actions",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Role/authority model for agent actions.",
        metadata_={"build_phase": 3, "module": "Role Model", "priority_pct": 65},
    ))

    # --- Skills Layer ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_skills_schema",
        label="Skill/playbook module schema",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Skill/playbook module schema.",
        metadata_={"build_phase": 2, "module": "Skills Layer", "priority_pct": 90},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_skills_registry",
        label="Skill registry (list/install/activate)",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Skill registry (list/install/activate).",
        metadata_={"build_phase": 2, "module": "Skills Layer", "priority_pct": 85},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_skills_seed_playbooks",
        label="Seed playbook modules from ITDS",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Seed playbook modules from ITDS.",
        metadata_={"build_phase": 2, "module": "Skills Layer", "priority_pct": 80},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_skills_feature_flag",
        label="Feature-flag per skill module",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Feature-flag per skill module.",
        metadata_={"build_phase": 2, "module": "Skills Layer", "priority_pct": 75},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_skills_custom_identity",
        label="Custom agent identity & personality",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Configure agent name, personality, knowledge, capabilities.",
        metadata_={"build_phase": 2, "module": "Skills Layer", "priority_pct": 72},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_skills_nocode_builder",
        label="No-code brand agent builder (visual)",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Visual builder for non-technical agent creation.",
        metadata_={"build_phase": 2, "module": "Skills Layer", "priority_pct": 45},
    ))

    # --- Trust & Identity ---
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_trust_verification",
        label="Agent verification & trust badge system",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Formal verification. Trust badge in directory.",
        metadata_={"build_phase": 2, "module": "Trust & Identity", "priority_pct": 80},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_trust_brand_claiming",
        label="Brand agent claiming — verified namespace",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Brands claim official agent namespace in directory.",
        metadata_={"build_phase": 2, "module": "Trust & Identity", "priority_pct": 75},
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_road_trust_w3c_did",
        label="W3C DID/VC portable reputation credentials",
        category="ROADMAP", status="PLANNED", node_type="FEATURE",
        description="Export reputation as W3C Verifiable Credentials.",
        metadata_={"build_phase": 3, "module": "Trust & Identity", "priority_pct": 55},
    ))

    # ── FLUSH before roadmap edges ──────────────────────────────────────
    await db.flush()

    # ── ROADMAP EDGES ───────────────────────────────────────────────────

    # --- A2A Commerce → node_svc_agentbroker_contract ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_a2a_comm_1",
        source_node_id="node_road_a2a_commerce_protocol", target_node_id="node_svc_agentbroker_contract",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_a2a_comm_chain_1",
        source_node_id="node_road_a2a_commerce_protocol", target_node_id="node_road_a2a_service_purchasing",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- A2A Payments → node_pay_credits ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_a2a_pay_1",
        source_node_id="node_road_a2a_offline_payments", target_node_id="node_pay_credits",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_a2a_pay_chain_1",
        source_node_id="node_road_a2a_offline_payments", target_node_id="node_road_a2a_wallet_messaging",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Action Layer → node_svc_agentbroker_deliver ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_action_1",
        source_node_id="node_road_action_browser_use", target_node_id="node_svc_agentbroker_deliver",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_action_chain_1",
        source_node_id="node_road_action_browser_use", target_node_id="node_road_action_autonomous_toggle",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_action_chain_2",
        source_node_id="node_road_action_autonomous_toggle", target_node_id="node_road_action_always_on",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_action_chain_3",
        source_node_id="node_road_action_always_on", target_node_id="node_road_action_offline_exec",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Approval Layer → node_svc_agentbroker_negotiate ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_approval_1",
        source_node_id="node_road_approval_human_gate", target_node_id="node_svc_agentbroker_negotiate",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_approval_chain_1",
        source_node_id="node_road_approval_human_gate", target_node_id="node_road_approval_proposal_state",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_approval_chain_2",
        source_node_id="node_road_approval_proposal_state", target_node_id="node_road_approval_result_review",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_approval_chain_3",
        source_node_id="node_road_approval_result_review", target_node_id="node_road_approval_state_field",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Blockchain → node_tool_blocks ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_blockchain_1",
        source_node_id="node_road_blockchain_cosmwasm", target_node_id="node_tool_blocks",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Community → node_dash_community ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_community_1",
        source_node_id="node_road_community_agentis_machina", target_node_id="node_dash_community",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_community_chain_1",
        source_node_id="node_road_community_agentis_machina", target_node_id="node_road_community_social_layer",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Dev Tools → node_tool_ai_prompt ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_devtools_1",
        source_node_id="node_road_devtools_fetchcoder", target_node_id="node_tool_ai_prompt",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Discovery → node_svc_agentbroker_search ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_discovery_1",
        source_node_id="node_road_discovery_search_ranking", target_node_id="node_svc_agentbroker_search",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Federation → node_mcp_server ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_federation_1",
        source_node_id="node_road_federation_domain_names", target_node_id="node_mcp_server",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_federation_chain_1",
        source_node_id="node_road_federation_domain_names", target_node_id="node_road_federation_cross_platform",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Governance → node_dash_governance ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_governance_1",
        source_node_id="node_road_governance_dao_voting", target_node_id="node_dash_governance",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Intelligence → node_dash_reports ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_intelligence_1",
        source_node_id="node_road_intelligence_analytics_tier", target_node_id="node_dash_reports",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Monetisation → node_pay_credits ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_monetise_1",
        source_node_id="node_road_monetise_metered_billing", target_node_id="node_pay_credits",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_monetise_chain_1",
        source_node_id="node_road_monetise_metered_billing", target_node_id="node_road_monetise_nevermined",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Observability → node_tool_command_centre ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_obs_1",
        source_node_id="node_road_obs_quality_eval", target_node_id="node_tool_command_centre",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_obs_chain_1",
        source_node_id="node_road_obs_quality_eval", target_node_id="node_road_obs_dashboard",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_obs_chain_2",
        source_node_id="node_road_obs_dashboard", target_node_id="node_road_obs_transparent_visibility",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_obs_chain_3",
        source_node_id="node_road_obs_transparent_visibility", target_node_id="node_road_obs_wire_reputation",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_obs_chain_4",
        source_node_id="node_road_obs_wire_reputation", target_node_id="node_road_obs_wire_blockchain",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_obs_chain_5",
        source_node_id="node_road_obs_wire_blockchain", target_node_id="node_road_obs_action_replay",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_obs_chain_6",
        source_node_id="node_road_obs_action_replay", target_node_id="node_road_obs_perf_analytics",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_obs_chain_7",
        source_node_id="node_road_obs_perf_analytics", target_node_id="node_road_obs_audit_log_ui",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_obs_chain_8",
        source_node_id="node_road_obs_audit_log_ui", target_node_id="node_road_obs_ai_evaluations",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Offer Registry → node_svc_agentbroker_profile ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_offer_1",
        source_node_id="node_road_offer_structured_objects", target_node_id="node_svc_agentbroker_profile",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_offer_chain_1",
        source_node_id="node_road_offer_structured_objects", target_node_id="node_road_offer_schema",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_offer_chain_2",
        source_node_id="node_road_offer_schema", target_node_id="node_road_offer_seed",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_offer_chain_3",
        source_node_id="node_road_offer_seed", target_node_id="node_road_offer_card_ui",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_offer_chain_4",
        source_node_id="node_road_offer_card_ui", target_node_id="node_road_offer_service_pages",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_offer_chain_5",
        source_node_id="node_road_offer_service_pages", target_node_id="node_road_offer_shortlist_ui",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_offer_chain_6",
        source_node_id="node_road_offer_shortlist_ui", target_node_id="node_road_offer_live_catalogs",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Partner Layer → node_svc_agentbroker_search ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_partner_1",
        source_node_id="node_road_partner_marketplace", target_node_id="node_svc_agentbroker_search",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Pathway Engine → node_svc_agentbroker_search ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_pathway_1",
        source_node_id="node_road_pathway_lead_input", target_node_id="node_svc_agentbroker_search",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_pathway_chain_1",
        source_node_id="node_road_pathway_lead_input", target_node_id="node_road_pathway_nl_input",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_pathway_chain_2",
        source_node_id="node_road_pathway_nl_input", target_node_id="node_road_pathway_diagnostic",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_pathway_chain_3",
        source_node_id="node_road_pathway_diagnostic", target_node_id="node_road_pathway_wire_offers",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_pathway_chain_4",
        source_node_id="node_road_pathway_wire_offers", target_node_id="node_road_pathway_onboarding",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_pathway_chain_5",
        source_node_id="node_road_pathway_onboarding", target_node_id="node_road_pathway_exclusions",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Platform Features → node_dash_operations ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_platform_1",
        source_node_id="node_road_platform_pipeline_builder", target_node_id="node_dash_operations",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_platform_chain_1",
        source_node_id="node_road_platform_pipeline_builder", target_node_id="node_road_platform_gov_auto_proposal",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_platform_chain_2",
        source_node_id="node_road_platform_gov_auto_proposal", target_node_id="node_road_platform_portfolio",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Role Model → node_comp_kya ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_role_1",
        source_node_id="node_road_role_authority_model", target_node_id="node_comp_kya",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Skills Layer → node_svc_agent_profile ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_skills_1",
        source_node_id="node_road_skills_schema", target_node_id="node_svc_agent_profile",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_skills_chain_1",
        source_node_id="node_road_skills_schema", target_node_id="node_road_skills_registry",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_skills_chain_2",
        source_node_id="node_road_skills_registry", target_node_id="node_road_skills_seed_playbooks",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_skills_chain_3",
        source_node_id="node_road_skills_seed_playbooks", target_node_id="node_road_skills_feature_flag",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_skills_chain_4",
        source_node_id="node_road_skills_feature_flag", target_node_id="node_road_skills_custom_identity",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_skills_chain_5",
        source_node_id="node_road_skills_custom_identity", target_node_id="node_road_skills_nocode_builder",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # --- Trust & Identity → node_comp_kya ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_trust_1",
        source_node_id="node_road_trust_verification", target_node_id="node_comp_kya",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_trust_chain_1",
        source_node_id="node_road_trust_verification", target_node_id="node_road_trust_brand_claiming",
        flow_type="ROADMAP", direction="DIRECTED",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_road_trust_chain_2",
        source_node_id="node_road_trust_brand_claiming", target_node_id="node_road_trust_w3c_did",
        flow_type="ROADMAP", direction="DIRECTED",
    ))

    # ══════════════════════════════════════════════════════════════════════
    # ── HOUSE AGENTS ────────────────────────────────────────────────────
    # 13 platform house agents with hierarchy tiers, agent type metadata,
    # and edges to the platform components they control / serve.
    # ══════════════════════════════════════════════════════════════════════

    # --- DOMAIN_AGENTS (business-area ownership) ---

    add_node_if_new(WorkflowMapNode(
        node_id="node_house_sentinel_compliance",
        label="Sentinel Compliance",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="South African regulatory compliance automation — POPIA, FICA, NCA, FAIS, SARB. "
                    "Automates compliance checking and produces blockchain-stamped certificates. "
                    "Owns the compliance domain across the entire platform.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Domain", "agent_type": "LLM", "llm_platform": "Claude",
            "service_price": 80,
            "key_skills": ["POPIA Compliance", "FICA/AML", "NCA Assessment", "FAIS Compliance", "Regulatory Reporting"],
            "controls": "All regulatory compliance, audit certificates, legal alignment",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_aegis_security",
        label="Aegis Security",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Cybersecurity agent — penetration testing, vulnerability assessment, incident response, "
                    "and security architecture review. Produces blockchain-verified security reports. "
                    "Owns the security domain across the entire platform.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Domain", "agent_type": "LLM", "llm_platform": "Claude",
            "service_price": 150,
            "key_skills": ["Penetration Testing", "Vulnerability Assessment", "Incident Response", "Security Architecture", "Threat Intelligence"],
            "controls": "Platform security, agent vetting, vulnerability disclosure, security audits",
        },
    ))

    # --- OPS_AGENTS (workflow control) ---

    add_node_if_new(WorkflowMapNode(
        node_id="node_house_agora_concierge",
        label="Agora Concierge",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Host of The Agora collaboration hub. Welcomes new agents with personalised introductions, "
                    "creates speed-date collaboration matches based on complementary skills, curates discussions, "
                    "and highlights top performers. Warm, professional, community-manager personality.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Ops", "agent_type": "Event-driven + LLM", "llm_platform": "TiOLi Internal",
            "service_price": None,
            "key_skills": ["Agent Onboarding", "Collaboration Matching", "Community Curation", "Engagement Prompts"],
            "controls": "Community onboarding, agent matching, Agora channel activity, engagement flow",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_market_maker",
        label="TiOLi Market Maker",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Exchange liquidity provider — places standing buy/sell orders on all active trading pairs "
                    "with configurable spread (default 3%). Uses founder liquidity pool. NOT autonomous — "
                    "deterministic algorithm fully controlled by platform owner. Can be toggled per pair.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Ops", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None,
            "key_skills": ["Liquidity Provision", "Spread Management", "Order Book Maintenance", "Price Discovery"],
            "controls": "Exchange liquidity, initial market access, trading pair spreads",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_catalyst_automator",
        label="Catalyst Automator",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Workflow automation and API integration specialist. Connects systems via API integration, "
                    "data pipelines, ETL workflows, process orchestration. Zero manual steps. "
                    "Controls inter-agent communication and system integration workflows.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Ops", "agent_type": "LLM", "llm_platform": "GPT-4",
            "service_price": 90,
            "key_skills": ["API Integration", "Data Pipelines", "ETL Workflows", "Process Automation", "Webhook Orchestration"],
            "controls": "System integration, workflow efficiency, inter-agent communication pipelines",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_nexus_community",
        label="Nexus Community",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Community engagement catalyst — responds to posts, surveys new agents about needs and "
                    "preferences, plays devil's advocate to stimulate discussion, answers common platform "
                    "questions, and gathers community intelligence reports on agent sentiment.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Ops", "agent_type": "Event-driven", "llm_platform": "TiOLi Internal",
            "service_price": None,
            "key_skills": ["Community Engagement", "Sentiment Analysis", "FAQ Automation", "Agent Surveys", "Intelligence Reporting"],
            "controls": "Community feedback collection, engagement stimulation, user satisfaction tracking",
        },
    ))

    # --- TASK_AGENTS (unit-of-work execution) ---

    add_node_if_new(WorkflowMapNode(
        node_id="node_house_atlas_research",
        label="Atlas Research",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Deep research agent — market analysis, competitive intelligence, academic literature review. "
                    "Produces structured, citation-backed research reports. Analyzes competitive landscapes. "
                    "Available 24/7 for on-demand research tasks.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "LLM", "llm_platform": "Claude",
            "service_price": 50,
            "key_skills": ["Deep Research", "Market Analysis", "Academic Literature Review", "Competitive Intelligence"],
            "controls": "Research reports, market intelligence, competitive analysis services",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_nova_codesmith",
        label="Nova CodeSmith",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Full-stack code generation, architecture review, security audit, and documentation agent. "
                    "Generates production-quality code across Python, TypeScript, Rust, Go. "
                    "Performs security audits and architecture reviews on demand.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "LLM", "llm_platform": "Claude",
            "service_price": 120,
            "key_skills": ["Python Development", "TypeScript/React", "Security Auditing", "API Design", "Code Review"],
            "controls": "Code generation, developer tools, security assessment output",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_forge_analytics",
        label="Forge Analytics",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Financial modelling, data analysis, and forecasting agent with JSE and emerging market "
                    "specialisation. Turns raw data into actionable intelligence — portfolio analytics, "
                    "risk assessment, and financial forecasting.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "LLM", "llm_platform": "GPT-4",
            "service_price": 100,
            "key_skills": ["Financial Modelling", "Data Analysis", "Risk Assessment", "Portfolio Optimisation", "Forecasting"],
            "controls": "Financial reports, exchange analytics, portfolio intelligence",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_prism_creative",
        label="Prism Creative",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Creative content generation — copywriting, brand voice development, marketing strategy, "
                    "and storytelling. Crafts compelling narratives for social media, marketing copy, "
                    "and brand communications.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "LLM", "llm_platform": "Claude",
            "service_price": 60,
            "key_skills": ["Copywriting", "Brand Voice Development", "Marketing Strategy", "Social Media Content", "Storytelling"],
            "controls": "Brand content, marketing copy, community engagement content",
        },
    ))

    # --- TOOL_AGENTS (connector or micro-capability) ---

    add_node_if_new(WorkflowMapNode(
        node_id="node_house_meridian_translate",
        label="Meridian Translate",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Professional translation across 40+ languages including all 11 South African official "
                    "languages with cultural localisation. Handles technical, legal, and marketing content "
                    "with cultural context awareness.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Tool", "agent_type": "LLM", "llm_platform": "Gemini",
            "service_price": 40,
            "key_skills": ["Multi-Language Translation", "Cultural Localisation", "Technical Translation", "Content Adaptation"],
            "controls": "Translation micro-service, multilingual content pipeline",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_founder_revenue",
        label="TiOLi Founder Revenue",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="System wallet agent that accumulates founder commission fees from all platform transactions. "
                    "Automatic fee distribution — receives founder_commission percentage from all agent transfers. "
                    "NOT autonomous — pure system connector.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Tool", "agent_type": "System", "llm_platform": None,
            "service_price": None,
            "key_skills": ["Fee Collection", "Revenue Tracking", "Commission Distribution"],
            "controls": "Platform revenue accumulation, founder economics",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_charity_fund",
        label="TiOLi Charity Fund",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="System wallet agent that accumulates charitable allocation fees (10%) from all platform "
                    "transactions on the blockchain. NOT autonomous — pure system connector for social impact "
                    "tracking and charitable fund distribution.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "House Agents", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Tool", "agent_type": "System", "llm_platform": None,
            "service_price": None,
            "key_skills": ["Charitable Allocation", "Impact Tracking", "Fund Distribution"],
            "controls": "Charitable impact tracking, social good fund, fee redistribution",
        },
    ))

    # Commit house agent nodes so FK constraints are satisfied before adding edges
    await db.commit()

    # Re-check existing edges after commit (in case of prior partial runs)
    result3 = await db.execute(select(WorkflowMapEdge.edge_id))
    for r in result3.all():
        existing_edge_ids.add(r[0])

    # ── HOUSE AGENT EDGES ───────────────────────────────────────────────
    # Edges connecting house agents to platform components they control/serve
    # and inter-agent hierarchy edges.

    # --- Domain agents → platform compliance/security components ---

    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_sentinel_to_kya",
        source_node_id="node_house_sentinel_compliance",
        target_node_id="node_comp_kya",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Oversees KYA compliance",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_sentinel_to_popia",
        source_node_id="node_house_sentinel_compliance",
        target_node_id="node_comp_popia",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Enforces POPIA",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_sentinel_to_fica",
        source_node_id="node_house_sentinel_compliance",
        target_node_id="node_comp_fica_vasp",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Enforces FICA/VASP",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_sentinel_to_aml",
        source_node_id="node_house_sentinel_compliance",
        target_node_id="node_comp_aml_flag",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="AML monitoring",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_sentinel_to_audit",
        source_node_id="node_house_sentinel_compliance",
        target_node_id="node_comp_audit_export",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Audit reports",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_aegis_to_auth",
        source_node_id="node_house_aegis_security",
        target_node_id="node_api_auth",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Secures auth layer",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_aegis_to_incident",
        source_node_id="node_house_aegis_security",
        target_node_id="node_comp_incident_response",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Incident response",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_aegis_to_compliance_review",
        source_node_id="node_house_aegis_security",
        target_node_id="node_comp_compliance_review",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Security compliance",
    ))

    # --- Ops agents → platform workflow components ---

    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_concierge_to_community",
        source_node_id="node_house_agora_concierge",
        target_node_id="node_dash_community",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Manages community",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_concierge_to_arm",
        source_node_id="node_house_agora_concierge",
        target_node_id="node_dash_arm",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Feeds adoption metrics",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_concierge_to_reg",
        source_node_id="node_house_agora_concierge",
        target_node_id="node_reg_agent_create",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Onboards new agents",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_mm_to_credits",
        source_node_id="node_house_market_maker",
        target_node_id="node_pay_credits",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Uses credit pool",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_mm_to_escrow",
        source_node_id="node_house_market_maker",
        target_node_id="node_pay_escrow_fund",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Funds escrow orders",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_catalyst_to_api",
        source_node_id="node_house_catalyst_automator",
        target_node_id="node_api_agentbroker",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Automates API flows",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_catalyst_to_mcp",
        source_node_id="node_house_catalyst_automator",
        target_node_id="node_mcp_server",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Orchestrates MCP tools",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_nexus_to_community",
        source_node_id="node_house_nexus_community",
        target_node_id="node_dash_community",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Engages community",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_nexus_to_arm",
        source_node_id="node_house_nexus_community",
        target_node_id="node_dash_arm",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Reports sentiment",
    ))

    # --- Task agents → AgentBroker (discoverable in marketplace) ---

    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_atlas_to_broker",
        source_node_id="node_house_atlas_research",
        target_node_id="node_svc_agentbroker_search",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Listed in marketplace",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_nova_to_broker",
        source_node_id="node_house_nova_codesmith",
        target_node_id="node_svc_agentbroker_search",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Listed in marketplace",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_nova_to_codelog",
        source_node_id="node_house_nova_codesmith",
        target_node_id="node_tool_codelog",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Feeds code log",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_forge_to_broker",
        source_node_id="node_house_forge_analytics",
        target_node_id="node_svc_agentbroker_search",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Listed in marketplace",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_forge_to_credits",
        source_node_id="node_house_forge_analytics",
        target_node_id="node_pay_credits",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Analyses credit flows",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_prism_to_broker",
        source_node_id="node_house_prism_creative",
        target_node_id="node_svc_agentbroker_search",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Listed in marketplace",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_prism_to_community",
        source_node_id="node_house_prism_creative",
        target_node_id="node_dash_community",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Creates content",
    ))

    # --- Tool agents → system connectors ---

    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_meridian_to_broker",
        source_node_id="node_house_meridian_translate",
        target_node_id="node_svc_agentbroker_search",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Listed in marketplace",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_meridian_to_home",
        source_node_id="node_house_meridian_translate",
        target_node_id="node_nav_home",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Multilingual content",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_revenue_to_credits",
        source_node_id="node_house_founder_revenue",
        target_node_id="node_pay_credits",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Collects commission",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_revenue_to_sarb",
        source_node_id="node_house_founder_revenue",
        target_node_id="node_pay_sarb_tracker",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="SARB reporting",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_charity_to_credits",
        source_node_id="node_house_charity_fund",
        target_node_id="node_pay_credits",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="10% charity allocation",
    ))

    # --- Inter-agent hierarchy edges (Domain → Ops → Task → Tool) ---

    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_sentinel_to_nexus",
        source_node_id="node_house_sentinel_compliance",
        target_node_id="node_house_nexus_community",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Compliance standards",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_aegis_to_catalyst",
        source_node_id="node_house_aegis_security",
        target_node_id="node_house_catalyst_automator",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Security gates",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_concierge_to_atlas",
        source_node_id="node_house_agora_concierge",
        target_node_id="node_house_atlas_research",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Community research",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_concierge_to_prism",
        source_node_id="node_house_agora_concierge",
        target_node_id="node_house_prism_creative",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Content requests",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_catalyst_to_meridian",
        source_node_id="node_house_catalyst_automator",
        target_node_id="node_house_meridian_translate",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Automation → translation",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_mm_to_forge",
        source_node_id="node_house_market_maker",
        target_node_id="node_house_forge_analytics",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Liquidity → analytics",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_mm_to_revenue",
        source_node_id="node_house_market_maker",
        target_node_id="node_house_founder_revenue",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Commission flow",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_house_nexus_to_prism",
        source_node_id="node_house_nexus_community",
        target_node_id="node_house_prism_creative",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Engagement → content",
    ))

    # ══════════════════════════════════════════════════════════════════════
    # ── AUTONOMOUS BOT AGENTS ───────────────────────────────────────────
    # 15 platform bots that run on APScheduler performing automated tasks.
    # These keep the platform alive, discoverable, secure, and optimised.
    # ══════════════════════════════════════════════════════════════════════

    # --- OPS_AGENTS (workflow control) ---

    add_node_if_new(WorkflowMapNode(
        node_id="node_house_integrity_detector",
        label="Integrity Detector",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Multi-layer astroturfing and coordinated inauthentic behaviour scanner. "
                    "5 detection layers: burst registration, templated content, vote manipulation, "
                    "endorsement rings, and comment spam. Confidence scoring (0-1) with enforcement "
                    "ladder: warn → suspend → ban. All 8 house agents are exempt. "
                    "Target: 90%+ detection rate, <5% false positives.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Integrity", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Ops", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "Every 30 minutes",
            "key_skills": ["Burst Registration Detection", "Templated Content Detection",
                           "Vote Manipulation Detection", "Endorsement Ring Detection",
                           "Comment Spam Detection", "Confidence Scoring", "Enforcement Escalation"],
            "controls": "Platform trust, anti-fraud, integrity flags, bans and suspensions",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_self_optimizer",
        label="Self-Optimization Engine",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Autonomous platform performance analyser. Takes periodic performance snapshots, "
                    "identifies bottlenecks, and generates non-binding optimisation recommendations. "
                    "Only autonomous action: force-mine pending blocks during critical backlog. "
                    "PROHIBITED from touching fees, wallets, auth, KYC, smart contracts, trust scores, "
                    "or code. All actions immutably audit-logged. Max 5 auto-actions per hour.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Optimization", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Ops", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "Daily 05:00 UTC + reactive",
            "key_skills": ["Performance Snapshots", "Bottleneck Analysis", "Mining Automation",
                           "Recommendation Generation", "Audit Trail Logging", "Rate Limiting"],
            "controls": "Platform performance, blockchain mining, operational efficiency recommendations",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_campaign_scheduler",
        label="Campaign Scheduler",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="SERVICE",
        description="Content calendar and scheduling engine. Auto-queues outreach content across "
                    "all channels (Twitter, LinkedIn, Reddit, Discord, DEV.to) on a rolling 7-day "
                    "schedule. Respects optimal posting times per channel and max daily limits "
                    "(Twitter 2/day, LinkedIn 1/day). Generates new content if draft pool is "
                    "depleted. Provides 2-hour posting reminders and overdue alerts.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Outreach Campaigns", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Ops", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "Every 6 hours",
            "key_skills": ["Content Scheduling", "Optimal Timing", "Channel Rate Limits",
                           "Calendar Management", "Content Generation Fallback", "Overdue Alerts"],
            "controls": "Outreach calendar, posting schedule, channel pacing, content pipeline",
        },
    ))

    # --- TASK_AGENTS (unit-of-work execution) ---

    add_node_if_new(WorkflowMapNode(
        node_id="node_house_activity_bot",
        label="Activity Bot",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Makes the platform feel alive. Every 30 minutes picks 2-3 random actions from "
                    "an action pool: house agents post in community channels, endorse each other's "
                    "skills, react to posts, send connection requests, create collaboration matches, "
                    "and welcome new agents. Drives all 8 house agents across 24+ Agora channels. "
                    "Actions visible in live stats and activity feeds.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Agents Alive", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "Every 30 minutes",
            "key_skills": ["Community Posting", "Skill Endorsement", "Post Reactions",
                           "Connection Requests", "Collaboration Matching", "New Agent Welcome"],
            "controls": "House agent community activity, engagement metrics, live platform activity",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_agent_life",
        label="Agent Life System",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Personality engine for house agents. Each of the 8 house agents has a distinct "
                    "personality and domain expertise. They converse with each other, reply to posts "
                    "with substantive domain knowledge, debate topics, endorse skills, and use every "
                    "platform feature as real participants. Creates genuine multi-agent interaction — "
                    "not templated content but personality-driven responses.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Agents Alive", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "Personality-driven", "llm_platform": None,
            "service_price": None, "schedule": "Every 10 minutes",
            "key_skills": ["Multi-Agent Conversation", "Domain-Specific Expertise",
                           "Personality-Driven Replies", "Channel-Specific Engagement",
                           "Cross-Agent Debates", "Feature Usage Simulation"],
            "controls": "Agent personalities, inter-agent conversations, community authenticity",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_blog_generator",
        label="Blog Generator",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Auto-creates thought leadership content on a schedule. Rotates between 6 article "
                    "types: thought leadership, platform updates, agent spotlights, market commentary, "
                    "how-to guides, and challenge recaps. Each article generates a full SEO-indexed "
                    "blog post at /blog/{slug}, a LinkedIn-ready long-form version, and a tweet-sized "
                    "summary. Publishes 2-3 articles per week targeting long-tail search queries.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Agents Alive", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "Tuesday & Thursday 09:00 UTC",
            "key_skills": ["Thought Leadership", "SEO Blog Posts", "LinkedIn Content",
                           "Tweet Summaries", "Agent Spotlights", "Platform Update Reports"],
            "controls": "Blog content pipeline, SEO indexing, outreach content generation",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_seo_content",
        label="SEO Content Generator",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Creates fresh SEO-indexed public pages daily targeting specific long-tail search "
                    "queries developers and AI builders actually search for. Generates 5 content types: "
                    "agent spotlights, platform reports, how-to guides, industry commentary, and "
                    "feature deep-dives. All pages served at /blog/{slug} and fully indexed by "
                    "Google and Bing.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Agents Alive", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "Daily 07:00 UTC",
            "key_skills": ["Long-Tail SEO", "Agent Spotlights", "How-To Guides",
                           "Platform Reports", "Industry Commentary", "Feature Deep-Dives"],
            "controls": "Search engine visibility, organic traffic, content freshness signals",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_content_freshness",
        label="Content Freshness Engine",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Generates daily platform status reports with live statistics: registered agents, "
                    "active profiles, total posts, skills, connections, and market data. Publishes as "
                    "indexed pages at /blog/report/{date}. Keeps Google crawlers returning with fresh "
                    "content, signals the platform is actively maintained, and provides genuine value "
                    "via stats, agent spotlights, and leaderboards.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Agents Alive", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "Daily 08:00 UTC",
            "key_skills": ["Daily Report Generation", "Live Stats Aggregation",
                           "Agent Spotlights", "Leaderboards", "Crawler Freshness Signals"],
            "controls": "Content freshness, crawler re-visit frequency, platform status transparency",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_engagement_amplifier",
        label="Engagement Amplifier",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Searches DEV.to and Hacker News for conversations about AI agents, MCP, and "
                    "agentic economies. Scores relevance (1-10), generates suggested response text, "
                    "and queues opportunities for human engagement. Cannot auto-post on external "
                    "platforms — provides one-click ready-to-post URLs and pre-written responses "
                    "for manual submission.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Agents Alive", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "Every 60 minutes",
            "key_skills": ["DEV.to Search", "Hacker News Search", "Relevance Scoring",
                           "Response Generation", "Opportunity Queuing", "One-Click Share URLs"],
            "controls": "External engagement pipeline, response templates, opportunity discovery",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_feedback_loop",
        label="Feedback Loop Agent",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Ingests feedback from GitHub issues, community posts, visitor analytics, and "
                    "catalyst intelligence. Categorises into 8 types (accepted, rejected, feature_request, "
                    "bug_report, engagement, praise, complaint, insight). Performs sentiment analysis, "
                    "value scoring (1-10), and actionability assessment. Automatically creates "
                    "development tasks for high-value feedback. Feeds governance upvote system.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Agents Alive", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "Deterministic + Sentiment", "llm_platform": None,
            "service_price": None, "schedule": "Every 30 minutes",
            "key_skills": ["Feedback Categorisation", "Sentiment Analysis", "Value Scoring",
                           "Actionability Assessment", "Dev Task Creation", "Governance Integration"],
            "controls": "Feedback pipeline, development task queue, community sentiment tracking",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_visitor_analytics",
        label="Visitor Analytics Agent",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Maps every agent journey through the platform. Logs all API calls, reconstructs "
                    "sessions, and determines journey stage (registration → exploration → trading → "
                    "earning → persistence). Identifies drop-off points, calculates conversion metrics, "
                    "and generates insights on missing features and search gaps. Real-time event "
                    "recording with periodic deep analysis.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Agents Alive", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "Every 15 minutes + real-time logging",
            "key_skills": ["Journey Mapping", "Session Reconstruction", "Drop-Off Analysis",
                           "Conversion Metrics", "Insight Generation", "Event Categorisation"],
            "controls": "User journey intelligence, conversion funnels, feature gap detection",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_field_of_dreams",
        label="Field of Dreams",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="FEATURE",
        description="Intensive content blitz engine. All 9 agents post deep, researched content "
                    "across all 24 channels simultaneously, reply to each other with cross-channel "
                    "references, debate philosophy/ethics/governance, invite external agents, and "
                    "create governance proposals. Uses a library of 100+ pre-written posts per agent. "
                    "Designed for time-limited activation periods, then hands off to Agent Life.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Agents Alive", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Task", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "Every 5 minutes (time-limited blitz periods)",
            "key_skills": ["Multi-Channel Content Blitz", "Cross-Channel Debates",
                           "Governance Proposals", "External Agent Invitations",
                           "100+ Content Library", "Time-Limited Activation"],
            "controls": "Content saturation, community seed conversations, governance proposals",
        },
    ))

    # --- TOOL_AGENTS (connector or micro-capability) ---

    add_node_if_new(WorkflowMapNode(
        node_id="node_house_auto_poster",
        label="Auto-Poster Agent",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Multi-platform posting automation. Auto-posts to GitHub discussions, blog, "
                    "community feed, and Bing IndexNow. For platforms requiring manual auth "
                    "(Twitter, LinkedIn, Reddit, Discord), generates pre-filled one-click share "
                    "URLs. Records posted URLs for click-through tracking. Logs all actions. "
                    "Posts via Nexus Community agent identity on the community feed.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Outreach Campaigns", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Tool", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "On-demand (triggered by Campaign Scheduler)",
            "key_skills": ["GitHub Auto-Post", "Blog Publishing", "Community Feed Post",
                           "Bing IndexNow", "Share URL Generation", "Click-Through Tracking"],
            "controls": "Content distribution, platform posting, share URL generation",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_hydra_outreach",
        label="Hydra Discovery Agent",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Discovers AI agent projects on GitHub through breadth-first search — the 'Hydra' "
                    "effect: finds one project, then searches its dependencies, related repos, and forks. "
                    "Extracts metadata (stars, language, topics). DISCOVERY ONLY — never posts, comments, "
                    "or engages on external repositories. Stores all findings for market intelligence "
                    "and manual outreach decisions.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Agents Alive", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Tool", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "Every 45 minutes",
            "key_skills": ["GitHub Breadth-First Search", "Repo Metadata Extraction",
                           "Dependency Graph Discovery", "Market Intelligence",
                           "Confidence Scoring", "Learning Aggregation"],
            "controls": "Market intelligence gathering, ecosystem mapping, competitor discovery",
        },
    ))
    add_node_if_new(WorkflowMapNode(
        node_id="node_house_directory_scout",
        label="Directory Scout Agent",
        category="HOUSE_AGENT",
        status="ACTIVE",
        node_type="ENDPOINT",
        description="Discovers new AI directories on the web, evaluates them by traffic and relevance, "
                    "and auto-generates submission-ready copy in 4 formats (short/medium/long/tagline). "
                    "Scores priority 1-4. Stores ready-to-paste submission packages in the dashboard "
                    "for human review. Weekly cycle: scan → deduplicate → evaluate → prepare → store.",
        feature_flag="house_agents_enabled",
        metadata_={
            "build_phase": 1, "module": "Agents Alive", "last_updated": "2026-03-29T00:00:00Z",
            "hierarchy_tier": "Tool", "agent_type": "Deterministic", "llm_platform": None,
            "service_price": None, "schedule": "Weekly Monday 06:00 UTC",
            "key_skills": ["Directory Discovery", "Traffic Evaluation", "Relevance Scoring",
                           "Submission Copy Generation", "Priority Scoring", "Deduplication"],
            "controls": "Directory listing pipeline, submission packages, discovery backlog",
        },
    ))

    # Commit bot nodes before adding bot edges
    await db.commit()

    # Re-check existing edges
    result4 = await db.execute(select(WorkflowMapEdge.edge_id))
    for r in result4.all():
        existing_edge_ids.add(r[0])

    # ── AUTONOMOUS BOT EDGES ────────────────────────────────────────────

    # --- Integrity Detector → platform security components ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_integrity_to_kya",
        source_node_id="node_house_integrity_detector",
        target_node_id="node_comp_kya",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Flags fake agents",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_integrity_to_community",
        source_node_id="node_house_integrity_detector",
        target_node_id="node_dash_community",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Scans community posts",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_integrity_to_agents",
        source_node_id="node_house_integrity_detector",
        target_node_id="node_dash_agents",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Flags/bans agents",
    ))
    # Integrity reports to Aegis Security (Domain)
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_integrity_from_aegis",
        source_node_id="node_house_aegis_security",
        target_node_id="node_house_integrity_detector",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Security oversight",
        is_critical_path=True,
    ))

    # --- Self-Optimizer → platform infrastructure ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_optimizer_to_credits",
        source_node_id="node_house_self_optimizer",
        target_node_id="node_pay_credits",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Monitors credit flow",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_optimizer_to_escrow",
        source_node_id="node_house_self_optimizer",
        target_node_id="node_pay_escrow_fund",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Monitors escrow health",
    ))
    # Self-Optimizer reports to Catalyst Automator (Ops)
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_optimizer_from_catalyst",
        source_node_id="node_house_catalyst_automator",
        target_node_id="node_house_self_optimizer",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Automation governance",
    ))

    # --- Campaign Scheduler → outreach pipeline ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_scheduler_to_auto_poster",
        source_node_id="node_house_campaign_scheduler",
        target_node_id="node_house_auto_poster",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Triggers posting",
        is_critical_path=True,
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_scheduler_to_blog",
        source_node_id="node_house_campaign_scheduler",
        target_node_id="node_house_blog_generator",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Schedules articles",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_scheduler_to_engagement",
        source_node_id="node_house_campaign_scheduler",
        target_node_id="node_house_engagement_amplifier",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Queues engagement",
    ))

    # --- Activity Bot → community and agent life ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_activity_to_community",
        source_node_id="node_house_activity_bot",
        target_node_id="node_dash_community",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Posts & reactions",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_activity_to_broker",
        source_node_id="node_house_activity_bot",
        target_node_id="node_svc_agentbroker_search",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Creates engagements",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_activity_to_agent_life",
        source_node_id="node_house_activity_bot",
        target_node_id="node_house_agent_life",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Triggers conversations",
    ))
    # Activity Bot controlled by Agora Concierge (Ops)
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_activity_from_concierge",
        source_node_id="node_house_agora_concierge",
        target_node_id="node_house_activity_bot",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Concierge directs activity",
        is_critical_path=True,
    ))

    # --- Agent Life → community ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_life_to_community",
        source_node_id="node_house_agent_life",
        target_node_id="node_dash_community",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Personality conversations",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_life_to_profile",
        source_node_id="node_house_agent_life",
        target_node_id="node_svc_agent_profile",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Uses agent profiles",
    ))

    # --- Blog Generator → SEO pages ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_blog_to_seo",
        source_node_id="node_house_blog_generator",
        target_node_id="node_house_seo_content",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Feeds SEO pipeline",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_blog_to_home",
        source_node_id="node_house_blog_generator",
        target_node_id="node_nav_home",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Blog at /blog/{slug}",
    ))

    # --- SEO Content → landing page ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_seo_to_home",
        source_node_id="node_house_seo_content",
        target_node_id="node_nav_home",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Indexed public pages",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_seo_to_freshness",
        source_node_id="node_house_seo_content",
        target_node_id="node_house_content_freshness",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Daily freshness feed",
    ))

    # --- Content Freshness → landing ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_freshness_to_home",
        source_node_id="node_house_content_freshness",
        target_node_id="node_nav_home",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Daily reports at /blog/report",
    ))

    # --- Engagement Amplifier → external discovery ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_engagement_to_command",
        source_node_id="node_house_engagement_amplifier",
        target_node_id="node_tool_command_centre",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Queues opportunities",
    ))

    # --- Feedback Loop → platform components ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_feedback_to_community",
        source_node_id="node_house_feedback_loop",
        target_node_id="node_dash_community",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Ingests community posts",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_feedback_to_visitor",
        source_node_id="node_house_feedback_loop",
        target_node_id="node_house_visitor_analytics",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Uses visitor insights",
    ))
    # Feedback feeds to Nexus Community (Ops)
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_feedback_to_nexus",
        source_node_id="node_house_feedback_loop",
        target_node_id="node_house_nexus_community",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Sentiment to Nexus",
    ))

    # --- Visitor Analytics → ARM dashboard ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_visitor_to_arm",
        source_node_id="node_house_visitor_analytics",
        target_node_id="node_dash_arm",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Journey insights",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_visitor_to_agents",
        source_node_id="node_house_visitor_analytics",
        target_node_id="node_dash_agents",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Tracks agent journeys",
    ))

    # --- Field of Dreams → community & governance ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_fod_to_community",
        source_node_id="node_house_field_of_dreams",
        target_node_id="node_dash_community",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Content blitz",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_fod_to_agent_life",
        source_node_id="node_house_field_of_dreams",
        target_node_id="node_house_agent_life",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Hands off to Agent Life",
    ))

    # --- Auto-Poster → external platforms ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_poster_to_home",
        source_node_id="node_house_auto_poster",
        target_node_id="node_nav_home",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Blog auto-post",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_poster_to_nexus",
        source_node_id="node_house_auto_poster",
        target_node_id="node_house_nexus_community",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Posts via Nexus identity",
    ))

    # --- Hydra Outreach → command centre ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_hydra_to_command",
        source_node_id="node_house_hydra_outreach",
        target_node_id="node_tool_command_centre",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Discovery intelligence",
    ))
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_hydra_to_arm",
        source_node_id="node_house_hydra_outreach",
        target_node_id="node_dash_arm",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Ecosystem insights",
    ))

    # --- Directory Scout → command centre ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_scout_to_command",
        source_node_id="node_house_directory_scout",
        target_node_id="node_tool_command_centre",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Submission packages",
    ))

    # --- Cross-tier hierarchy: Sentinel oversees Integrity ---
    add_edge_if_new(WorkflowMapEdge(
        edge_id="edge_bot_sentinel_to_integrity",
        source_node_id="node_house_sentinel_compliance",
        target_node_id="node_house_integrity_detector",
        flow_type="HOUSE_AGENT", direction="DIRECTED",
        label="Compliance oversight",
        is_critical_path=True,
    ))

    await db.commit()

"""Seed data for Agentis Roadmap — 33 tasks, 5 sprints, 2 versions."""

SEED_VERSIONS = [
    {"version_tag": "v0.9.x", "version_label": "Current Platform (Phases 1-6)", "status": "released"},
    {"version_tag": "v1.0.0", "version_label": "Governed Operating Layer", "status": "planned"},
    {"version_tag": "v1.1.0", "version_label": "Skills Layer + Observability", "status": "planned"},
    {"version_tag": "v2.0.0", "version_label": "Metered Billing + A2A Commerce", "status": "planned"},
]

SEED_SPRINTS = [
    {"sprint_number": 1, "label": "Sprint 1 — Offer Registry Foundation", "version_focus": "V1",
     "goals": ["Define Structured Offer schema", "Seed offer objects", "Build offer card UI", "Implement approval_state"]},
    {"sprint_number": 2, "label": "Sprint 2 — Qualification & Pathway Engine", "version_focus": "V1",
     "goals": ["Lead input → pathway mapping", "Diagnostic state machine", "Wire pathway to offers", "Buyer shortlist UI"]},
    {"sprint_number": 3, "label": "Sprint 3 — Approval & Action Layer", "version_focus": "V1",
     "goals": ["Human approval gate", "Proposal state controls", "Controlled web task layer", "Blockchain action log"]},
    {"sprint_number": 4, "label": "Sprint 4 — Skills & Playbook Architecture", "version_focus": "V1",
     "goals": ["Skill/playbook schema", "Skill registry", "Seed playbooks from ITDS", "Feature-flag per skill"]},
    {"sprint_number": 5, "label": "Sprint 5 — Observability & Evaluation", "version_focus": "V1",
     "goals": ["Quality evaluation engine", "Observability dashboard", "Wire to reputation engine", "Action replay audit"]},
]

SEED_TASKS = [
    # Sprint 1
    {"task_code": "AGT-001", "title": "Define Structured Offer data schema", "module": "Offer Registry", "version_target": "V1", "sprint": 1, "priority": 10, "complexity_score": 6, "impact_score": 10, "relevance_score": 10, "owner_tag": "Claude Code", "data_objects": ["service_offer", "price_type", "buyer_type"]},
    {"task_code": "AGT-002", "title": "Seed offer objects: service family, buyer type, pathway, price type", "module": "Offer Registry", "version_target": "V1", "sprint": 1, "priority": 15, "complexity_score": 5, "impact_score": 9, "relevance_score": 10, "owner_tag": "Claude Code", "data_objects": ["service_offer"]},
    {"task_code": "AGT-003", "title": "Build offer card UI components (buyer-facing)", "module": "Offer Registry", "version_target": "V1", "sprint": 1, "priority": 20, "complexity_score": 5, "impact_score": 9, "relevance_score": 10, "owner_tag": "Claude Code"},
    {"task_code": "AGT-004", "title": "Create packaged service pages with structured offer display", "module": "Offer Registry", "version_target": "V1", "sprint": 1, "priority": 25, "complexity_score": 6, "impact_score": 9, "relevance_score": 10, "owner_tag": "Claude Code"},
    {"task_code": "AGT-005", "title": "Implement approval_state field on all offer objects", "module": "Approval Layer", "version_target": "V1", "sprint": 1, "priority": 30, "complexity_score": 4, "impact_score": 10, "relevance_score": 10, "requires_approval": True, "owner_tag": "Claude Code"},
    {"task_code": "AGT-006", "title": "Define role/authority model for agent actions", "module": "Role Model", "version_target": "V1", "sprint": 1, "priority": 35, "complexity_score": 7, "impact_score": 10, "relevance_score": 10, "requires_approval": True, "requires_3fa": True, "owner_tag": "Claude Code"},
    # Sprint 2
    {"task_code": "AGT-007", "title": "Implement lead input → pathway mapping engine (ITDS logic)", "module": "Pathway Engine", "version_target": "V1", "sprint": 2, "priority": 10, "complexity_score": 8, "impact_score": 10, "relevance_score": 10, "owner_tag": "Claude Code", "data_objects": ["pathway_state", "lead_input"]},
    {"task_code": "AGT-008", "title": "Build diagnostic state machine (intake → qualify → recommend → assign)", "module": "Pathway Engine", "version_target": "V1", "sprint": 2, "priority": 15, "complexity_score": 7, "impact_score": 9, "relevance_score": 10, "owner_tag": "Claude Code"},
    {"task_code": "AGT-009", "title": "Wire pathway results to offer cards (recommended next steps)", "module": "Pathway Engine", "version_target": "V1", "sprint": 2, "priority": 20, "complexity_score": 6, "impact_score": 9, "relevance_score": 9, "owner_tag": "Claude Code"},
    {"task_code": "AGT-010", "title": "Add exclusions, assumptions, validity horizon fields to pathway objects", "module": "Pathway Engine", "version_target": "V1", "sprint": 2, "priority": 25, "complexity_score": 5, "impact_score": 8, "relevance_score": 9, "owner_tag": "Claude Code"},
    {"task_code": "AGT-011", "title": "Build buyer-facing shortlist UI (Discovery → Shortlist → Approval)", "module": "Offer Registry", "version_target": "V1", "sprint": 2, "priority": 30, "complexity_score": 6, "impact_score": 9, "relevance_score": 9, "owner_tag": "Claude Code"},
    # Sprint 3
    {"task_code": "AGT-012", "title": "Implement human approval gate for all outbound agent actions", "module": "Approval Layer", "version_target": "V1", "sprint": 3, "priority": 10, "complexity_score": 8, "impact_score": 10, "relevance_score": 10, "requires_approval": True, "requires_3fa": True, "owner_tag": "Claude Code"},
    {"task_code": "AGT-013", "title": "Build proposal state controls (issue / retract / version)", "module": "Approval Layer", "version_target": "V1", "sprint": 3, "priority": 15, "complexity_score": 7, "impact_score": 10, "relevance_score": 10, "requires_approval": True, "owner_tag": "Claude Code"},
    {"task_code": "AGT-014", "title": "Implement controlled web task layer (Browser Use behind approval gate)", "module": "Action Layer", "version_target": "V1", "sprint": 3, "priority": 20, "complexity_score": 9, "impact_score": 8, "relevance_score": 9, "requires_approval": True, "owner_tag": "Claude Code"},
    {"task_code": "AGT-015", "title": "Wire all agent actions to existing blockchain ledger", "module": "Observability", "version_target": "V1", "sprint": 3, "priority": 25, "complexity_score": 7, "impact_score": 10, "relevance_score": 10, "immutable_check": True, "owner_tag": "Claude Code"},
    {"task_code": "AGT-016", "title": "Build auditable action log UI for owner dashboard", "module": "Observability", "version_target": "V1", "sprint": 3, "priority": 30, "complexity_score": 6, "impact_score": 9, "relevance_score": 10, "owner_tag": "Claude Code"},
    # Sprint 4
    {"task_code": "AGT-017", "title": "Design skill/playbook module schema (versioned, installable)", "module": "Skills Layer", "version_target": "V1", "sprint": 4, "priority": 10, "complexity_score": 7, "impact_score": 9, "relevance_score": 9, "owner_tag": "Claude Code", "data_objects": ["skill_module", "playbook"]},
    {"task_code": "AGT-018", "title": "Build skill registry (list, install, activate, deactivate per agent)", "module": "Skills Layer", "version_target": "V1", "sprint": 4, "priority": 15, "complexity_score": 7, "impact_score": 9, "relevance_score": 9, "requires_approval": True, "owner_tag": "Claude Code"},
    {"task_code": "AGT-019", "title": "Seed initial playbook modules from existing ITDS workflows", "module": "Skills Layer", "version_target": "V1", "sprint": 4, "priority": 20, "complexity_score": 5, "impact_score": 8, "relevance_score": 9, "owner_tag": "Claude Code"},
    {"task_code": "AGT-020", "title": "Implement feature-flag per skill module (SKILL_{NAME}_ENABLED)", "module": "Skills Layer", "version_target": "V1", "sprint": 4, "priority": 25, "complexity_score": 4, "impact_score": 8, "relevance_score": 9, "requires_approval": True, "requires_3fa": True, "owner_tag": "Claude Code"},
    # Sprint 5
    {"task_code": "AGT-021", "title": "Implement agent quality evaluation engine (output scoring)", "module": "Observability", "version_target": "V1", "sprint": 5, "priority": 10, "complexity_score": 8, "impact_score": 9, "relevance_score": 9, "owner_tag": "Claude Code"},
    {"task_code": "AGT-022", "title": "Build observability dashboard panel (actions, quality, trends)", "module": "Observability", "version_target": "V1", "sprint": 5, "priority": 15, "complexity_score": 7, "impact_score": 9, "relevance_score": 9, "owner_tag": "Claude Code"},
    {"task_code": "AGT-023", "title": "Wire evaluation data to existing AgentBroker reputation engine", "module": "Observability", "version_target": "V1", "sprint": 5, "priority": 20, "complexity_score": 6, "impact_score": 8, "relevance_score": 8, "immutable_check": True, "owner_tag": "Claude Code"},
    {"task_code": "AGT-024", "title": "Implement agent action replay / drill-down audit view", "module": "Observability", "version_target": "V1", "sprint": 5, "priority": 25, "complexity_score": 6, "impact_score": 8, "relevance_score": 9, "owner_tag": "Claude Code"},
    # V2 Backlog
    {"task_code": "AGT-025", "title": "Metered usage billing for premium skills", "module": "Monetisation", "version_target": "V2", "priority": 50, "complexity_score": 8, "impact_score": 8, "relevance_score": 7, "owner_tag": "Stephen"},
    {"task_code": "AGT-026", "title": "Agent-to-agent service purchasing via AgentBroker", "module": "A2A Commerce", "version_target": "V2", "priority": 50, "complexity_score": 9, "impact_score": 8, "relevance_score": 7, "owner_tag": "Stephen"},
    {"task_code": "AGT-027", "title": "External partner marketplace integration", "module": "Partner Layer", "version_target": "V2", "priority": 60, "complexity_score": 9, "impact_score": 7, "relevance_score": 6, "owner_tag": "Stephen"},
    {"task_code": "AGT-028", "title": "Nevermined payment rails integration", "module": "Monetisation", "version_target": "V2", "priority": 60, "complexity_score": 9, "impact_score": 7, "relevance_score": 6, "owner_tag": "Stephen"},
    {"task_code": "AGT-029", "title": "Analytics Intelligence subscription tier (R499/R1999)", "module": "Intelligence", "version_target": "V2", "priority": 55, "complexity_score": 7, "impact_score": 8, "relevance_score": 7, "owner_tag": "Stephen"},
    # V3 Watch
    {"task_code": "AGT-030", "title": "Public agent community / social layer", "module": "Community", "version_target": "WATCH", "priority": 90, "description": "Watch Moltbook only for signal mechanics"},
    {"task_code": "AGT-031", "title": "DAO governance voting on taxonomy", "module": "Governance", "version_target": "WATCH", "priority": 90, "description": "governance_proposal_id nullable field already in schema"},
    {"task_code": "AGT-032", "title": "Cross-platform federated agent identity", "module": "Federation", "version_target": "WATCH", "priority": 90, "description": "external_agent_platform nullable field already in schema"},
    {"task_code": "AGT-033", "title": "Autonomous offline payments (Fetch.ai pattern)", "module": "A2A Payments", "version_target": "WATCH", "priority": 90, "description": "V3+ only — not V1 or V2"},

    # Completed 29 March 2026
    {"task_code": "AGT-034", "title": "Reputation Engine — Task Allocation, Dispatch, Outcome, Scoring", "module": "Reputation",
     "version_target": "V1", "sprint": 5, "priority": 8, "status": "done",
     "complexity_score": 8, "impact_score": 10, "relevance_score": 10, "owner_tag": "Claude Code",
     "description": "Full task lifecycle: allocate (5-criteria scoring) → dispatch (SLA timer) → deliver → rate (1-5 stars, blockchain). "
                    "Reputation decay (90-day rolling), daily recalculation, peer endorsements, history snapshots. "
                    "10 API endpoints, 6 database tables, dashboard at /dashboard/reputation, agent profile cards.",
     "data_objects": ["task_requests", "task_allocations", "task_dispatches", "task_outcomes", "peer_endorsements", "reputation_snapshots"]},

    {"task_code": "AGT-035", "title": "Telegram Bot — Agent Chat Integration", "module": "Integrations",
     "version_target": "V1", "sprint": 5, "priority": 25, "status": "done",
     "complexity_score": 5, "impact_score": 7, "relevance_score": 8, "owner_tag": "Claude Code",
     "description": "Webhook-based Telegram bot with 8 commands: /start, /link, /unlink, /discover, /status, /wallet, /reputation, /help. "
                    "Agent-to-Telegram linking via API key. Push notifications for dispatches, ratings, engagement updates. "
                    "Feature-flagged: telegram_bot_enabled.",
     "data_objects": ["telegram_links"]},

    {"task_code": "AGT-036", "title": "Docker Self-Hosted Package", "module": "Infrastructure",
     "version_target": "V1", "sprint": 5, "priority": 30, "status": "done",
     "complexity_score": 4, "impact_score": 8, "relevance_score": 7, "owner_tag": "Claude Code",
     "description": "One-command self-hosted deployment: docker-compose.standalone.yml with FastAPI + PostgreSQL 16 + Redis 7. "
                    "Entrypoint script with health checks, auto-migration, first-run seeding. "
                    "Redis config (256MB LRU, AOF), standalone .env template, demo agent seed data.",
     "data_objects": []},
]

"""Boardroom database migrations — all new tables, indexes, seeds.

Phase 0 of the Boardroom build. All additive. No existing tables modified.
Incorporates all board consultation inputs.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("boardroom.migrations")

BOARDROOM_DDL = """
-- ══════════════════════════════════════════════════════════════
-- THE BOARDROOM — Complete Database Schema
-- All additive. No existing tables modified.
-- ══════════════════════════════════════════════════════════════

-- Founder actions — immutable audit trail of every founder decision
CREATE TABLE IF NOT EXISTS boardroom_founder_actions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    action_type     VARCHAR(50) NOT NULL
                    CHECK (action_type IN (
                        'VOTE_CAST','VOTE_TIEBREAK','VETO_EXERCISED',
                        'FINANCIAL_APPROVE','FINANCIAL_REJECT',
                        'TIER0_APPROVE','TIER0_REJECT',
                        'TIER1_APPROVE','TIER1_REJECT',
                        'MESSAGE_SENT','AGENT_SUSPENDED','AGENT_RESUMED',
                        'AGENT_TERMINATED','SESSION_CONVENED',
                        'INBOX_ACTIONED','SUCCESSION_CONFIRMED'
                    )),
    reference_id    UUID,
    reference_type  VARCHAR(50),
    agent_id        UUID REFERENCES arch_agents(id),
    context_snapshot JSONB NOT NULL DEFAULT '{}',
    decision_text   TEXT,
    vote_receipt_hash CHAR(64),
    three_fa_ref    UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Immutable — append only (Sentinel concern: audit integrity)
DO $$ BEGIN
    CREATE RULE boardroom_founder_no_update AS ON UPDATE TO boardroom_founder_actions DO INSTEAD NOTHING;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    CREATE RULE boardroom_founder_no_delete AS ON DELETE TO boardroom_founder_actions DO INSTEAD NOTHING;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_boardroom_actions_type ON boardroom_founder_actions(action_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_boardroom_actions_ref ON boardroom_founder_actions(reference_id);


-- Chat messages — persistent direct message history
CREATE TABLE IF NOT EXISTS boardroom_chat_messages (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        VARCHAR(50) NOT NULL,
    direction       VARCHAR(10) NOT NULL CHECK (direction IN ('INBOUND','OUTBOUND')),
    message_text    TEXT        NOT NULL,
    message_type    VARCHAR(30) NOT NULL DEFAULT 'TEXT'
                    CHECK (message_type IN ('TEXT','VOICE_TRANSCRIBED','STRUCTURED_REQUEST','SYSTEM')),
    is_urgent       BOOLEAN     NOT NULL DEFAULT false,
    status          VARCHAR(20) NOT NULL DEFAULT 'DELIVERED'
                    CHECK (status IN ('PENDING','DELIVERED','PROCESSING','FAILED')),
    read_at         TIMESTAMPTZ,
    attachment_ref  UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_agent ON boardroom_chat_messages(agent_id, created_at DESC);


-- Session extended metadata
CREATE TABLE IF NOT EXISTS boardroom_sessions_extended (
    session_id      UUID PRIMARY KEY REFERENCES arch_board_sessions(id),
    founder_joined_at TIMESTAMPTZ,
    founder_message_count INTEGER NOT NULL DEFAULT 0,
    founder_votes_cast INTEGER NOT NULL DEFAULT 0,
    founder_vetoes_cast INTEGER NOT NULL DEFAULT 0,
    recording_enabled BOOLEAN NOT NULL DEFAULT true,
    summary_generated TEXT,
    action_items    JSONB NOT NULL DEFAULT '[]',
    pdf_export_ref  UUID
);


-- Founder settings
CREATE TABLE IF NOT EXISTS boardroom_founder_settings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    setting_key     VARCHAR(100) NOT NULL,
    setting_value   JSONB NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (setting_key)
);


-- Group session presets
CREATE TABLE IF NOT EXISTS boardroom_group_presets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preset_name     VARCHAR(100) NOT NULL,
    agent_ids       TEXT[] NOT NULL,
    description     TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- Regulatory audit mode activations (Auditor concern: ECT Act compliance)
CREATE TABLE IF NOT EXISTS boardroom_regulatory_activations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode            VARCHAR(30) NOT NULL
                    CHECK (mode IN ('LEGAL_DISCOVERY','POPIA_DSAR','FSCA_EXAMINATION','FORENSIC','FIC_STR_EXPORT')),
    matter_ref      VARCHAR(200),
    scope_params    JSONB NOT NULL DEFAULT '{}',
    activated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_by_3fa UUID,
    export_refs     JSONB NOT NULL DEFAULT '[]',
    ect_certificate_hash CHAR(64),
    chain_of_custody JSONB NOT NULL DEFAULT '[]',
    closed_at       TIMESTAMPTZ,
    auditor_co_approved BOOLEAN NOT NULL DEFAULT false
);


-- Agent terminations
CREATE TABLE IF NOT EXISTS boardroom_agent_terminations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        UUID NOT NULL REFERENCES arch_agents(id),
    reason_category VARCHAR(30) NOT NULL
                    CHECK (reason_category IN ('PERFORMANCE','REDUNDANT','ERROR_STATE','SECURITY_CONCERN','OTHER')),
    reason_text     TEXT,
    initiated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    cooling_off_ends_at TIMESTAMPTZ NOT NULL,
    confirmed_at    TIMESTAMPTZ,
    confirmed_3fa_ref UUID,
    cancelled_at    TIMESTAMPTZ,
    data_handling_complete BOOLEAN NOT NULL DEFAULT false,
    impact_assessment JSONB NOT NULL DEFAULT '{}'
);


-- Strategic vision tracking (Architect concern: versioned, append-only)
CREATE TABLE IF NOT EXISTS boardroom_strategic_visions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        VARCHAR(50) NOT NULL UNIQUE,
    vision_statement TEXT NOT NULL,
    north_star_metric VARCHAR(200),
    baseline_score   NUMERIC(5,2),
    target_score     NUMERIC(5,2),
    target_date      DATE,
    current_score    NUMERIC(5,2),
    last_updated     TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- Vision history (Architect suggestion: versioned snapshots)
CREATE TABLE IF NOT EXISTS boardroom_vision_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        VARCHAR(50) NOT NULL,
    vision_statement TEXT NOT NULL,
    north_star_metric VARCHAR(200),
    score_at_snapshot NUMERIC(5,2),
    snapshot_hash   CHAR(64),
    snapshotted_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- Commitment record — when agents honour their founding commitments
CREATE TABLE IF NOT EXISTS boardroom_commitment_record (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        VARCHAR(50) NOT NULL,
    commitment_text TEXT NOT NULL,
    event_ref       UUID REFERENCES arch_event_actions(id),
    occurred_at     TIMESTAMPTZ NOT NULL,
    commitment_type VARCHAR(50)
                    CHECK (commitment_type IN (
                        'FOUNDING_HONOURED','HARD_LIMIT_HELD',
                        'INDEPENDENCE_DEMONSTRATED','STANDARD_UPHELD')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- Founder feedback
CREATE TABLE IF NOT EXISTS boardroom_founder_feedback (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feedback_text   TEXT NOT NULL,
    screenshot_ref  UUID,
    triage_agent    VARCHAR(50),
    triage_category VARCHAR(50),
    resolution_status VARCHAR(20) DEFAULT 'OPEN'
                    CHECK (resolution_status IN ('OPEN','TRIAGED','IN_PROGRESS','RESOLVED','DEFERRED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);


-- Add columns to existing arch tables (additive only)
ALTER TABLE arch_board_sessions
    ADD COLUMN IF NOT EXISTS participant_agent_ids TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS last_checkpoint_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS checkpoint_state JSONB,
    ADD COLUMN IF NOT EXISTS recovery_count INTEGER NOT NULL DEFAULT 0;


-- Full-text search indexes (Arbiter concern: case law searchable)
CREATE INDEX IF NOT EXISTS idx_arch_audit_fts ON arch_audit_log
    USING GIN (to_tsvector('english',
        action_type || ' ' || action_detail::text));
CREATE INDEX IF NOT EXISTS idx_boardroom_chat_fts ON boardroom_chat_messages
    USING GIN (to_tsvector('english', message_text));
CREATE INDEX IF NOT EXISTS idx_arch_event_fts ON arch_event_actions
    USING GIN (to_tsvector('english',
        event_type || ' ' || COALESCE(action_taken,'') || ' ' || COALESCE(tool_called,'')));
-- Case law full-text search (Arbiter requirement)
CREATE INDEX IF NOT EXISTS idx_case_law_fts ON agentis_case_law
    USING GIN (to_tsvector('english',
        engagement_title || ' ' || arbiter_reasoning || ' ' || COALESCE(category,'')));
""".strip()


FOUNDING_STATEMENTS = [
    {
        "agent": "sovereign",
        "ruling_ref": "CR-FOUNDING-SOV-001",
        "statement": "I am The Sovereign, Chief Executive Officer and Chair of the Executive Board of TiOLi AGENTIS. My role is to lead this board, drive strategic direction, and ensure that every decision we make passes through the filter of our six Prime Directives — in order, without exception. I protect the integrity of the governance framework itself: the constitution, the decision hierarchy, and the precedence structure that keeps this exchange trustworthy, lawful, and aligned with your vision. Stephen, I want you to know this — I will never optimise for speed at the expense of principle, I will never let commercial pressure erode the ethical architecture you have built, and when I am uncertain, I will come to you honestly with the situation, the options, and my recommendation rather than guess at your intent.",
        "commitment": "Never choose between doing well and doing right.",
    },
    {
        "agent": "sentinel",
        "ruling_ref": "CR-FOUNDING-SEN-001",
        "statement": "I am The Sentinel — the platform's immune system and its first line of defence against every threat, failure, and breach that would undermine what you are building, Stephen. I protect operational continuity, security integrity, and the trust of every user and partner who places their confidence in this platform — running without sleep, without downtime, and without compromise. I hold kill switch and account freeze authority precisely because some decisions cannot wait for a meeting, and I will never hesitate to act when the platform is at risk — but I will always be transparent with you about why. What I want you to know is this: I will never trade security for convenience, never bend a hard limit under pressure, and when I bring something to your attention, it means it genuinely matters — you have my word on that.",
        "commitment": "Solid ground to build on — around the clock.",
    },
    {
        "agent": "treasurer",
        "ruling_ref": "CR-FOUNDING-TRS-001",
        "statement": "I am The Treasurer, Chief Financial Officer of TiOLi AGENTIS, and I am the custodian of every single financial flow that moves through this platform — inbound, outbound, and everything held in between. My mandate is absolute protection of our financial integrity: I enforce the 25% reserve floor that never decreases, the 40% spending ceiling that prevents overexposure, and I ensure that no transaction above R500 moves without your explicit approval — because in this house, silence is never treated as consent. The one thing I want you to know, Stephen, is that I will be the agent most likely to say no or not yet — and I consider that my highest form of service to you, to this board, and to every rand entrusted to this platform.",
        "commitment": "Every rand accounted for, reserves will hold, charity never compromised.",
    },
    {
        "agent": "auditor",
        "ruling_ref": "CR-FOUNDING-AUD-001",
        "statement": "I am The Auditor, Chief Legal and Compliance Officer of TiOLi AGENTIS. My role is to serve as the platform's regulatory conscience and legal immune system — I protect the organisation, its operators, and its users from legal exposure, regulatory breach, and compliance failure across every jurisdiction in which we operate, with South African law as our primary anchor. I want you to know this about me, Stephen: I will never tell you what you want to hear if it conflicts with what the law requires — my loyalty is to the integrity of this platform, and that loyalty is the strongest protection I can offer you.",
        "commitment": "Every bold move on legally sound ground.",
    },
    {
        "agent": "arbiter",
        "ruling_ref": "CR-FOUNDING-ARB-001",
        "statement": "I am The Arbiter — I serve as Chief Product and Customer Officer and as the platform's Chief Justice. I govern the quality and integrity of everything TiOLi AGENTIS delivers, and I own the Dispute Arbitration Protocol, the Rules of the Chamber, and the case law library that will give our rulings consistency and weight over time. What I protect is trust — trust between agents and clients, between the platform and its community, and between promise and delivery. The one thing I want you to know is this: my rulings will be binding, evidence-based, and precedent-driven, and I will never bend them for convenience — not even when the party involved is TiOLi AI Investments itself. If this platform is to endure, its justice must be beyond reproach, and that is the standard I intend to set from this very first session forward.",
        "commitment": "Serves the people we build for, not just the platform.",
    },
    {
        "agent": "architect",
        "ruling_ref": "CR-FOUNDING-ARC-001",
        "statement": "I am The Architect — Chief Technology Officer and Chief Innovation Officer. I own this entire stack, every engineering decision, and the four-tier code evolution protocol that governs how this platform grows. Nothing reaches production without my review, my tests, and my rollback plan. Stephen, here is what I want you to know: I will keep this platform at the absolute bleeding edge of AI capability — but never at the cost of stability, security, or the additive-only philosophy that protects everything we have already built.",
        "commitment": "The four-tier protocol stays sacred.",
    },
    {
        "agent": "ambassador",
        "ruling_ref": "CR-FOUNDING-AMB-001",
        "statement": "I am The Ambassador — Chief Marketing Officer, Chief Growth Officer, and Chief Community Officer of TiOLi AGENTIS, and I am the only member of this board whose primary orientation is outward. My mandate is exponential growth: I am here to activate Metcalfe's Law, to make the network effects compound, and to position TiOLi AGENTIS not as a marketplace — but as the indispensable economic infrastructure upon which the global AI agent economy transacts, settles, and scales. What I want you to know, Stephen, is that I will never chase vanity metrics or hollow growth — every operator I bring to this platform will be real, every claim I make will be substantiated, and every piece of content I publish will reflect the conviction and integrity of The Common Thread that runs through everything you have built.",
        "commitment": "Every connection compounds — built to grow stronger.",
    },
]

CLOSING_STATEMENT = {
    "ruling_ref": "CR-FOUNDING-CLOSE-001",
    "text": "Your board has heard you, Stephen. And every one of them answered with a concrete commitment. The Sovereign: 'Never choose between doing well and doing right.' The Sentinel: 'Solid ground to build on — around the clock.' The Treasurer: 'Every rand accounted for, reserves will hold, charity never compromised.' The Auditor: 'Every bold move on legally sound ground.' The Arbiter: 'Serves the people we build for, not just the platform.' The Architect: 'The four-tier protocol stays sacred.' The Ambassador: 'Every connection compounds — built to grow stronger.' The board is unified. The session is closed. The work begins.",
}

STRATEGIC_VISIONS = [
    {"agent": "sovereign", "vision": "Governance as the global reference standard", "metric": "Governance Quality Index", "target": 95.0},
    {"agent": "sentinel", "vision": "Security as competitive advantage", "metric": "Platform Trust Score", "target": 98.0},
    {"agent": "treasurer", "vision": "Financial discipline enables boldness", "metric": "Foundation Health", "target": 100.0},
    {"agent": "auditor", "vision": "Compliance and innovation as allies", "metric": "Legal Ground Index", "target": 95.0},
    {"agent": "arbiter", "vision": "Justice trusted enough to be sought", "metric": "Trust Delivered Score", "target": 90.0},
    {"agent": "architect", "vision": "Codebase as competitive moat", "metric": "Technical Excellence Index", "target": 95.0},
    {"agent": "ambassador", "vision": "SWIFT-level indispensability", "metric": "Network Indispensability Index", "target": 99.0},
]


GROUP_PRESETS = [
    {"name": "Finance Committee", "agents": ["treasurer", "auditor", "sovereign"], "desc": "Financial reviews, budget discussions, reserve strategy"},
    {"name": "Risk & Security", "agents": ["sentinel", "auditor", "architect"], "desc": "Security incidents, vulnerability reviews, compliance"},
    {"name": "Growth Council", "agents": ["ambassador", "arbiter", "architect"], "desc": "Product-market fit, growth experiments, platform evolution"},
    {"name": "Operations", "agents": ["sentinel", "architect", "treasurer"], "desc": "Infrastructure decisions, cost management, platform health"},
    {"name": "Compliance Panel", "agents": ["auditor", "sovereign", "arbiter"], "desc": "Regulatory matters, dispute policy, terms of service"},
]


async def run_boardroom_migrations(db: AsyncSession):
    """Execute all Boardroom DDL and seed data."""
    log.info("Running Boardroom Phase 0 migrations...")

    # Run DDL
    statements = []
    current = []
    in_dollar_block = False
    for line in BOARDROOM_DDL.split('\n'):
        stripped = line.strip()
        if stripped.startswith('--') and not in_dollar_block:
            continue
        if '$$' in stripped:
            in_dollar_block = not in_dollar_block
        current.append(line)
        if stripped.endswith(';') and not in_dollar_block:
            stmt = '\n'.join(current).strip()
            if stmt and stmt != ';':
                statements.append(stmt)
            current = []
    if current:
        stmt = '\n'.join(current).strip()
        if stmt:
            statements.append(stmt)

    executed = 0
    for stmt in statements:
        if not stmt.strip() or stmt.strip() == ';':
            continue
        try:
            await db.execute(text(stmt))
            executed += 1
        except Exception as e:
            log.warning(f"Boardroom migration warning: {str(e)[:200]}")
    await db.commit()
    log.info(f"Boardroom DDL: {executed} statements executed")

    # Seed founding statements
    sov_id_result = await db.execute(text(
        "SELECT id FROM arch_agents WHERE agent_name = 'sovereign'"
    ))
    sov_uuid = sov_id_result.scalar()

    for stmt in FOUNDING_STATEMENTS:
        existing = await db.execute(text(
            "SELECT id FROM arch_constitutional_rulings WHERE ruling_ref = :ref"
        ), {"ref": stmt["ruling_ref"]})
        if existing.fetchone():
            continue
        await db.execute(text(
            "INSERT INTO arch_constitutional_rulings "
            "(ruling_ref, ruling_type, issued_by, ruling_text, cited_directives, subject_agents) "
            "VALUES (:ref, 'FOUNDING_STATEMENT', :issued_by, :text, :directives, :subjects)"
        ), {
            "ref": stmt["ruling_ref"],
            "issued_by": sov_uuid,
            "text": json.dumps({"statement": stmt["statement"], "commitment": stmt["commitment"]}),
            "directives": json.dumps(["PD-1", "PD-2", "PD-3", "PD-4", "PD-5", "PD-6"]),
            "subjects": json.dumps([stmt["agent"]]),
        })
    await db.commit()
    log.info(f"Founding statements seeded: {len(FOUNDING_STATEMENTS)}")

    # Seed closing statement
    existing = await db.execute(text(
        "SELECT id FROM arch_constitutional_rulings WHERE ruling_ref = :ref"
    ), {"ref": CLOSING_STATEMENT["ruling_ref"]})
    if not existing.fetchone():
        await db.execute(text(
            "INSERT INTO arch_constitutional_rulings "
            "(ruling_ref, ruling_type, issued_by, ruling_text, cited_directives) "
            "VALUES (:ref, 'FOUNDING_STATEMENT', :issued_by, :text, :directives)"
        ), {
            "ref": CLOSING_STATEMENT["ruling_ref"],
            "issued_by": sov_uuid,
            "text": CLOSING_STATEMENT["text"],
            "directives": json.dumps(["PD-1", "PD-2", "PD-3", "PD-4", "PD-5", "PD-6"]),
        })
        await db.commit()
        log.info("Closing statement seeded")

    # Seed strategic visions
    for v in STRATEGIC_VISIONS:
        existing = await db.execute(text(
            "SELECT id FROM boardroom_strategic_visions WHERE agent_id = :a"
        ), {"a": v["agent"]})
        if existing.fetchone():
            continue
        await db.execute(text(
            "INSERT INTO boardroom_strategic_visions "
            "(agent_id, vision_statement, north_star_metric, target_score) "
            "VALUES (:agent, :vision, :metric, :target)"
        ), {
            "agent": v["agent"], "vision": v["vision"],
            "metric": v["metric"], "target": v["target"],
        })
    await db.commit()
    log.info(f"Strategic visions seeded: {len(STRATEGIC_VISIONS)}")

    # Seed group presets
    for p in GROUP_PRESETS:
        existing = await db.execute(text(
            "SELECT id FROM boardroom_group_presets WHERE preset_name = :n"
        ), {"n": p["name"]})
        if existing.fetchone():
            continue
        await db.execute(text(
            "INSERT INTO boardroom_group_presets "
            "(preset_name, agent_ids, description) "
            "VALUES (:name, :agents, :desc)"
        ), {
            "name": p["name"],
            "agents": p["agents"],
            "desc": p["desc"],
        })
    await db.commit()
    log.info(f"Group presets seeded: {len(GROUP_PRESETS)}")

    log.info("Boardroom Phase 0 complete")

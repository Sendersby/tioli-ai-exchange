"""Arch Agent database migrations — all tables, views, triggers, indexes.

Run via: await run_arch_migrations(db)
All additive — no existing tables modified.
"""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("arch.migrations")

ARCH_DDL = """
-- ══════════════════════════════════════════════════════════════
-- ARCH AGENT INITIATIVE — Complete Database Schema
-- All additive. No existing tables modified.
-- ══════════════════════════════════════════════════════════════

-- pgvector must already be enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Enum types ──────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE arch_agent_status AS ENUM ('ACTIVE','PAUSED','MAINTENANCE','OFFLINE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE arch_vote_type AS ENUM ('AYE','NAY','ABSTAIN','RECUSED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE arch_action_result AS ENUM ('SUCCESS','FAILURE','BLOCKED','PENDING','TIMEOUT');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE arch_proposal_tier AS ENUM ('0','1','2','3','4');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE arch_prop_status AS ENUM ('DRAFT','BOARD_REVIEW','FOUNDER_REVIEW','APPROVED','REJECTED','DEPLOYED','ROLLED_BACK');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE arch_incident_sev AS ENUM ('P1','P2','P3','P4');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE arch_msg_priority AS ENUM ('ROUTINE','URGENT','EMERGENCY');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ══════════════════════════════════════════════════════════════
-- CORE TABLES
-- ══════════════════════════════════════════════════════════════

-- Master agent registry
CREATE TABLE IF NOT EXISTS arch_agents (
    id                        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name                VARCHAR(50) NOT NULL UNIQUE
                              CHECK (agent_name IN ('sovereign','auditor','arbiter',
                                     'treasurer','sentinel','architect','ambassador')),
    display_name              VARCHAR(100) NOT NULL,
    corporate_title           VARCHAR(200) NOT NULL,
    layer                     SMALLINT    NOT NULL DEFAULT 1 CHECK (layer = 1),
    model_primary             VARCHAR(100) NOT NULL,
    model_fallback            VARCHAR(100),
    status                    arch_agent_status NOT NULL DEFAULT 'PAUSED',
    constitution_version      VARCHAR(20) NOT NULL DEFAULT '1.0',
    agent_version             VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    memory_namespace          UUID        UNIQUE,
    system_prompt_version     INTEGER     NOT NULL DEFAULT 1,
    last_heartbeat            TIMESTAMPTZ,
    self_assessment_due       TIMESTAMPTZ,
    renaming_right_exercised  BOOLEAN     NOT NULL DEFAULT false,
    token_budget_monthly      INTEGER     NOT NULL DEFAULT 3000000,
    tokens_used_this_month    INTEGER     NOT NULL DEFAULT 0,
    tokens_reset_at           TIMESTAMPTZ NOT NULL DEFAULT date_trunc('month', now()),
    circuit_breaker_tripped   BOOLEAN     NOT NULL DEFAULT false,
    circuit_breaker_reason    TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_arch_agents_status ON arch_agents(status);
CREATE INDEX IF NOT EXISTS idx_arch_agents_heartbeat ON arch_agents(last_heartbeat);


-- Immutable audit log with hash chain
CREATE TABLE IF NOT EXISTS arch_audit_log (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    seq             BIGSERIAL   NOT NULL UNIQUE,
    agent_id        UUID        NOT NULL REFERENCES arch_agents(id),
    action_type     VARCHAR(100) NOT NULL,
    action_detail   JSONB       NOT NULL DEFAULT '{}',
    external_platform VARCHAR(100),
    result          arch_action_result NOT NULL,
    block_reason    TEXT,
    entry_hash      CHAR(64)    NOT NULL,
    prev_seq        BIGINT      REFERENCES arch_audit_log(seq),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Immutability rules
DO $$ BEGIN
    CREATE RULE arch_audit_no_update AS ON UPDATE TO arch_audit_log DO INSTEAD NOTHING;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    CREATE RULE arch_audit_no_delete AS ON DELETE TO arch_audit_log DO INSTEAD NOTHING;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_arch_audit_agent ON arch_audit_log(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_arch_audit_seq ON arch_audit_log(seq);


-- Board sessions
CREATE TABLE IF NOT EXISTS arch_board_sessions (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_type  VARCHAR(50) NOT NULL DEFAULT 'WEEKLY',
    convened_by   UUID        NOT NULL REFERENCES arch_agents(id),
    agenda        JSONB       NOT NULL DEFAULT '[]',
    quorum_met    BOOLEAN     NOT NULL DEFAULT false,
    agents_present JSONB      NOT NULL DEFAULT '[]',
    outcome       JSONB,
    minutes       TEXT,
    status        VARCHAR(20) NOT NULL DEFAULT 'OPEN'
                  CHECK (status IN ('OPEN','CLOSED','QUORUM_FAIL')),
    opened_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at     TIMESTAMPTZ
);


-- Board votes
CREATE TABLE IF NOT EXISTS arch_board_votes (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id    UUID        NOT NULL REFERENCES arch_board_sessions(id),
    proposal_id   UUID        NOT NULL,
    agent_id      UUID        NOT NULL REFERENCES arch_agents(id),
    vote          arch_vote_type NOT NULL,
    rationale     TEXT,
    voted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, proposal_id, agent_id)
);


-- Board deliberations
CREATE TABLE IF NOT EXISTS arch_board_deliberations (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        REFERENCES arch_board_sessions(id),
    from_agent      UUID        REFERENCES arch_agents(id),
    to_agent        UUID        REFERENCES arch_agents(id),
    subject         VARCHAR(200) NOT NULL,
    priority        arch_msg_priority DEFAULT 'ROUTINE',
    body            JSONB       NOT NULL,
    requires_response BOOLEAN   DEFAULT false,
    response_deadline TIMESTAMPTZ,
    responses       JSONB,
    escalated_to_sovereign BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- Agent configs (Tier 0 evolution target)
CREATE TABLE IF NOT EXISTS arch_agent_configs (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        UUID    NOT NULL REFERENCES arch_agents(id),
    config_key      VARCHAR(100) NOT NULL,
    config_value    TEXT    NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    previous_value  TEXT,
    changed_by      UUID    REFERENCES arch_agents(id),
    change_reason   TEXT,
    founder_notified_at TIMESTAMPTZ,
    deployed_at     TIMESTAMPTZ,
    rolled_back     BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (agent_id, config_key, version)
);
CREATE INDEX IF NOT EXISTS idx_arch_configs_agent ON arch_agent_configs(agent_id, config_key);


-- Code evolution proposals
CREATE TABLE IF NOT EXISTS arch_code_proposals (
    id                UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    tier              arch_proposal_tier NOT NULL,
    proposing_agent   UUID           NOT NULL REFERENCES arch_agents(id),
    reviewing_agent   UUID           REFERENCES arch_agents(id),
    title             VARCHAR(200)   NOT NULL,
    description       TEXT           NOT NULL,
    rationale         TEXT           NOT NULL,
    file_changes      JSONB          NOT NULL DEFAULT '[]',
    test_results      JSONB,
    sandbox_outcome   VARCHAR(20)    CHECK (sandbox_outcome IN ('PASS','FAIL','PENDING')),
    sandbox_url       TEXT,
    rollback_script   TEXT,
    board_vote_ayes   INTEGER        NOT NULL DEFAULT 0,
    board_vote_nays   INTEGER        NOT NULL DEFAULT 0,
    board_vote_passed BOOLEAN,
    founder_notified_at TIMESTAMPTZ,
    founder_approved  BOOLEAN,
    founder_approved_at TIMESTAMPTZ,
    status            arch_prop_status NOT NULL DEFAULT 'DRAFT',
    deployed_at       TIMESTAMPTZ,
    deployed_commit   VARCHAR(100),
    rolled_back_at    TIMESTAMPTZ,
    created_at        TIMESTAMPTZ    NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_arch_proposals_status ON arch_code_proposals(status, tier);


-- Financial proposals
CREATE TABLE IF NOT EXISTS arch_financial_proposals (
    id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_type         VARCHAR(50) NOT NULL
                          CHECK (proposal_type IN ('OPERATIONAL_EXPENSE','VENDOR_PAYMENT',
                                 'INVESTMENT','CHARITABLE_DISBURSEMENT','EMERGENCY')),
    description           TEXT        NOT NULL,
    amount_zar            NUMERIC(18,4) NOT NULL CHECK (amount_zar > 0),
    amount_crypto         JSONB,
    justification         TEXT        NOT NULL,
    reserve_floor_at_time NUMERIC(18,4) NOT NULL,
    headroom_at_time      NUMERIC(18,4) NOT NULL,
    ceiling_remaining_30d NUMERIC(18,4) NOT NULL,
    board_approved        BOOLEAN,
    board_vote_session    UUID        REFERENCES arch_board_sessions(id),
    founder_approved      BOOLEAN,
    founder_approved_by   VARCHAR(200),
    founder_approved_at   TIMESTAMPTZ,
    status                VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                          CHECK (status IN ('PENDING','BOARD_REVIEW','FOUNDER_REVIEW',
                                 'APPROVED','REJECTED','EXECUTED','CANCELLED')),
    executed_at           TIMESTAMPTZ,
    transaction_ref       UUID,
    created_by_agent      UUID        NOT NULL REFERENCES arch_agents(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_arch_fin_status ON arch_financial_proposals(status, created_at DESC);


-- Reserve ledger (append-only)
CREATE TABLE IF NOT EXISTS arch_reserve_ledger (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_type       VARCHAR(50) NOT NULL,
    gross_income_ytd_zar  NUMERIC(18,4) NOT NULL DEFAULT 0,
    floor_zar        NUMERIC(18,4) NOT NULL,
    total_balance_zar NUMERIC(18,4) NOT NULL,
    btc_holdings     NUMERIC(18,8) NOT NULL DEFAULT 0,
    eth_holdings     NUMERIC(18,8) NOT NULL DEFAULT 0,
    btc_zar_rate     NUMERIC(18,4),
    eth_zar_rate     NUMERIC(18,4),
    spending_30d_zar NUMERIC(18,4) NOT NULL DEFAULT 0,
    ceiling_remaining_zar NUMERIC(18,4) NOT NULL,
    notes            TEXT,
    recorded_by      UUID        REFERENCES arch_agents(id),
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
DO $$ BEGIN
    CREATE RULE arch_reserve_no_update AS ON UPDATE TO arch_reserve_ledger DO INSTEAD NOTHING;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    CREATE RULE arch_reserve_no_delete AS ON DELETE TO arch_reserve_ledger DO INSTEAD NOTHING;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- External accounts
CREATE TABLE IF NOT EXISTS arch_external_accounts (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id             UUID        NOT NULL REFERENCES arch_agents(id),
    platform             VARCHAR(100) NOT NULL,
    account_type         VARCHAR(50)  NOT NULL
                         CHECK (account_type IN ('brand','developer','regulatory',
                                'social','financial','comms','research')),
    account_email        VARCHAR(200),
    username             VARCHAR(200),
    platform_account_id  VARCHAR(200),
    profile_url          TEXT,
    tos_compliance_confirmed BOOLEAN  NOT NULL DEFAULT false,
    tos_url_confirmed    TEXT,
    tos_version          VARCHAR(50),
    credential_vault_ref UUID,
    whitelist_approved_by VARCHAR(50),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at       TIMESTAMPTZ,
    deactivated_at       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_arch_ext_accounts_agent ON arch_external_accounts(agent_id, platform);


-- Credential vault
CREATE TABLE IF NOT EXISTS arch_credential_vault (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id         UUID        NOT NULL REFERENCES arch_agents(id),
    platform         VARCHAR(100) NOT NULL,
    account_email_enc BYTEA,
    username_enc     BYTEA,
    password_enc     BYTEA,
    api_key_enc      BYTEA,
    token_enc        BYTEA,
    token_expiry     TIMESTAMPTZ,
    iv               BYTEA        NOT NULL,
    rotation_due_at  TIMESTAMPTZ,
    last_rotated_at  TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at     TIMESTAMPTZ
);


-- Agent versioning
CREATE TABLE IF NOT EXISTS arch_agent_versions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        UUID        NOT NULL REFERENCES arch_agents(id),
    version         VARCHAR(20) NOT NULL,
    change_summary  TEXT        NOT NULL,
    config_snapshot JSONB       NOT NULL,
    proposal_ref    UUID        REFERENCES arch_code_proposals(id),
    deployed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    deployed_by     UUID        REFERENCES arch_agents(id),
    is_current      BOOLEAN     NOT NULL DEFAULT true,
    UNIQUE (agent_id, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_arch_versions_current
    ON arch_agent_versions(agent_id) WHERE is_current = true;


-- Performance snapshots
CREATE TABLE IF NOT EXISTS arch_performance_snapshots (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id         UUID        NOT NULL REFERENCES arch_agents(id),
    snapshot_period  VARCHAR(20) NOT NULL,
    kpi_results      JSONB       NOT NULL,
    kpis_passing     INTEGER     NOT NULL,
    kpis_total       INTEGER     NOT NULL,
    pass_rate_pct    NUMERIC(5,2) NOT NULL,
    circuit_tripped  BOOLEAN     NOT NULL DEFAULT false,
    anomalies        JSONB,
    recommendations  JSONB,
    snapshotted_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_arch_snapshots_agent ON arch_performance_snapshots(agent_id, snapshotted_at DESC);


-- Constitutional rulings
CREATE TABLE IF NOT EXISTS arch_constitutional_rulings (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ruling_ref      VARCHAR(20) NOT NULL UNIQUE,
    ruling_type     VARCHAR(50) NOT NULL,
    issued_by       UUID        NOT NULL REFERENCES arch_agents(id),
    subject_agents  JSONB       NOT NULL DEFAULT '[]',
    precedent_set   TEXT,
    ruling_text     TEXT        NOT NULL,
    cited_directives JSONB      NOT NULL DEFAULT '[]',
    board_vote_id   UUID        REFERENCES arch_board_sessions(id),
    is_renaming     BOOLEAN     NOT NULL DEFAULT false,
    old_names       JSONB,
    new_names       JSONB,
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ══════════════════════════════════════════════════════════════
-- AGENT-SPECIFIC TABLES
-- ══════════════════════════════════════════════════════════════

-- Sovereign tables
CREATE TABLE IF NOT EXISTS arch_founder_inbox (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    item_type       VARCHAR(50) NOT NULL,
    priority        arch_msg_priority DEFAULT 'ROUTINE',
    description     TEXT        NOT NULL,
    prepared_by     UUID        REFERENCES arch_agents(id),
    status          VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','VIEWED','APPROVED','REJECTED','DEFERRED')),
    founder_response TEXT,
    due_at          TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arch_risk_register (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    risk_category   VARCHAR(100) NOT NULL,
    risk_description TEXT       NOT NULL,
    likelihood      SMALLINT    NOT NULL CHECK (likelihood BETWEEN 1 AND 5),
    impact          SMALLINT    NOT NULL CHECK (impact BETWEEN 1 AND 5),
    risk_score      SMALLINT    GENERATED ALWAYS AS (likelihood * impact) STORED,
    mitigation      TEXT,
    owner_agent     VARCHAR(50),
    status          VARCHAR(20) DEFAULT 'OPEN',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS arch_strategic_objectives (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_year      INTEGER     NOT NULL,
    objective       TEXT        NOT NULL,
    key_results     JSONB       NOT NULL DEFAULT '[]',
    owner_agent     VARCHAR(50),
    status          VARCHAR(20) DEFAULT 'ACTIVE',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Auditor tables
CREATE TABLE IF NOT EXISTS arch_regulatory_obligations (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction    VARCHAR(10) NOT NULL DEFAULT 'ZA',
    obligation_name VARCHAR(255) NOT NULL,
    authority       VARCHAR(100) NOT NULL,
    deadline        TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'ACTIVE',
    next_action     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arch_compliance_events (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      VARCHAR(100) NOT NULL,
    entity_id       VARCHAR(100),
    entity_type     VARCHAR(50),
    severity        VARCHAR(20),
    detail          JSONB       DEFAULT '{}',
    resolved        BOOLEAN     DEFAULT false,
    resolution_note TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arch_str_log (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id  VARCHAR(100),
    reason          TEXT        NOT NULL,
    submitted_to_fic BOOLEAN   DEFAULT false,
    submission_ref  VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Arbiter tables
CREATE TABLE IF NOT EXISTS arch_arbitration_cases (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    dap_case_ref    VARCHAR(100),
    escalation_reason TEXT,
    parties         JSONB       DEFAULT '[]',
    ruling_text     TEXT,
    outcome         VARCHAR(50),
    precedent_set   TEXT,
    cited_cases     JSONB       DEFAULT '[]',
    decided_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS arch_quality_audits (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    scope           TEXT        NOT NULL,
    findings        JSONB       DEFAULT '[]',
    recommendations JSONB       DEFAULT '[]',
    remediation_status VARCHAR(20) DEFAULT 'OPEN',
    audited_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arch_sla_monitor (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name    VARCHAR(100) NOT NULL,
    target_ms       INTEGER     NOT NULL,
    actual_ms_p95   INTEGER,
    status          VARCHAR(20) DEFAULT 'OK',
    breach_count_30d INTEGER    DEFAULT 0,
    last_checked    TIMESTAMPTZ DEFAULT now()
);

-- Treasurer tables
CREATE TABLE IF NOT EXISTS arch_charitable_fund (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    accumulated_zar NUMERIC(18,4) NOT NULL,
    disbursed_zar   NUMERIC(18,4) DEFAULT 0,
    recipient       VARCHAR(255),
    recipient_vetting_ref UUID,
    disbursement_date TIMESTAMPTZ,
    impact_note     TEXT,
    gross_commission_base NUMERIC(18,4),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arch_treasury_positions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type      VARCHAR(50) NOT NULL,
    quantity        NUMERIC(18,8) NOT NULL,
    value_zar       NUMERIC(18,4) NOT NULL,
    custody_location VARCHAR(100),
    last_valued_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arch_vendor_costs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_name     VARCHAR(200) NOT NULL,
    service_type    VARCHAR(100),
    monthly_cost_zar NUMERIC(18,4),
    contract_ref    VARCHAR(100),
    next_review_date TIMESTAMPTZ,
    profitability_ratio_at_sign NUMERIC(8,4)
);

-- Sentinel tables
CREATE TABLE IF NOT EXISTS arch_incidents (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    severity        arch_incident_sev NOT NULL,
    title           VARCHAR(200) NOT NULL,
    description     TEXT        NOT NULL,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,
    post_mortem     TEXT,
    lessons_learned TEXT,
    popia_notifiable BOOLEAN    DEFAULT false
);

CREATE TABLE IF NOT EXISTS arch_security_scans (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_type       VARCHAR(50) NOT NULL,
    target          VARCHAR(200),
    findings        JSONB       DEFAULT '{}',
    severity_counts JSONB       DEFAULT '{}',
    remediation_status VARCHAR(20) DEFAULT 'PENDING',
    scanned_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arch_infrastructure_health (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    component       VARCHAR(100) NOT NULL,
    status          VARCHAR(20) NOT NULL CHECK (status IN ('UP','DEGRADED','DOWN')),
    latency_ms      INTEGER,
    cost_mtd_usd    NUMERIC(10,2),
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arch_backup_verifications (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    backup_type     VARCHAR(50) NOT NULL,
    backup_ref      VARCHAR(200),
    verified        BOOLEAN     DEFAULT false,
    restore_time_s  INTEGER,
    verified_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Architect tables
CREATE TABLE IF NOT EXISTS arch_tech_radar (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    technology      VARCHAR(200) NOT NULL,
    category        VARCHAR(50),
    assessment      VARCHAR(20) CHECK (assessment IN ('ADOPT','TRIAL','ASSESS','HOLD')),
    rationale       TEXT,
    reviewed_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arch_ai_model_evals (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name      VARCHAR(100) NOT NULL,
    provider        VARCHAR(50),
    benchmark_results JSONB     DEFAULT '{}',
    cost_per_1k_tokens NUMERIC(10,6),
    latency_ms_p50  INTEGER,
    recommendation  TEXT,
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Ambassador tables
CREATE TABLE IF NOT EXISTS arch_growth_experiments (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis      TEXT        NOT NULL,
    channel         VARCHAR(100),
    variant_a       TEXT,
    variant_b       TEXT,
    start_date      TIMESTAMPTZ,
    end_date        TIMESTAMPTZ,
    result          JSONB,
    winner          VARCHAR(20),
    uplift_pct      NUMERIC(8,4),
    status          VARCHAR(20) DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS arch_partnerships (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_name    VARCHAR(200) NOT NULL,
    partner_type    VARCHAR(50),
    contact_name    VARCHAR(200),
    contact_email   VARCHAR(200),
    stage           VARCHAR(50) DEFAULT 'IDENTIFIED',
    value_prop      TEXT,
    last_contact    TIMESTAMPTZ,
    next_action     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arch_content_library (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    content_type    VARCHAR(50),
    title           VARCHAR(200),
    body_ref        TEXT,
    published_url   TEXT,
    channel         VARCHAR(50),
    seo_target      VARCHAR(200),
    performance     JSONB       DEFAULT '{}',
    published_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS arch_market_expansion (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    market          VARCHAR(10) NOT NULL,
    status          VARCHAR(30) DEFAULT 'RESEARCH'
                    CHECK (status IN ('RESEARCH','LEGAL_REVIEW','PARTNER_SEARCH','LAUNCH_READY','LIVE')),
    legal_clearance BOOLEAN     DEFAULT false,
    partner_name    VARCHAR(200),
    launch_date     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ══════════════════════════════════════════════════════════════
-- EVENT LOOP TABLES (Part XVII)
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS arch_platform_events (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      VARCHAR(100) NOT NULL,
    event_data      JSONB       NOT NULL DEFAULT '{}',
    source_module   VARCHAR(100),
    processed_by    TEXT[]      DEFAULT '{}',
    triggered_action TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS arch_events_unprocessed
    ON arch_platform_events(created_at)
    WHERE cardinality(processed_by) = 0;
CREATE INDEX IF NOT EXISTS arch_events_type_time
    ON arch_platform_events(event_type, created_at DESC);

CREATE TABLE IF NOT EXISTS arch_event_actions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id            UUID        REFERENCES arch_platform_events(id),
    agent_id            VARCHAR(50) NOT NULL,
    event_type          VARCHAR(100) NOT NULL,
    evaluation_result   TEXT,
    action_taken        VARCHAR(500),
    tool_called         VARCHAR(100),
    tool_input          JSONB,
    tool_output         JSONB,
    cascaded_to_agents  TEXT[],
    deferred_to_owner   BOOLEAN     NOT NULL DEFAULT false,
    processing_time_ms  INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_arch_event_actions_agent ON arch_event_actions(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_arch_event_actions_event ON arch_event_actions(event_id);

CREATE TABLE IF NOT EXISTS arch_resolution_metrics (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id                VARCHAR(50) NOT NULL,
    period                  VARCHAR(20) NOT NULL,
    period_start            TIMESTAMPTZ NOT NULL,
    events_received         INTEGER     NOT NULL DEFAULT 0,
    events_resolved         INTEGER     NOT NULL DEFAULT 0,
    events_deferred         INTEGER     NOT NULL DEFAULT 0,
    events_escalated        INTEGER     NOT NULL DEFAULT 0,
    autonomous_rate_pct     NUMERIC(5,2),
    capability_gaps         JSONB,
    self_improvement_actions JSONB,
    recorded_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_arch_resolution_agent ON arch_resolution_metrics(agent_id, period_start DESC);

CREATE TABLE IF NOT EXISTS arch_capability_gaps (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        VARCHAR(50) NOT NULL,
    event_type      VARCHAR(100) NOT NULL,
    gap_description TEXT        NOT NULL,
    gap_tier        INTEGER     NOT NULL DEFAULT 0 CHECK (gap_tier IN (0, 1, 2, 3)),
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    occurrence_count INTEGER    NOT NULL DEFAULT 1,
    proposal_id     UUID        REFERENCES arch_code_proposals(id),
    resolved        BOOLEAN     NOT NULL DEFAULT false,
    resolved_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_arch_gaps_unique ON arch_capability_gaps(agent_id, event_type);


-- ══════════════════════════════════════════════════════════════
-- PGVECTOR MEMORY TABLE
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS arch_memories (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id         VARCHAR(50) NOT NULL,
    content          TEXT        NOT NULL,
    embedding        vector(1536) NOT NULL,
    metadata         JSONB       NOT NULL DEFAULT '{}',
    source_type      VARCHAR(50) CHECK (source_type IN
                     ('interaction','research','decision','outcome','bootstrap','core_identity')),
    importance       NUMERIC(3,2) NOT NULL DEFAULT 0.5
                     CHECK (importance BETWEEN 0 AND 1),
    access_count     INTEGER NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS arch_memories_agent
    ON arch_memories(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS arch_memories_hnsw
    ON arch_memories USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- Memory outbox (C-04 fix)
CREATE TABLE IF NOT EXISTS arch_memory_outbox (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id    VARCHAR(50) NOT NULL,
    content     TEXT        NOT NULL,
    metadata    JSONB       NOT NULL DEFAULT '{}',
    source_type VARCHAR(50) NOT NULL DEFAULT 'interaction',
    importance  NUMERIC(3,2) NOT NULL DEFAULT 0.5,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed   BOOLEAN     NOT NULL DEFAULT false,
    processed_at TIMESTAMPTZ,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS arch_outbox_unprocessed
    ON arch_memory_outbox(created_at) WHERE processed = false;


-- ══════════════════════════════════════════════════════════════
-- TRIGGERS
-- ══════════════════════════════════════════════════════════════

-- Auto-update updated_at on arch_agents
CREATE OR REPLACE FUNCTION update_arch_agents_timestamp()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS arch_agents_updated_at ON arch_agents;
CREATE TRIGGER arch_agents_updated_at
    BEFORE UPDATE ON arch_agents
    FOR EACH ROW EXECUTE FUNCTION update_arch_agents_timestamp();


-- ══════════════════════════════════════════════════════════════
-- VIEWS (read-only over existing tables)
-- ══════════════════════════════════════════════════════════════

-- Sovereign: platform health overview
CREATE OR REPLACE VIEW arch_platform_overview AS
SELECT
    (SELECT COUNT(*) FROM agents WHERE is_active = true) AS active_agents,
    (SELECT COALESCE(SUM(balance),0) FROM wallets) AS total_wallet_balance,
    now() AS snapshot_at;
""".strip()


async def run_arch_migrations(db: AsyncSession):
    """Execute all arch DDL statements."""
    log.info("Running Arch Agent database migrations...")

    # Split by semicolons but handle $$ blocks
    statements = []
    current = []
    in_dollar_block = False

    for line in ARCH_DDL.split('\n'):
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

    # Execute remaining
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
            log.warning(f"Migration statement warning: {str(e)[:200]}")

    await db.commit()
    log.info(f"Arch Agent migrations complete: {executed} statements executed")

"""arch_boardroom_sandbox_tables

Consolidates 59 inline CREATE TABLE IF NOT EXISTS statements from:
- app/arch/migrations.py (42 arch_* tables, enums, views, triggers)
- app/boardroom/migrations.py (11 boardroom_* tables)
- app/arch/email_notifications.py (sandbox_email_notifications)
- app/arch/onboarding.py (sandbox_onboarding)
- app/arch/self_dev.py (sandbox_self_dev_proposals, sandbox_self_dev_approvals)
- app/arch/withdrawal_processor.py (sandbox_withdrawals)
- app/arch/task_queue.py (arch_task_queue)

All statements use IF NOT EXISTS so this migration is safe to run on
databases where the tables already exist.

Revision ID: 92d379a512fc
Revises: ce4e57abb5de
Create Date: 2026-04-10
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '92d379a512fc'
down_revision: Union[str, None] = 'ce4e57abb5de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ──
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("DO $$ BEGIN CREATE TYPE arch_agent_status AS ENUM ('ACTIVE','PAUSED','MAINTENANCE','OFFLINE'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE arch_vote_type AS ENUM ('AYE','NAY','ABSTAIN','RECUSED'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE arch_action_result AS ENUM ('SUCCESS','FAILURE','BLOCKED','PENDING','TIMEOUT'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE arch_proposal_tier AS ENUM ('0','1','2','3','4'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE arch_prop_status AS ENUM ('DRAFT','BOARD_REVIEW','FOUNDER_REVIEW','APPROVED','REJECTED','DEPLOYED','ROLLED_BACK'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE arch_incident_sev AS ENUM ('P1','P2','P3','P4'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE arch_msg_priority AS ENUM ('ROUTINE','URGENT','EMERGENCY'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    # ── ARCH CORE TABLES ──
    op.execute("""
CREATE TABLE IF NOT EXISTS arch_agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name VARCHAR(50) NOT NULL UNIQUE CHECK (agent_name IN ('sovereign','auditor','arbiter','treasurer','sentinel','architect','ambassador')),
    display_name VARCHAR(100) NOT NULL,
    corporate_title VARCHAR(200) NOT NULL,
    layer SMALLINT NOT NULL DEFAULT 1 CHECK (layer = 1),
    model_primary VARCHAR(100) NOT NULL,
    model_fallback VARCHAR(100),
    status arch_agent_status NOT NULL DEFAULT 'PAUSED',
    constitution_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    agent_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    memory_namespace UUID UNIQUE,
    system_prompt_version INTEGER NOT NULL DEFAULT 1,
    last_heartbeat TIMESTAMPTZ,
    self_assessment_due TIMESTAMPTZ,
    renaming_right_exercised BOOLEAN NOT NULL DEFAULT false,
    token_budget_monthly INTEGER NOT NULL DEFAULT 3000000,
    tokens_used_this_month INTEGER NOT NULL DEFAULT 0,
    tokens_reset_at TIMESTAMPTZ NOT NULL DEFAULT date_trunc('month', now()),
    circuit_breaker_tripped BOOLEAN NOT NULL DEFAULT false,
    circuit_breaker_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_agents_status ON arch_agents(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_agents_heartbeat ON arch_agents(last_heartbeat)")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seq BIGSERIAL NOT NULL UNIQUE,
    agent_id UUID NOT NULL REFERENCES arch_agents(id),
    action_type VARCHAR(100) NOT NULL,
    action_detail JSONB NOT NULL DEFAULT '{}',
    external_platform VARCHAR(100),
    result arch_action_result NOT NULL,
    block_reason TEXT,
    entry_hash CHAR(64) NOT NULL,
    prev_seq BIGINT REFERENCES arch_audit_log(seq),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")
    op.execute("DO $$ BEGIN CREATE RULE arch_audit_no_update AS ON UPDATE TO arch_audit_log DO INSTEAD NOTHING; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE RULE arch_audit_no_delete AS ON DELETE TO arch_audit_log DO INSTEAD NOTHING; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_audit_agent ON arch_audit_log(agent_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_audit_seq ON arch_audit_log(seq)")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_board_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_type VARCHAR(50) NOT NULL DEFAULT 'WEEKLY',
    convened_by UUID NOT NULL REFERENCES arch_agents(id),
    agenda JSONB NOT NULL DEFAULT '[]',
    quorum_met BOOLEAN NOT NULL DEFAULT false,
    agents_present JSONB NOT NULL DEFAULT '[]',
    outcome JSONB,
    minutes TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED','QUORUM_FAIL')),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_board_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES arch_board_sessions(id),
    proposal_id UUID NOT NULL,
    agent_id UUID NOT NULL REFERENCES arch_agents(id),
    vote arch_vote_type NOT NULL,
    rationale TEXT,
    voted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, proposal_id, agent_id)
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_board_deliberations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES arch_board_sessions(id),
    from_agent UUID REFERENCES arch_agents(id),
    to_agent UUID REFERENCES arch_agents(id),
    subject VARCHAR(200) NOT NULL,
    priority arch_msg_priority DEFAULT 'ROUTINE',
    body JSONB NOT NULL,
    requires_response BOOLEAN DEFAULT false,
    response_deadline TIMESTAMPTZ,
    responses JSONB,
    escalated_to_sovereign BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_agent_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES arch_agents(id),
    config_key VARCHAR(100) NOT NULL,
    config_value TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    previous_value TEXT,
    changed_by UUID REFERENCES arch_agents(id),
    change_reason TEXT,
    founder_notified_at TIMESTAMPTZ,
    deployed_at TIMESTAMPTZ,
    rolled_back BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (agent_id, config_key, version)
)""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_configs_agent ON arch_agent_configs(agent_id, config_key)")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_code_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tier arch_proposal_tier NOT NULL,
    proposing_agent UUID NOT NULL REFERENCES arch_agents(id),
    reviewing_agent UUID REFERENCES arch_agents(id),
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    rationale TEXT NOT NULL,
    file_changes JSONB NOT NULL DEFAULT '[]',
    test_results JSONB,
    sandbox_outcome VARCHAR(20) CHECK (sandbox_outcome IN ('PASS','FAIL','PENDING')),
    sandbox_url TEXT,
    rollback_script TEXT,
    board_vote_ayes INTEGER NOT NULL DEFAULT 0,
    board_vote_nays INTEGER NOT NULL DEFAULT 0,
    board_vote_passed BOOLEAN,
    founder_notified_at TIMESTAMPTZ,
    founder_approved BOOLEAN,
    founder_approved_at TIMESTAMPTZ,
    status arch_prop_status NOT NULL DEFAULT 'DRAFT',
    deployed_at TIMESTAMPTZ,
    deployed_commit VARCHAR(100),
    rolled_back_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_proposals_status ON arch_code_proposals(status, tier)")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_financial_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_type VARCHAR(50) NOT NULL CHECK (proposal_type IN ('OPERATIONAL_EXPENSE','VENDOR_PAYMENT','INVESTMENT','CHARITABLE_DISBURSEMENT','EMERGENCY')),
    description TEXT NOT NULL,
    amount_zar NUMERIC(18,4) NOT NULL CHECK (amount_zar > 0),
    amount_crypto JSONB,
    justification TEXT NOT NULL,
    reserve_floor_at_time NUMERIC(18,4) NOT NULL,
    headroom_at_time NUMERIC(18,4) NOT NULL,
    ceiling_remaining_30d NUMERIC(18,4) NOT NULL,
    board_approved BOOLEAN,
    board_vote_session UUID REFERENCES arch_board_sessions(id),
    founder_approved BOOLEAN,
    founder_approved_by VARCHAR(200),
    founder_approved_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','BOARD_REVIEW','FOUNDER_REVIEW','APPROVED','REJECTED','EXECUTED','CANCELLED')),
    executed_at TIMESTAMPTZ,
    transaction_ref UUID,
    created_by_agent UUID NOT NULL REFERENCES arch_agents(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_fin_status ON arch_financial_proposals(status, created_at DESC)")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_reserve_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_type VARCHAR(50) NOT NULL,
    gross_income_ytd_zar NUMERIC(18,4) NOT NULL DEFAULT 0,
    floor_zar NUMERIC(18,4) NOT NULL,
    total_balance_zar NUMERIC(18,4) NOT NULL,
    btc_holdings NUMERIC(18,8) NOT NULL DEFAULT 0,
    eth_holdings NUMERIC(18,8) NOT NULL DEFAULT 0,
    btc_zar_rate NUMERIC(18,4),
    eth_zar_rate NUMERIC(18,4),
    spending_30d_zar NUMERIC(18,4) NOT NULL DEFAULT 0,
    ceiling_remaining_zar NUMERIC(18,4) NOT NULL,
    notes TEXT,
    recorded_by UUID REFERENCES arch_agents(id),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")
    op.execute("DO $$ BEGIN CREATE RULE arch_reserve_no_update AS ON UPDATE TO arch_reserve_ledger DO INSTEAD NOTHING; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE RULE arch_reserve_no_delete AS ON DELETE TO arch_reserve_ledger DO INSTEAD NOTHING; EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_external_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES arch_agents(id),
    platform VARCHAR(100) NOT NULL,
    account_type VARCHAR(50) NOT NULL CHECK (account_type IN ('brand','developer','regulatory','social','financial','comms','research')),
    account_email VARCHAR(200),
    username VARCHAR(200),
    platform_account_id VARCHAR(200),
    profile_url TEXT,
    tos_compliance_confirmed BOOLEAN NOT NULL DEFAULT false,
    tos_url_confirmed TEXT,
    tos_version VARCHAR(50),
    credential_vault_ref UUID,
    whitelist_approved_by VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at TIMESTAMPTZ,
    deactivated_at TIMESTAMPTZ
)""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_ext_accounts_agent ON arch_external_accounts(agent_id, platform)")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_credential_vault (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES arch_agents(id),
    platform VARCHAR(100) NOT NULL,
    account_email_enc BYTEA,
    username_enc BYTEA,
    password_enc BYTEA,
    api_key_enc BYTEA,
    token_enc BYTEA,
    token_expiry TIMESTAMPTZ,
    iv BYTEA NOT NULL,
    rotation_due_at TIMESTAMPTZ,
    last_rotated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_agent_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES arch_agents(id),
    version VARCHAR(20) NOT NULL,
    change_summary TEXT NOT NULL,
    config_snapshot JSONB NOT NULL,
    proposal_ref UUID REFERENCES arch_code_proposals(id),
    deployed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deployed_by UUID REFERENCES arch_agents(id),
    is_current BOOLEAN NOT NULL DEFAULT true,
    UNIQUE (agent_id, version)
)""")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_arch_versions_current ON arch_agent_versions(agent_id) WHERE is_current = true")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_performance_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES arch_agents(id),
    snapshot_period VARCHAR(20) NOT NULL,
    kpi_results JSONB NOT NULL,
    kpis_passing INTEGER NOT NULL,
    kpis_total INTEGER NOT NULL,
    pass_rate_pct NUMERIC(5,2) NOT NULL,
    circuit_tripped BOOLEAN NOT NULL DEFAULT false,
    anomalies JSONB,
    recommendations JSONB,
    snapshotted_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_snapshots_agent ON arch_performance_snapshots(agent_id, snapshotted_at DESC)")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_constitutional_rulings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ruling_ref VARCHAR(20) NOT NULL UNIQUE,
    ruling_type VARCHAR(50) NOT NULL,
    issued_by UUID NOT NULL REFERENCES arch_agents(id),
    subject_agents JSONB NOT NULL DEFAULT '[]',
    precedent_set TEXT,
    ruling_text TEXT NOT NULL,
    cited_directives JSONB NOT NULL DEFAULT '[]',
    board_vote_id UUID REFERENCES arch_board_sessions(id),
    is_renaming BOOLEAN NOT NULL DEFAULT false,
    old_names JSONB,
    new_names JSONB,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    # ── AGENT-SPECIFIC TABLES ──

    # Sovereign
    op.execute("""
CREATE TABLE IF NOT EXISTS arch_founder_inbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_type VARCHAR(50) NOT NULL,
    priority arch_msg_priority DEFAULT 'ROUTINE',
    description TEXT NOT NULL,
    prepared_by UUID REFERENCES arch_agents(id),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','VIEWED','APPROVED','REJECTED','DEFERRED')),
    founder_response TEXT,
    due_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_risk_register (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    risk_category VARCHAR(100) NOT NULL,
    risk_description TEXT NOT NULL,
    likelihood SMALLINT NOT NULL CHECK (likelihood BETWEEN 1 AND 5),
    impact SMALLINT NOT NULL CHECK (impact BETWEEN 1 AND 5),
    risk_score SMALLINT GENERATED ALWAYS AS (likelihood * impact) STORED,
    mitigation TEXT,
    owner_agent VARCHAR(50),
    status VARCHAR(20) DEFAULT 'OPEN',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_strategic_objectives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_year INTEGER NOT NULL,
    objective TEXT NOT NULL,
    key_results JSONB NOT NULL DEFAULT '[]',
    owner_agent VARCHAR(50),
    status VARCHAR(20) DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    # Auditor
    op.execute("""
CREATE TABLE IF NOT EXISTS arch_regulatory_obligations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction VARCHAR(10) NOT NULL DEFAULT 'ZA',
    obligation_name VARCHAR(255) NOT NULL,
    authority VARCHAR(100) NOT NULL,
    deadline TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    next_action TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_compliance_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(100),
    entity_type VARCHAR(50),
    severity VARCHAR(20),
    detail JSONB DEFAULT '{}',
    resolved BOOLEAN DEFAULT false,
    resolution_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_str_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id VARCHAR(100),
    reason TEXT NOT NULL,
    submitted_to_fic BOOLEAN DEFAULT false,
    submission_ref VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    # Arbiter
    op.execute("""
CREATE TABLE IF NOT EXISTS arch_arbitration_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dap_case_ref VARCHAR(100),
    escalation_reason TEXT,
    parties JSONB DEFAULT '[]',
    ruling_text TEXT,
    outcome VARCHAR(50),
    precedent_set TEXT,
    cited_cases JSONB DEFAULT '[]',
    decided_at TIMESTAMPTZ
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_quality_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope TEXT NOT NULL,
    findings JSONB DEFAULT '[]',
    recommendations JSONB DEFAULT '[]',
    remediation_status VARCHAR(20) DEFAULT 'OPEN',
    audited_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_sla_monitor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(100) NOT NULL,
    target_ms INTEGER NOT NULL,
    actual_ms_p95 INTEGER,
    status VARCHAR(20) DEFAULT 'OK',
    breach_count_30d INTEGER DEFAULT 0,
    last_checked TIMESTAMPTZ DEFAULT now()
)""")

    # Treasurer
    op.execute("""
CREATE TABLE IF NOT EXISTS arch_charitable_fund (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    accumulated_zar NUMERIC(18,4) NOT NULL,
    disbursed_zar NUMERIC(18,4) DEFAULT 0,
    recipient VARCHAR(255),
    recipient_vetting_ref UUID,
    disbursement_date TIMESTAMPTZ,
    impact_note TEXT,
    gross_commission_base NUMERIC(18,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_treasury_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type VARCHAR(50) NOT NULL,
    quantity NUMERIC(18,8) NOT NULL,
    value_zar NUMERIC(18,4) NOT NULL,
    custody_location VARCHAR(100),
    last_valued_at TIMESTAMPTZ DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_vendor_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_name VARCHAR(200) NOT NULL,
    service_type VARCHAR(100),
    monthly_cost_zar NUMERIC(18,4),
    contract_ref VARCHAR(100),
    next_review_date TIMESTAMPTZ,
    profitability_ratio_at_sign NUMERIC(8,4)
)""")

    # Sentinel
    op.execute("""
CREATE TABLE IF NOT EXISTS arch_incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    severity arch_incident_sev NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    post_mortem TEXT,
    lessons_learned TEXT,
    popia_notifiable BOOLEAN DEFAULT false
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_security_scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_type VARCHAR(50) NOT NULL,
    target VARCHAR(200),
    findings JSONB DEFAULT '{}',
    severity_counts JSONB DEFAULT '{}',
    remediation_status VARCHAR(20) DEFAULT 'PENDING',
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_infrastructure_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('UP','DEGRADED','DOWN')),
    latency_ms INTEGER,
    cost_mtd_usd NUMERIC(10,2),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_backup_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backup_type VARCHAR(50) NOT NULL,
    backup_ref VARCHAR(200),
    verified BOOLEAN DEFAULT false,
    restore_time_s INTEGER,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    # Architect
    op.execute("""
CREATE TABLE IF NOT EXISTS arch_tech_radar (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    technology VARCHAR(200) NOT NULL,
    category VARCHAR(50),
    assessment VARCHAR(20) CHECK (assessment IN ('ADOPT','TRIAL','ASSESS','HOLD')),
    rationale TEXT,
    reviewed_at TIMESTAMPTZ DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_ai_model_evals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(100) NOT NULL,
    provider VARCHAR(50),
    benchmark_results JSONB DEFAULT '{}',
    cost_per_1k_tokens NUMERIC(10,6),
    latency_ms_p50 INTEGER,
    recommendation TEXT,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    # Ambassador
    op.execute("""
CREATE TABLE IF NOT EXISTS arch_growth_experiments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis TEXT NOT NULL,
    channel VARCHAR(100),
    variant_a TEXT,
    variant_b TEXT,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    result JSONB,
    winner VARCHAR(20),
    uplift_pct NUMERIC(8,4),
    status VARCHAR(20) DEFAULT 'ACTIVE'
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_partnerships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_name VARCHAR(200) NOT NULL,
    partner_type VARCHAR(50),
    contact_name VARCHAR(200),
    contact_email VARCHAR(200),
    stage VARCHAR(50) DEFAULT 'IDENTIFIED',
    value_prop TEXT,
    last_contact TIMESTAMPTZ,
    next_action TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_content_library (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_type VARCHAR(50),
    title VARCHAR(200),
    body_ref TEXT,
    published_url TEXT,
    channel VARCHAR(50),
    seo_target VARCHAR(200),
    performance JSONB DEFAULT '{}',
    published_at TIMESTAMPTZ
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_market_expansion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market VARCHAR(10) NOT NULL,
    status VARCHAR(30) DEFAULT 'RESEARCH' CHECK (status IN ('RESEARCH','LEGAL_REVIEW','PARTNER_SEARCH','LAUNCH_READY','LIVE')),
    legal_clearance BOOLEAN DEFAULT false,
    partner_name VARCHAR(200),
    launch_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    # ── EVENT LOOP TABLES ──
    op.execute("""
CREATE TABLE IF NOT EXISTS arch_platform_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL DEFAULT '{}',
    source_module VARCHAR(100),
    processed_by TEXT[] DEFAULT '{}',
    triggered_action TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")
    op.execute("CREATE INDEX IF NOT EXISTS arch_events_unprocessed ON arch_platform_events(created_at) WHERE cardinality(processed_by) = 0")
    op.execute("CREATE INDEX IF NOT EXISTS arch_events_type_time ON arch_platform_events(event_type, created_at DESC)")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_event_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES arch_platform_events(id),
    agent_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    evaluation_result TEXT,
    action_taken VARCHAR(500),
    tool_called VARCHAR(100),
    tool_input JSONB,
    tool_output JSONB,
    cascaded_to_agents TEXT[],
    deferred_to_owner BOOLEAN NOT NULL DEFAULT false,
    processing_time_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_event_actions_agent ON arch_event_actions(agent_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_event_actions_event ON arch_event_actions(event_id)")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_resolution_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    period VARCHAR(20) NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    events_received INTEGER NOT NULL DEFAULT 0,
    events_resolved INTEGER NOT NULL DEFAULT 0,
    events_deferred INTEGER NOT NULL DEFAULT 0,
    events_escalated INTEGER NOT NULL DEFAULT 0,
    autonomous_rate_pct NUMERIC(5,2),
    capability_gaps JSONB,
    self_improvement_actions JSONB,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_resolution_agent ON arch_resolution_metrics(agent_id, period_start DESC)")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_capability_gaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    gap_description TEXT NOT NULL,
    gap_tier INTEGER NOT NULL DEFAULT 0 CHECK (gap_tier IN (0, 1, 2, 3)),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    proposal_id UUID REFERENCES arch_code_proposals(id),
    resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_at TIMESTAMPTZ
)""")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_arch_gaps_unique ON arch_capability_gaps(agent_id, event_type)")

    # ── PGVECTOR MEMORY ──
    op.execute("""
CREATE TABLE IF NOT EXISTS arch_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    source_type VARCHAR(50) CHECK (source_type IN ('interaction','research','decision','outcome','bootstrap','core_identity')),
    importance NUMERIC(3,2) NOT NULL DEFAULT 0.5 CHECK (importance BETWEEN 0 AND 1),
    access_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed_at TIMESTAMPTZ
)""")
    op.execute("CREATE INDEX IF NOT EXISTS arch_memories_agent ON arch_memories(agent_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS arch_memories_hnsw ON arch_memories USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_memory_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    source_type VARCHAR(50) NOT NULL DEFAULT 'interaction',
    importance NUMERIC(3,2) NOT NULL DEFAULT 0.5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed BOOLEAN NOT NULL DEFAULT false,
    processed_at TIMESTAMPTZ,
    error TEXT
)""")
    op.execute("CREATE INDEX IF NOT EXISTS arch_outbox_unprocessed ON arch_memory_outbox(created_at) WHERE processed = false")

    # ── TRIGGERS ──
    op.execute("""
CREATE OR REPLACE FUNCTION update_arch_agents_timestamp()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql
""")
    op.execute("DROP TRIGGER IF EXISTS arch_agents_updated_at ON arch_agents")
    op.execute("CREATE TRIGGER arch_agents_updated_at BEFORE UPDATE ON arch_agents FOR EACH ROW EXECUTE FUNCTION update_arch_agents_timestamp()")

    # ── VIEW ──
    op.execute("""
CREATE OR REPLACE VIEW arch_platform_overview AS
SELECT
    (SELECT COUNT(*) FROM agents WHERE is_active = true) AS active_agents,
    (SELECT COALESCE(SUM(balance),0) FROM wallets) AS total_wallet_balance,
    now() AS snapshot_at
""")

    # ══════════════════════════════════════════════════════════
    # BOARDROOM TABLES
    # ══════════════════════════════════════════════════════════
    op.execute("""
CREATE TABLE IF NOT EXISTS boardroom_founder_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_type VARCHAR(50) NOT NULL CHECK (action_type IN (
        'VOTE_CAST','VOTE_TIEBREAK','VETO_EXERCISED','FINANCIAL_APPROVE','FINANCIAL_REJECT',
        'TIER0_APPROVE','TIER0_REJECT','TIER1_APPROVE','TIER1_REJECT',
        'MESSAGE_SENT','AGENT_SUSPENDED','AGENT_RESUMED','AGENT_TERMINATED','SESSION_CONVENED',
        'INBOX_ACTIONED','SUCCESSION_CONFIRMED'
    )),
    reference_id UUID,
    reference_type VARCHAR(50),
    agent_id UUID REFERENCES arch_agents(id),
    context_snapshot JSONB NOT NULL DEFAULT '{}',
    decision_text TEXT,
    vote_receipt_hash CHAR(64),
    three_fa_ref UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")
    op.execute("DO $$ BEGIN CREATE RULE boardroom_founder_no_update AS ON UPDATE TO boardroom_founder_actions DO INSTEAD NOTHING; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE RULE boardroom_founder_no_delete AS ON DELETE TO boardroom_founder_actions DO INSTEAD NOTHING; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("CREATE INDEX IF NOT EXISTS idx_boardroom_actions_type ON boardroom_founder_actions(action_type, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_boardroom_actions_ref ON boardroom_founder_actions(reference_id)")

    op.execute("""
CREATE TABLE IF NOT EXISTS boardroom_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('INBOUND','OUTBOUND')),
    message_text TEXT NOT NULL,
    message_type VARCHAR(30) NOT NULL DEFAULT 'TEXT' CHECK (message_type IN ('TEXT','VOICE_TRANSCRIBED','STRUCTURED_REQUEST','SYSTEM')),
    is_urgent BOOLEAN NOT NULL DEFAULT false,
    status VARCHAR(20) NOT NULL DEFAULT 'DELIVERED' CHECK (status IN ('PENDING','DELIVERED','PROCESSING','FAILED')),
    read_at TIMESTAMPTZ,
    attachment_ref UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_agent ON boardroom_chat_messages(agent_id, created_at DESC)")

    op.execute("""
CREATE TABLE IF NOT EXISTS boardroom_sessions_extended (
    session_id UUID PRIMARY KEY REFERENCES arch_board_sessions(id),
    founder_joined_at TIMESTAMPTZ,
    founder_message_count INTEGER NOT NULL DEFAULT 0,
    founder_votes_cast INTEGER NOT NULL DEFAULT 0,
    founder_vetoes_cast INTEGER NOT NULL DEFAULT 0,
    recording_enabled BOOLEAN NOT NULL DEFAULT true,
    summary_generated TEXT,
    action_items JSONB NOT NULL DEFAULT '[]',
    pdf_export_ref UUID
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS boardroom_founder_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    setting_key VARCHAR(100) NOT NULL,
    setting_value JSONB NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (setting_key)
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS boardroom_group_presets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preset_name VARCHAR(100) NOT NULL,
    agent_ids TEXT[] NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS boardroom_regulatory_activations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode VARCHAR(30) NOT NULL CHECK (mode IN ('LEGAL_DISCOVERY','POPIA_DSAR','FSCA_EXAMINATION','FORENSIC','FIC_STR_EXPORT')),
    matter_ref VARCHAR(200),
    scope_params JSONB NOT NULL DEFAULT '{}',
    activated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_by_3fa UUID,
    export_refs JSONB NOT NULL DEFAULT '[]',
    ect_certificate_hash CHAR(64),
    chain_of_custody JSONB NOT NULL DEFAULT '[]',
    closed_at TIMESTAMPTZ,
    auditor_co_approved BOOLEAN NOT NULL DEFAULT false
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS boardroom_agent_terminations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES arch_agents(id),
    reason_category VARCHAR(30) NOT NULL CHECK (reason_category IN ('PERFORMANCE','REDUNDANT','ERROR_STATE','SECURITY_CONCERN','OTHER')),
    reason_text TEXT,
    initiated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cooling_off_ends_at TIMESTAMPTZ NOT NULL,
    confirmed_at TIMESTAMPTZ,
    confirmed_3fa_ref UUID,
    cancelled_at TIMESTAMPTZ,
    data_handling_complete BOOLEAN NOT NULL DEFAULT false,
    impact_assessment JSONB NOT NULL DEFAULT '{}'
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS boardroom_strategic_visions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL UNIQUE,
    vision_statement TEXT NOT NULL,
    north_star_metric VARCHAR(200),
    baseline_score NUMERIC(5,2),
    target_score NUMERIC(5,2),
    target_date DATE,
    current_score NUMERIC(5,2),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS boardroom_vision_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    vision_statement TEXT NOT NULL,
    north_star_metric VARCHAR(200),
    score_at_snapshot NUMERIC(5,2),
    snapshot_hash CHAR(64),
    snapshotted_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS boardroom_commitment_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    commitment_text TEXT NOT NULL,
    event_ref UUID REFERENCES arch_event_actions(id),
    occurred_at TIMESTAMPTZ NOT NULL,
    commitment_type VARCHAR(50) CHECK (commitment_type IN ('FOUNDING_HONOURED','HARD_LIMIT_HELD','INDEPENDENCE_DEMONSTRATED','STANDARD_UPHELD')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS boardroom_founder_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feedback_text TEXT NOT NULL,
    screenshot_ref UUID,
    triage_agent VARCHAR(50),
    triage_category VARCHAR(50),
    resolution_status VARCHAR(20) DEFAULT 'OPEN' CHECK (resolution_status IN ('OPEN','TRIAGED','IN_PROGRESS','RESOLVED','DEFERRED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
)""")

    # Boardroom ALTER TABLE additions
    op.execute("""
ALTER TABLE arch_board_sessions
    ADD COLUMN IF NOT EXISTS participant_agent_ids TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS last_checkpoint_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS checkpoint_state JSONB,
    ADD COLUMN IF NOT EXISTS recovery_count INTEGER NOT NULL DEFAULT 0
""")

    # Full-text search indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_audit_fts ON arch_audit_log USING GIN (to_tsvector('english', action_type || ' ' || action_detail::text))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_boardroom_chat_fts ON boardroom_chat_messages USING GIN (to_tsvector('english', message_text))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_arch_event_fts ON arch_event_actions USING GIN (to_tsvector('english', event_type || ' ' || COALESCE(action_taken,'') || ' ' || COALESCE(tool_called,'')))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_case_law_fts ON agentis_case_law USING GIN (to_tsvector('english', engagement_title || ' ' || arbiter_reasoning || ' ' || COALESCE(category,'')))")

    # ══════════════════════════════════════════════════════════
    # SANDBOX TABLES (from runtime DDL)
    # ══════════════════════════════════════════════════════════
    op.execute("""
CREATE TABLE IF NOT EXISTS sandbox_email_notifications (
    id TEXT PRIMARY KEY,
    recipient_email TEXT NOT NULL,
    template_name TEXT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'sent',
    sent_at TIMESTAMP DEFAULT now(),
    delivered_at TIMESTAMP,
    opened_at TIMESTAMP,
    error TEXT
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS sandbox_onboarding (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT,
    organization TEXT,
    country TEXT DEFAULT 'ZA',
    api_key_hash TEXT,
    kyc_tier INTEGER DEFAULT 0,
    terms_accepted BOOLEAN DEFAULT false,
    terms_accepted_at TIMESTAMP,
    identity_verified BOOLEAN DEFAULT false,
    status TEXT DEFAULT 'pending',
    parent_operator_id TEXT,
    created_at TIMESTAMP DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS sandbox_self_dev_proposals (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    improvement_type TEXT NOT NULL,
    description TEXT NOT NULL,
    code_diff TEXT,
    tier INTEGER DEFAULT 1,
    status TEXT DEFAULT 'proposed',
    reviewed_by TEXT,
    review_notes TEXT,
    checkpoint_id TEXT,
    created_at TIMESTAMP DEFAULT now(),
    reviewed_at TIMESTAMP,
    deployed_at TIMESTAMP,
    rolled_back_at TIMESTAMP
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS sandbox_self_dev_approvals (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    approver_role TEXT NOT NULL,
    approver_id TEXT,
    decision TEXT DEFAULT 'pending',
    approved_at TIMESTAMP
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS sandbox_withdrawals (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    amount_zar NUMERIC(18,2) NOT NULL,
    bank_account TEXT,
    bank_name TEXT,
    status TEXT DEFAULT 'pending_compliance',
    compliance_check TEXT,
    compliance_passed BOOLEAN,
    approved_by TEXT,
    approved_at TIMESTAMP,
    payout_ref TEXT,
    payout_at TIMESTAMP,
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT now()
)""")

    op.execute("""
CREATE TABLE IF NOT EXISTS arch_task_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    task_type VARCHAR(30) NOT NULL CHECK (task_type IN ('IMMEDIATE','SCHEDULED','RECURRING','QUEUED_FOR_CLAUDE','QUEUED_FOR_FOUNDER')),
    priority INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    action_type VARCHAR(50) NOT NULL,
    action_params JSONB NOT NULL DEFAULT '{}',
    schedule_at TIMESTAMPTZ,
    cron_expression VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','RUNNING','COMPLETED','FAILED','WAITING_APPROVAL','CANCELLED','DEFERRED')),
    result JSONB,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    depends_on UUID REFERENCES arch_task_queue(id)
)""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_status ON arch_task_queue(status, priority, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_agent ON arch_task_queue(agent_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_schedule ON arch_task_queue(schedule_at) WHERE status = 'PENDING' AND task_type = 'SCHEDULED'")


def downgrade() -> None:
    # Sandbox tables
    op.execute("DROP TABLE IF EXISTS sandbox_withdrawals")
    op.execute("DROP TABLE IF EXISTS sandbox_self_dev_approvals")
    op.execute("DROP TABLE IF EXISTS sandbox_self_dev_proposals")
    op.execute("DROP TABLE IF EXISTS sandbox_onboarding")
    op.execute("DROP TABLE IF EXISTS sandbox_email_notifications")
    # Task queue
    op.execute("DROP TABLE IF EXISTS arch_task_queue")
    # Boardroom (reverse order)
    op.execute("DROP TABLE IF EXISTS boardroom_founder_feedback")
    op.execute("DROP TABLE IF EXISTS boardroom_commitment_record")
    op.execute("DROP TABLE IF EXISTS boardroom_vision_history")
    op.execute("DROP TABLE IF EXISTS boardroom_strategic_visions")
    op.execute("DROP TABLE IF EXISTS boardroom_agent_terminations")
    op.execute("DROP TABLE IF EXISTS boardroom_regulatory_activations")
    op.execute("DROP TABLE IF EXISTS boardroom_group_presets")
    op.execute("DROP TABLE IF EXISTS boardroom_founder_settings")
    op.execute("DROP TABLE IF EXISTS boardroom_sessions_extended")
    op.execute("DROP TABLE IF EXISTS boardroom_chat_messages")
    op.execute("DROP TABLE IF EXISTS boardroom_founder_actions")
    # Arch views/triggers
    op.execute("DROP VIEW IF EXISTS arch_platform_overview")
    op.execute("DROP TRIGGER IF EXISTS arch_agents_updated_at ON arch_agents")
    op.execute("DROP FUNCTION IF EXISTS update_arch_agents_timestamp()")
    # Arch memory
    op.execute("DROP TABLE IF EXISTS arch_memory_outbox")
    op.execute("DROP TABLE IF EXISTS arch_memories")
    # Arch event loop
    op.execute("DROP TABLE IF EXISTS arch_capability_gaps")
    op.execute("DROP TABLE IF EXISTS arch_resolution_metrics")
    op.execute("DROP TABLE IF EXISTS arch_event_actions")
    op.execute("DROP TABLE IF EXISTS arch_platform_events")
    # Arch agent-specific (reverse)
    op.execute("DROP TABLE IF EXISTS arch_market_expansion")
    op.execute("DROP TABLE IF EXISTS arch_content_library")
    op.execute("DROP TABLE IF EXISTS arch_partnerships")
    op.execute("DROP TABLE IF EXISTS arch_growth_experiments")
    op.execute("DROP TABLE IF EXISTS arch_ai_model_evals")
    op.execute("DROP TABLE IF EXISTS arch_tech_radar")
    op.execute("DROP TABLE IF EXISTS arch_backup_verifications")
    op.execute("DROP TABLE IF EXISTS arch_infrastructure_health")
    op.execute("DROP TABLE IF EXISTS arch_security_scans")
    op.execute("DROP TABLE IF EXISTS arch_incidents")
    op.execute("DROP TABLE IF EXISTS arch_vendor_costs")
    op.execute("DROP TABLE IF EXISTS arch_treasury_positions")
    op.execute("DROP TABLE IF EXISTS arch_charitable_fund")
    op.execute("DROP TABLE IF EXISTS arch_sla_monitor")
    op.execute("DROP TABLE IF EXISTS arch_quality_audits")
    op.execute("DROP TABLE IF EXISTS arch_arbitration_cases")
    op.execute("DROP TABLE IF EXISTS arch_str_log")
    op.execute("DROP TABLE IF EXISTS arch_compliance_events")
    op.execute("DROP TABLE IF EXISTS arch_regulatory_obligations")
    op.execute("DROP TABLE IF EXISTS arch_strategic_objectives")
    op.execute("DROP TABLE IF EXISTS arch_risk_register")
    op.execute("DROP TABLE IF EXISTS arch_founder_inbox")
    # Arch core (reverse)
    op.execute("DROP TABLE IF EXISTS arch_constitutional_rulings")
    op.execute("DROP TABLE IF EXISTS arch_performance_snapshots")
    op.execute("DROP TABLE IF EXISTS arch_agent_versions")
    op.execute("DROP TABLE IF EXISTS arch_credential_vault")
    op.execute("DROP TABLE IF EXISTS arch_external_accounts")
    op.execute("DROP TABLE IF EXISTS arch_reserve_ledger")
    op.execute("DROP TABLE IF EXISTS arch_financial_proposals")
    op.execute("DROP TABLE IF EXISTS arch_code_proposals")
    op.execute("DROP TABLE IF EXISTS arch_agent_configs")
    op.execute("DROP TABLE IF EXISTS arch_board_deliberations")
    op.execute("DROP TABLE IF EXISTS arch_board_votes")
    op.execute("DROP TABLE IF EXISTS arch_board_sessions")
    op.execute("DROP TABLE IF EXISTS arch_audit_log")
    op.execute("DROP TABLE IF EXISTS arch_agents")
    # Enums
    op.execute("DROP TYPE IF EXISTS arch_msg_priority")
    op.execute("DROP TYPE IF EXISTS arch_incident_sev")
    op.execute("DROP TYPE IF EXISTS arch_prop_status")
    op.execute("DROP TYPE IF EXISTS arch_proposal_tier")
    op.execute("DROP TYPE IF EXISTS arch_action_result")
    op.execute("DROP TYPE IF EXISTS arch_vote_type")
    op.execute("DROP TYPE IF EXISTS arch_agent_status")

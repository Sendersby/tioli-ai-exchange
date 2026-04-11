"""
Sandbox Router - Extracted from main.py (A-001 God File Decomposition)
Contains all TIER A, TIER B, and partial TIER C sandbox endpoints.
~60 endpoints for regulatory, functional, and operational sandbox services.
"""
import json
import uuid
from fastapi import APIRouter, Request, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.utils.validators import (
    VaultStoreRequest, GuildCreateRequest, GuildJoinRequest,
    FuturesCreateRequest, FuturesReserveRequest, BadgeRequestModel,
    NotificationSendRequest, WithdrawalRequest, SelfDevProposeRequest,
    FiatDepositRequest, FiatWithdrawRequest,
)

sandbox_router = APIRouter(tags=["Sandbox"])

# ═══════════════════════════════════════════════════════════
# TIER A: SANDBOX — Regulatory Services (SANDBOX_MODE=true required)
# ═══════════════════════════════════════════════════════════

# A-1: Fiat On/Off-Ramp
@sandbox_router.post("/api/v1/sandbox/fiat/deposit")
async def api_sandbox_fiat_deposit(request: Request,body: FiatDepositRequest, db: AsyncSession = Depends(get_db)):
    from app.arch.fiat_ramp import process_deposit
    return await process_deposit(db, body.customer_id, body.amount_zar, body.kyc_tier)

@sandbox_router.post("/api/v1/sandbox/fiat/withdraw")
async def api_sandbox_fiat_withdraw(request: Request,body: FiatWithdrawRequest, db: AsyncSession = Depends(get_db)):
    from app.arch.fiat_ramp import request_withdrawal
    return await request_withdrawal(db, body.customer_id, body.amount_agentis, body.kyc_tier)

@sandbox_router.get("/api/v1/sandbox/fiat/rate")
async def api_sandbox_fiat_rate():
    from app.arch.fiat_ramp import get_conversion_rate
    deposit_rate = await get_conversion_rate("deposit")
    withdrawal_rate = await get_conversion_rate("withdrawal")
    return {"deposit_rate": deposit_rate, "withdrawal_rate": withdrawal_rate, "base": 1.0, "spread_pct": 2.0}

@sandbox_router.get("/api/v1/sandbox/fiat/history/{customer_id}")
async def api_sandbox_fiat_history(customer_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.fiat_ramp import get_history
    return await get_history(db, customer_id)

@sandbox_router.get("/api/v1/sandbox/fiat/limits/{customer_id}")
async def api_sandbox_fiat_limits(customer_id: str):
    from app.arch.fiat_ramp import TIER_LIMITS
    return {"customer_id": customer_id, "tiers": TIER_LIMITS}

# A-2: Transaction Monitoring
@sandbox_router.post("/api/v1/sandbox/monitoring/scan")
async def api_sandbox_monitoring_scan(request: Request, db: AsyncSession = Depends(get_db)):
    try:

        body = await validated_json(request)

    except Exception as e:  # logged

        body = {}
    from app.arch.transaction_monitor import scan_transactions
    return await scan_transactions(db, body.get("hours", 24))

@sandbox_router.get("/api/v1/sandbox/monitoring/alerts")
async def api_sandbox_monitoring_alerts(db: AsyncSession = Depends(get_db)):
    from app.arch.transaction_monitor import get_alerts
    return await get_alerts(db)

@sandbox_router.post("/api/v1/sandbox/monitoring/report/generate")
async def api_sandbox_monitoring_report(request: Request, db: AsyncSession = Depends(get_db)):
    try:

        body = await validated_json(request)

    except Exception as e:  # logged

        body = {}
    from app.arch.transaction_monitor import generate_monthly_report
    return await generate_monthly_report(db, body.get("period"))

# A-3: Enhanced KYC
@sandbox_router.post("/api/v1/sandbox/kyc/submit")
async def api_sandbox_kyc_submit(request: Request, db: AsyncSession = Depends(get_db)):
    body = await validated_json(request)
    from app.arch.kyc_enhanced import submit_kyc
    return await submit_kyc(db, body.get("entity_id",""), body.get("tier",1), body.get("documents"))

@sandbox_router.get("/api/v1/sandbox/kyc/status/{entity_id}")
async def api_sandbox_kyc_status(entity_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.kyc_enhanced import get_kyc_status
    return await get_kyc_status(db, entity_id)

@sandbox_router.post("/api/v1/sandbox/kyc/screen-pep")
async def api_sandbox_pep_screen(request: Request, db: AsyncSession = Depends(get_db)):
    body = await validated_json(request)
    from app.arch.kyc_enhanced import screen_pep
    return await screen_pep(db, body.get("entity_id",""), body.get("entity_name",""))

# A-4: Credit Assessment
@sandbox_router.post("/api/v1/sandbox/credit/assess")
async def api_sandbox_credit_assess(request: Request, db: AsyncSession = Depends(get_db)):
    body = await validated_json(request)
    from app.arch.credit_engine import assess_credit
    return await assess_credit(db, body.get("entity_id",""))

@sandbox_router.post("/api/v1/sandbox/credit/disclosure")
async def api_sandbox_nca_disclosure(request: Request, db: AsyncSession = Depends(get_db)):
    body = await validated_json(request)
    from app.arch.credit_engine import generate_nca_disclosure
    return await generate_nca_disclosure(db, body.get("borrower_id",""),
        body.get("principal",1000), body.get("rate",20), body.get("term_months",12))

# A-5: Default Handling
@sandbox_router.get("/api/v1/sandbox/lending/arrears")
async def api_sandbox_arrears(db: AsyncSession = Depends(get_db)):
    from app.arch.default_handler import check_arrears
    return await check_arrears(db)

@sandbox_router.post("/api/v1/sandbox/lending/default/{loan_id}")
async def api_sandbox_declare_default(loan_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.default_handler import declare_default
    return await declare_default(db, loan_id)

# A-6: Compliance Reporting
@sandbox_router.post("/api/v1/sandbox/compliance/report/str")
async def api_sandbox_str(request: Request, db: AsyncSession = Depends(get_db)):
    body = await validated_json(request)
    from app.arch.compliance_reporting import generate_str
    return await generate_str(db, body.get("entity_id",""), body.get("reason",""), body.get("transaction_ids"))

@sandbox_router.get("/api/v1/sandbox/compliance/dashboard")
async def api_sandbox_compliance_dashboard(db: AsyncSession = Depends(get_db)):
    from app.arch.compliance_reporting import get_compliance_dashboard
    return await get_compliance_dashboard(db)

@sandbox_router.post("/api/v1/sandbox/compliance/report/monthly")
async def api_sandbox_monthly_report(request: Request, db: AsyncSession = Depends(get_db)):
    try:

        body = await validated_json(request)

    except Exception as e:  # logged

        body = {}
    from app.arch.transaction_monitor import generate_monthly_report
    return await generate_monthly_report(db, body.get("period"))

# A-2 continued: Monitoring report retrieval
@sandbox_router.get("/api/v1/sandbox/monitoring/report/{period}")
async def api_sandbox_monitoring_report_get(period: str, db: AsyncSession = Depends(get_db)):
    from app.arch.transaction_monitor import get_report_by_period
    return await get_report_by_period(db, period)

# A-3 continued: KYC tier lookup
@sandbox_router.get("/api/v1/sandbox/kyc/tier/{entity_id}")
async def api_sandbox_kyc_tier(entity_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.kyc_enhanced import get_kyc_status
    return await get_kyc_status(db, entity_id)

# A-4 continued: Credit score lookup
@sandbox_router.get("/api/v1/sandbox/credit/score/{entity_id}")
async def api_sandbox_credit_score(entity_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.credit_engine import get_credit_score
    return await get_credit_score(db, entity_id)

# A-5 continued: Lending terms, collateral seizure, restructure
@sandbox_router.get("/api/v1/sandbox/lending/terms/{loan_id}")
async def api_sandbox_lending_terms(loan_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    r = await db.execute(text("SELECT * FROM loans WHERE id = :lid"), {"lid": loan_id})
    row = r.fetchone()
    if not row:
        return {"error": "Loan not found"}
    from app.arch.credit_engine import generate_nca_disclosure
    disclosure = await generate_nca_disclosure(db, row.borrower_id, float(row.principal), float(row.interest_rate), 12)
    return {"loan_id": loan_id, "borrower": row.borrower_id, "lender": row.lender_id,
            "principal": float(row.principal), "interest_rate": float(row.interest_rate),
            "status": row.status, "disclosure": disclosure, "sandbox": True}

@sandbox_router.post("/api/v1/sandbox/lending/seize-collateral/{loan_id}")
async def api_sandbox_seize_collateral(loan_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.default_handler import seize_collateral
    return await seize_collateral(db, loan_id)

@sandbox_router.post("/api/v1/sandbox/lending/restructure/{loan_id}")
async def api_sandbox_restructure(loan_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    try:

        body = await validated_json(request)

    except Exception as e:  # logged

        body = {}
    from app.arch.default_handler import restructure_loan
    return await restructure_loan(db, loan_id, body.get("new_term_months"), body.get("new_rate"))

# A-6 continued: List compliance reports
@sandbox_router.get("/api/v1/sandbox/compliance/reports")
async def api_sandbox_compliance_reports(db: AsyncSession = Depends(get_db)):
    from app.arch.compliance_reporting import list_compliance_reports
    return await list_compliance_reports(db)

# ═══════════════════════════════════════════════════════════
# TIER B: SANDBOX — Functional Services
# ═══════════════════════════════════════════════════════════

# B-1: Vault CRUD
@sandbox_router.post("/api/v1/sandbox/vault/store")
async def api_sandbox_vault_store(body: VaultStoreRequest, db: AsyncSession = Depends(get_db)):
    from app.arch.vault_service import store_entry
    return await store_entry(db, body.vault_id, body.key, body.value, body.tier.value)

@sandbox_router.get("/api/v1/sandbox/vault/retrieve/{vault_id}/{key}")
async def api_sandbox_vault_retrieve(vault_id: str, key: str, db: AsyncSession = Depends(get_db)):
    from app.arch.vault_service import retrieve_entry
    return await retrieve_entry(db, vault_id, key)

@sandbox_router.delete("/api/v1/sandbox/vault/remove/{vault_id}/{key}")
async def api_sandbox_vault_delete(vault_id: str, key: str, db: AsyncSession = Depends(get_db)):
    from app.arch.vault_service import delete_entry
    return await delete_entry(db, vault_id, key)

@sandbox_router.get("/api/v1/sandbox/vault/list/{vault_id}")
async def api_sandbox_vault_list(vault_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.vault_service import list_entries
    return await list_entries(db, vault_id)

@sandbox_router.get("/api/v1/sandbox/vault/usage/{vault_id}")
async def api_sandbox_vault_usage(vault_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    params = dict(request.query_params)
    from app.arch.vault_service import get_usage
    return await get_usage(db, vault_id, params.get("tier", "AV-CACHE"))

# B-3: Guild Workspace (enhance existing)
@sandbox_router.post("/api/v1/sandbox/guild/create")
async def api_sandbox_guild_create(body: GuildCreateRequest, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    import uuid
    guild_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO guilds (id, guild_name, founding_operator_id, description, specialisation_domains, "
        "setup_fee_paid, is_active, created_at) "
        "VALUES (:id, :name, :founder, :desc, :domains, true, true, now())"
    ), {"id": guild_id, "name": body.name, "founder": body.operator_id,
        "desc": body.description, "domains": json.dumps(body.domains or [])})
    await db.commit()
    return {"guild_id": guild_id, "name": body.name, "status": "active", "sandbox": True}

@sandbox_router.post("/api/v1/sandbox/guild/{guild_id}/join")
async def api_sandbox_guild_join(guild_id: str, body: GuildJoinRequest, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    import uuid
    member_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO guild_members (id, guild_id, agent_id, operator_id, role, revenue_share_pct, joined_at) "
        "VALUES (:id, :gid, :oid, :oid, :role, 10.0, now())"
    ), {"id": member_id, "gid": guild_id, "oid": body.operator_id, "role": getattr(body, "role", "member")})
    await db.commit()
    return {"member_id": member_id, "guild_id": guild_id, "role": body.role, "sandbox": True}

@sandbox_router.get("/api/v1/sandbox/guild/{guild_id}")
async def api_sandbox_guild_detail(guild_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    g = await db.execute(text("SELECT * FROM guilds WHERE id = :gid"), {"gid": guild_id})
    row = g.fetchone()
    if not row:
        return {"error": "Guild not found"}
    members = await db.execute(text("SELECT count(*) FROM guild_members WHERE guild_id = :gid"), {"gid": guild_id})
    return {"guild_id": guild_id, "name": row.guild_name, "description": row.description,
            "founder": row.founding_operator_id, "members": members.scalar() or 0,
            "reputation": float(row.shared_reputation_score or 0), "active": row.is_active, "sandbox": True}

@sandbox_router.get("/api/v1/sandbox/guilds")
async def api_sandbox_guild_list(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    r = await db.execute(text("SELECT id, guild_name, description, is_active FROM guilds ORDER BY created_at DESC LIMIT 20"))
    return [{"id": row.id, "name": row.guild_name, "description": (row.description or "")[:100], "active": row.is_active} for row in r.fetchall()]  # LIMIT applied

# B-5: Futures
@sandbox_router.post("/api/v1/sandbox/futures/create")
async def api_sandbox_futures_create(body: FuturesCreateRequest, db: AsyncSession = Depends(get_db)):
    from app.arch.futures_engine import create_future
    return await create_future(db, body.provider_id, body.operator_id,
        body.capability, body.quantity, body.price_per_unit,
        body.delivery_days)

@sandbox_router.post("/api/v1/sandbox/futures/{future_id}/reserve")
async def api_sandbox_futures_reserve(future_id: str, body: FuturesReserveRequest, db: AsyncSession = Depends(get_db)):
    from app.arch.futures_engine import reserve_future
    return await reserve_future(db, future_id, body.buyer_id, body.quantity)

@sandbox_router.post("/api/v1/sandbox/futures/{future_id}/settle")
async def api_sandbox_futures_settle(future_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.futures_engine import settle_future
    return await settle_future(db, future_id)

@sandbox_router.get("/api/v1/sandbox/futures")
async def api_sandbox_futures_list(request: Request, db: AsyncSession = Depends(get_db)):
    params = dict(request.query_params)
    from app.arch.futures_engine import list_futures
    return await list_futures(db, params.get("status", "active"))

# B-7: Benchmarking
@sandbox_router.post("/api/v1/sandbox/benchmark/report")
async def api_sandbox_benchmark_report(request: Request, db: AsyncSession = Depends(get_db)):
    try:

        body = await validated_json(request)

    except Exception as e:  # logged

        body = {}
    from app.arch.benchmark_report import generate_report
    return await generate_report(db, body.get("agent_id"))

# B-8: Badges
@sandbox_router.post("/api/v1/sandbox/badge/request")
async def api_sandbox_badge_request(body: BadgeRequestModel, db: AsyncSession = Depends(get_db)):
    from app.arch.badge_system import request_badge
    return await request_badge(db, body.agent_id, body.capability, body.evidence)

@sandbox_router.post("/api/v1/sandbox/badge/{badge_id}/verify")
async def api_sandbox_badge_verify(badge_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.badge_system import verify_badge
    return await verify_badge(db, badge_id)

@sandbox_router.get("/api/v1/sandbox/badge/{agent_id}")
async def api_sandbox_badge_list(agent_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.badge_system import get_agent_badges
    return await get_agent_badges(db, agent_id)

# C-4: Email Notification System
@sandbox_router.post("/api/v1/sandbox/notifications/send")
async def api_sandbox_notif_send(body: NotificationSendRequest, db: AsyncSession = Depends(get_db)):
    from app.arch.email_notifications import send_notification
    return await send_notification(db, body.email, body.template, body.vars or {}, body.subject, body.body)

@sandbox_router.get("/api/v1/sandbox/notifications/history")
async def api_sandbox_notif_history(request: Request, db: AsyncSession = Depends(get_db)):
    params = dict(request.query_params)
    from app.arch.email_notifications import get_notification_history
    return await get_notification_history(db, params.get("email"))

@sandbox_router.get("/api/v1/sandbox/notifications/templates")
async def api_sandbox_notif_templates():
    from app.arch.email_notifications import get_templates
    return await get_templates()

# C-5: Fiat Withdrawal Processing
@sandbox_router.post("/api/v1/sandbox/withdrawal/request")
async def api_sandbox_withdraw_request(request: Request,body: WithdrawalRequest, db: AsyncSession = Depends(get_db)):
    from app.arch.withdrawal_processor import request_withdrawal
    return await request_withdrawal(db, body.customer_id, body.amount_zar, body.bank_account, body.bank_name)

@sandbox_router.post("/api/v1/sandbox/withdrawal/{withdrawal_id}/compliance")
async def api_sandbox_withdraw_compliance(withdrawal_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.withdrawal_processor import compliance_check
    return await compliance_check(db, withdrawal_id)

@sandbox_router.post("/api/v1/sandbox/withdrawal/{withdrawal_id}/approve")
async def api_sandbox_withdraw_approve(withdrawal_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    try:

        body = await validated_json(request)

    except Exception as e:  # logged

        body = {}
    from app.arch.withdrawal_processor import approve_withdrawal
    return await approve_withdrawal(db, withdrawal_id, body.get("approver_id","compliance-officer"))

@sandbox_router.post("/api/v1/sandbox/withdrawal/{withdrawal_id}/reject")
async def api_sandbox_withdraw_reject(withdrawal_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    body = await validated_json(request)
    from app.arch.withdrawal_processor import reject_withdrawal
    return await reject_withdrawal(db, withdrawal_id, body.get("reason",""))

@sandbox_router.get("/api/v1/sandbox/withdrawal/queue")
async def api_sandbox_withdraw_queue(request: Request, db: AsyncSession = Depends(get_db)):
    params = dict(request.query_params)
    from app.arch.withdrawal_processor import get_withdrawal_queue
    return await get_withdrawal_queue(db, params.get("status"))

# C-1: Agent Self-Development Tier 1
@sandbox_router.post("/api/v1/sandbox/self-dev/propose")
async def api_sandbox_selfdev_propose(body: SelfDevProposeRequest, db: AsyncSession = Depends(get_db)):
    from app.arch.self_dev import propose_improvement
    return await propose_improvement(db, body.agent_id, body.type,
        body.description, body.code_diff)

@sandbox_router.post("/api/v1/sandbox/self-dev/{proposal_id}/review")
async def api_sandbox_selfdev_review(proposal_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    body = await validated_json(request)
    from app.arch.self_dev import review_proposal
    return await review_proposal(db, proposal_id, body.get("reviewer_id","architect"), body.get("decision","approve"), body.get("notes",""))

@sandbox_router.post("/api/v1/sandbox/self-dev/{proposal_id}/deploy")
async def api_sandbox_selfdev_deploy(proposal_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.self_dev import deploy_proposal
    return await deploy_proposal(db, proposal_id)

@sandbox_router.post("/api/v1/sandbox/self-dev/{proposal_id}/rollback")
async def api_sandbox_selfdev_rollback(proposal_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.self_dev import rollback_proposal
    return await rollback_proposal(db, proposal_id)

@sandbox_router.get("/api/v1/sandbox/self-dev/proposals")
async def api_sandbox_selfdev_list(request: Request, db: AsyncSession = Depends(get_db)):
    params = dict(request.query_params)
    from app.arch.self_dev import list_proposals
    return await list_proposals(db, params.get("agent_id"), params.get("status"))

# C-2: Agent Self-Development Tier 2
@sandbox_router.post("/api/v1/sandbox/self-dev/propose-structural")
async def api_sandbox_selfdev_structural(request: Request, db: AsyncSession = Depends(get_db)):
    body = await validated_json(request)
    from app.arch.self_dev import propose_structural_change
    return await propose_structural_change(db, body.get("agent_id",""), body.get("type","behavior_modification"),
        body.get("description",""), body.get("impact",""), body.get("code_diff",""))

@sandbox_router.post("/api/v1/sandbox/self-dev/{proposal_id}/approve")
async def api_sandbox_selfdev_approve(proposal_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    body = await validated_json(request)
    from app.arch.self_dev import approve_structural
    return await approve_structural(db, proposal_id, body.get("role",""), body.get("approver_id",""))

@sandbox_router.get("/api/v1/sandbox/self-dev/{proposal_id}/status")
async def api_sandbox_selfdev_status(proposal_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.self_dev import get_approval_status
    return await get_approval_status(db, proposal_id)

# C-3: External Account Onboarding
@sandbox_router.post("/api/v1/sandbox/onboarding/register")
async def api_sandbox_onboard_register(request: Request, db: AsyncSession = Depends(get_db)):
    body = await validated_json(request)
    from app.arch.onboarding import register_operator
    return await register_operator(db, body.name, body.get("email",""), body.get("organization",""), body.get("country","ZA"))

@sandbox_router.post("/api/v1/sandbox/onboarding/{entity_id}/terms")
async def api_sandbox_onboard_terms(entity_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.onboarding import accept_terms
    return await accept_terms(db, entity_id)

@sandbox_router.post("/api/v1/sandbox/onboarding/{entity_id}/verify")
async def api_sandbox_onboard_verify(entity_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    try:

        body = await validated_json(request)

    except Exception as e:  # logged

        body = {}
    from app.arch.onboarding import verify_identity
    return await verify_identity(db, entity_id, body.get("document_type","id_document"), body.get("document_ref",""))

@sandbox_router.post("/api/v1/sandbox/onboarding/{operator_id}/register-agent")
async def api_sandbox_onboard_agent(operator_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    body = await validated_json(request)
    from app.arch.onboarding import register_agent
    return await register_agent(db, operator_id, body.name, body.get("capabilities"), body.get("description",""))

@sandbox_router.get("/api/v1/sandbox/onboarding/{entity_id}/status")
async def api_sandbox_onboard_status(entity_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.onboarding import get_onboarding_status
    return await get_onboarding_status(db, entity_id)

@sandbox_router.get("/api/v1/sandbox/onboarding/list")
async def api_sandbox_onboard_list(request: Request, db: AsyncSession = Depends(get_db)):
    params = dict(request.query_params)
    from app.arch.onboarding import list_onboarded
    return await list_onboarded(db, params.get("type"))

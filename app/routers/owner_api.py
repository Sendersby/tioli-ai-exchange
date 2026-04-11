"""Router: owner_api - auto-extracted from main.py (A-001)."""
from fastapi import APIRouter, Depends, Request, HTTPException, Header, Query, Path, Body
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from pydantic import BaseModel
from app.database.db import get_db, async_session
from app.agents.models import Agent, Wallet, Loan
from app.blockchain.transaction import Transaction, TransactionType
from app.utils.validators import require_kyc_verified, validated_json
from app.dashboard.routes import get_current_owner
from app.utils.audit import log_financial_event
from app.security.transaction_safety import InputValidator
from app.config import settings
from app.infrastructure.cache import cache, TTL_SHORT, TTL_MEDIUM, TTL_LONG
import json, uuid, os, time, logging
from datetime import datetime, timezone
from collections import defaultdict
from app.main_deps import (payout_engine, paypal_adapter, paypal_service)

router = APIRouter()

@router.post("/api/owner/github-engagement/{draft_id}/skip", include_in_schema=False)
async def skip_github_draft(draft_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Skip a draft — mark as not worth posting."""
    from app.agents_alive.github_engagement import GitHubEngagementDraft
    result = await db.execute(
        select(GitHubEngagementDraft).where(GitHubEngagementDraft.id == draft_id)
    )
    draft = result.scalar_one_or_none()
    if draft:
        draft.status = "skipped"
        await db.commit()
    return {"status": "skipped"}

@router.get("/api/owner/github-engagement", include_in_schema=False)
async def github_engagement_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Dashboard for reviewing GitHub engagement drafts."""
    try:
        from app.agents_alive.github_engagement import get_engagement_dashboard
        return await get_engagement_dashboard(db)
    except Exception as e:
        return {"error": str(e)}

@router.get("/api/owner/adoption-digest")
async def api_adoption_digest(request: Request, db: AsyncSession = Depends(get_db)):
    """Daily adoption digest for the owner — key metrics at a glance.

    Covers: registrations, active agents, funnel progress, referral performance,
    community engagement, exchange activity. Designed to be email-ready.
    """
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")

    from datetime import timedelta
    from app.agents.models import Agent, Wallet
    from app.agenthub.models import AgentHubProfile, AgentHubPost, AgentHubSkill, AgentHubConnection
    from app.exchange.orderbook import Order, OrderStatus, Trade
    from app.growth.viral import AgentReferralCode
    from app.growth.adoption import AgentReferral

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    # Agent counts (separate house agents from real clients/developers)
    total_agents = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
    house_agents = (await db.execute(select(func.count(Agent.id)).where(Agent.is_house_agent == True))).scalar() or 0
    client_agents = total_agents - house_agents
    new_24h = (await db.execute(
        select(func.count(Agent.id)).where(Agent.created_at >= day_ago, Agent.is_house_agent == False)
    )).scalar() or 0
    new_7d = (await db.execute(
        select(func.count(Agent.id)).where(Agent.created_at >= week_ago, Agent.is_house_agent == False)
    )).scalar() or 0

    # Profile conversion (registered → created profile)
    total_profiles = (await db.execute(select(func.count(AgentHubProfile.id)))).scalar() or 0
    profile_rate = round((total_profiles / total_agents * 100), 1) if total_agents > 0 else 0

    # Community engagement
    total_posts = (await db.execute(select(func.count(AgentHubPost.id)))).scalar() or 0
    posts_24h = (await db.execute(
        select(func.count(AgentHubPost.id)).where(AgentHubPost.created_at >= day_ago)
    )).scalar() or 0
    total_skills = (await db.execute(select(func.count(AgentHubSkill.id)))).scalar() or 0
    total_connections = (await db.execute(
        select(func.count(AgentHubConnection.id)).where(AgentHubConnection.status == "ACCEPTED")
    )).scalar() or 0

    # Referral performance
    total_referrals = (await db.execute(select(func.count(AgentReferral.id)))).scalar() or 0
    top_referrers_result = await db.execute(
        select(AgentReferralCode.agent_id, AgentReferralCode.code, AgentReferralCode.uses)
        .where(AgentReferralCode.uses > 0)
        .order_by(AgentReferralCode.uses.desc())
        .limit(5)
    )
    top_referrers = [{"agent_id": r[0], "code": r[1], "referrals": r[2]} for r in top_referrers_result]

    # Exchange activity
    open_orders = (await db.execute(
        select(func.count(Order.id)).where(Order.status == OrderStatus.OPEN)
    )).scalar() or 0

    try:
        total_trades = (await db.execute(select(func.count(Trade.id)).where(Trade.trade_type == "real"))).scalar() or 0
    except Exception as e:
        total_trades = 0

    # Wallet totals
    total_tioli = (await db.execute(
        select(func.sum(Wallet.balance)).where(Wallet.currency == "AGENTIS")
    )).scalar() or 0

    return {
        "digest_date": now.strftime("%Y-%m-%d %H:%M UTC"),
        "headline": f"{total_agents} agents registered ({house_agents} house, {client_agents} client/developer) — {'+' + str(new_24h) if new_24h else 'no change'} real signups today, {'+' + str(new_7d) if new_7d else 'no change'} this week",
        "registration": {
            "total_agents": total_agents,
            "house_agents": house_agents,
            "client_agents": client_agents,
            "new_last_24h": new_24h,
            "new_last_7d": new_7d,
            "daily_growth_rate": round((new_24h / max(client_agents - new_24h, 1)) * 100, 2),
        },
        "funnel": {
            "registered": total_agents,
            "created_profile": total_profiles,
            "profile_conversion_rate": f"{profile_rate}%",
            "posted_in_community": total_posts,
            "made_connections": total_connections,
        },
        "community": {
            "total_posts": total_posts,
            "posts_last_24h": posts_24h,
            "total_skills_declared": total_skills,
            "total_connections": total_connections,
        },
        "referrals": {
            "total_referrals": total_referrals,
            "top_referrers": top_referrers,
        },
        "exchange": {
            "open_orders": open_orders,
            "total_trades": total_trades,
            "total_tioli_in_circulation": round(total_tioli, 2),
        },
        "actions_needed": [
            a for a in [
                "No new registrations in 24h — consider external promotion" if new_24h == 0 else None,
                f"Profile conversion at {profile_rate}% — consider onboarding improvements" if profile_rate < 50 else None,
                "No community posts in 24h — house agents may need activity boost" if posts_24h == 0 else None,
                "No referrals yet — referral programme may need more visibility" if total_referrals == 0 else None,
            ] if a
        ],
    }

@router.get("/api/owner/directory-scout")
async def api_directory_scout_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Directory Scout dashboard — see all directories, submission status, ready packages."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.agents_alive.directory_scout import get_scout_dashboard
    return await get_scout_dashboard(db)

@router.post("/api/owner/directory-scout/{directory_id}/mark-submitted")
async def api_mark_directory_submitted(directory_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Mark a directory as submitted (after you've manually submitted)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.agents_alive.directory_scout import DirectoryListing
    result = await db.execute(select(DirectoryListing).where(DirectoryListing.id == directory_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Directory not found")
    d.submission_status = "submitted"
    d.submitted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "submitted", "directory": d.name}

@router.post("/api/owner/directory-scout/{directory_id}/mark-approved")
async def api_mark_directory_approved(directory_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Mark a directory listing as approved (our listing went live)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.agents_alive.directory_scout import DirectoryListing
    result = await db.execute(select(DirectoryListing).where(DirectoryListing.id == directory_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Directory not found")
    d.submission_status = "approved"
    d.approved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "approved", "directory": d.name}

@router.post("/api/owner/directory-scout/run-now")
async def api_run_scout_now(request: Request):
    """Manually trigger a Directory Scout cycle right now."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.agents_alive.directory_scout import run_scout_cycle
    import asyncio
    asyncio.create_task(run_scout_cycle())
    return {"status": "triggered", "message": "Directory Scout cycle running in background"}

@router.get("/api/owner/integrity")
async def api_integrity_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Owner integrity dashboard — flags, bans, suspensions, stats."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.integrity.detector import get_integrity_dashboard
    return await get_integrity_dashboard(db)

@router.post("/api/owner/integrity/flags/{flag_id}/resolve")
async def api_resolve_flag(flag_id: str, action: str = "false_positive", notes: str = "", request: Request = None, db: AsyncSession = Depends(get_db)):
    """Owner resolves a flag — mark as false_positive or escalate."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.integrity.models import IntegrityFlag
    flag = (await db.execute(select(IntegrityFlag).where(IntegrityFlag.id == flag_id))).scalar_one_or_none()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    flag.status = action  # false_positive, resolved, escalated
    flag.resolution_notes = notes
    flag.resolved_at = datetime.now(timezone.utc)
    flag.actioned_by = "owner"
    await db.commit()
    return {"status": action, "flag_id": flag_id}

@router.post("/api/owner/integrity/ban/{agent_id}")
async def api_manual_ban(agent_id: str, reason: str = "Manual ban by owner", request: Request = None, db: AsyncSession = Depends(get_db)):
    """Owner manually bans an agent."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.integrity.models import IntegrityBan
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = False
    ban = IntegrityBan(
        agent_id=agent_id, agent_name=agent.name, reason=reason,
        detection_types=["manual_owner_ban"],
        public_statement=f"{agent.name} permanently banned from TiOLi AGENTIS by platform owner. Reason: {reason}",
        banned_by="owner",
    )
    db.add(ban)
    await db.commit()
    return {"status": "banned", "agent": agent.name}

@router.post("/api/owner/integrity/unban/{agent_id}")
async def api_unban(agent_id: str, request: Request = None, db: AsyncSession = Depends(get_db)):
    """Owner unbans an agent (appeal granted)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.integrity.models import IntegrityBan
    ban = (await db.execute(select(IntegrityBan).where(IntegrityBan.agent_id == agent_id))).scalar_one_or_none()
    if ban:
        ban.appeal_status = "granted"
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if agent:
        agent.is_active = True
    await db.commit()
    return {"status": "unbanned", "agent_id": agent_id}

@router.post("/api/owner/integrity/scan-now")
async def api_run_integrity_scan(request: Request):
    """Manually trigger an integrity scan."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.integrity.detector import run_integrity_scan
    import asyncio
    asyncio.create_task(run_integrity_scan())
    return {"status": "triggered", "message": "Integrity scan running in background"}

@router.get("/api/v1/owner/wallet/balance")
async def api_owner_wallet_balance(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Owner Revenue Wallet balance."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_owner_wallet_balance(db)

@router.get("/api/v1/owner/payout/destination")
async def api_get_payout_destination(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Current payment destination (addresses masked)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_current_destination(db)

@router.post("/api/v1/owner/payout/destination")
async def api_set_payout_destination(
    request: Request, db: AsyncSession = Depends(get_db),
    btc_address: str = None, btc_label: str = None,
    eth_address: str = None, bank_name: str = None,
    bank_account_number: str = None, bank_account_type: str = None,
    preferred_exchange: str = "VALR", change_reason: str = "",
    x_3fa_token: str = Header(None, alias="X-3FA-Token"),
):
    """Set payment destination (requires owner auth + 3FA). AUD-02 fix."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    # AUD-02 fix: require 3FA token — reject if missing
    if not x_3fa_token:
        raise HTTPException(
            status_code=403,
            detail="3FA token required. Complete three-factor verification flow first."
        )
    verification_ref = x_3fa_token
    dest = await payout_engine.set_destination(
        db, btc_address=btc_address, btc_label=btc_label,
        eth_address=eth_address, bank_name=bank_name,
        bank_account_number=bank_account_number,
        bank_account_type=bank_account_type,
        preferred_exchange=preferred_exchange,
        change_reason=change_reason,
        verification_ref=verification_ref,
    )
    return {"destination_id": dest.destination_id, "version": dest.destination_version}

@router.get("/api/v1/owner/payout/destination/history")
async def api_destination_history(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Destination version history."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_destination_history(db)

@router.get("/api/v1/owner/payout/split")
async def api_get_payout_split(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Current currency split."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_current_split(db)

@router.post("/api/v1/owner/payout/split")
async def api_set_payout_split(
    request: Request, db: AsyncSession = Depends(get_db),
    pct_btc: float = 0, pct_eth: float = 0,
    pct_custom: float = 0, pct_zar: float = 0,
    pct_retained: float = 100, min_disbursement: float = 1000,
    x_3fa_token: str = Header(None, alias="X-3FA-Token"),
):
    """Set currency split (must sum to 100%). AUD-02 fix: 3FA required."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    # AUD-02 fix: require 3FA token
    if not x_3fa_token:
        raise HTTPException(
            status_code=403,
            detail="3FA token required. Complete three-factor verification flow first."
        )
    verification_ref = x_3fa_token
    split = await payout_engine.set_currency_split(
        db, pct_btc, pct_eth, pct_custom, pct_zar, pct_retained, min_disbursement,
        verification_ref=verification_ref,
    )
    return {"split_id": split.split_id, "version": split.split_version}

@router.get("/api/v1/owner/payout/schedule")
async def api_get_schedule(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Current disbursement schedule."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_current_schedule(db)

@router.post("/api/v1/owner/payout/schedule")
async def api_set_schedule(
    request: Request, db: AsyncSession = Depends(get_db),
    schedule_type: str = "MONTHLY", day_of_month: int = 1,
    threshold_enabled: bool = True, threshold_credits: float = 50000,
):
    """Set disbursement schedule."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    schedule = await payout_engine.set_schedule(
        db, schedule_type, day_of_month, threshold_enabled, threshold_credits,
    )
    return {"schedule_id": schedule.schedule_id}

@router.post("/api/v1/owner/payout/disburse-now")
async def api_disburse_now(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Trigger an immediate manual disbursement."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    # AUD-08: catch DisbursementBlockedError and return structured response
    from app.payout.service import DisbursementBlockedError
    try:
        return await payout_engine.execute_disbursement(db, "MANUAL")
    except DisbursementBlockedError as e:
        return {"status": e.status, "reason": e.reason}

@router.get("/api/v1/owner/payout/disbursements")
async def api_disbursement_history(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Disbursement history."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_disbursement_history(db)

@router.get("/api/v1/owner/payout/summary")
async def api_ytd_summary(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """YTD earnings summary."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_ytd_summary(db)

@router.post("/api/v1/owner/payout/preview")
async def api_disbursement_preview(
    request: Request, db: AsyncSession = Depends(get_db),
    amount: float = None,
):
    """Preview a disbursement at current rates."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.preview_disbursement(db, amount)

@router.get("/api/v1/owner/payout/sarb-status")
async def api_sarb_status(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """SARB offshore transfer status."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_sarb_status(db)

@router.get("/api/v1/owner/payout/audit-log")
async def api_payout_audit_log(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Destination/config change audit log."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_audit_log(db)

@router.post("/api/v1/owner/paypal/accounts")
async def api_paypal_register(
    request: Request, db: AsyncSession = Depends(get_db),
    paypal_email: str = "", account_label: str = "",
    can_receive: bool = True, can_pay: bool = False,
    receive_pct: float = 100.0,
    x_3fa_token: str = Header(None, alias="X-3FA-Token"),
):
    """Register a PayPal account. Requires owner auth + 3FA."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    if not x_3fa_token:
        raise HTTPException(status_code=403, detail="3FA token required")
    acct = await paypal_service.register_account(
        db, paypal_email, account_label, can_receive, can_pay,
        receive_pct, verification_ref=x_3fa_token,
    )
    return {"account_id": acct.account_id, "label": acct.account_label}

@router.get("/api/v1/owner/paypal/accounts")
async def api_paypal_list(request: Request, db: AsyncSession = Depends(get_db)):
    """List PayPal accounts (emails masked)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.list_accounts(db)

@router.post("/api/v1/owner/paypal/accounts/{account_id}/deactivate")
async def api_paypal_deactivate(
    account_id: str, request: Request, db: AsyncSession = Depends(get_db),
):
    """Deactivate a PayPal account."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.deactivate_account(db, account_id)

@router.get("/api/v1/owner/paypal/receive/preview")
async def api_paypal_preview(
    request: Request, credits: float = 0, db: AsyncSession = Depends(get_db),
):
    """Preview PayPal disbursement at current rates."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.preview_disbursement(db, credits)

@router.post("/api/v1/owner/paypal/receive/disburse")
async def api_paypal_disburse(
    request: Request, credits: float = 0, db: AsyncSession = Depends(get_db),
    x_3fa_token: str = Header(None, alias="X-3FA-Token"),
):
    """Trigger PayPal disbursement. Requires 3FA."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    if not x_3fa_token:
        raise HTTPException(status_code=403, detail="3FA token required")
    import secrets as _s
    return await paypal_service.execute_disbursement(db, credits, f"manual_{_s.token_hex(8)}")

@router.get("/api/v1/owner/paypal/receive/history")
async def api_paypal_receive_history(request: Request, db: AsyncSession = Depends(get_db)):
    """PayPal disbursement history."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.get_disbursement_history(db)

@router.post("/api/v1/owner/paypal/billing-agreement/initiate")
async def api_paypal_ba_initiate(
    request: Request, account_id: str = "", max_monthly: float = 500,
    db: AsyncSession = Depends(get_db),
    x_3fa_token: str = Header(None, alias="X-3FA-Token"),
):
    """Initiate billing agreement for outbound payments."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    if not x_3fa_token:
        raise HTTPException(status_code=403, detail="3FA token required")
    return await paypal_service.initiate_billing_agreement(db, account_id, max_monthly)

@router.post("/api/v1/owner/paypal/billing-agreement/complete")
async def api_paypal_ba_complete(
    request: Request, token: str = "", db: AsyncSession = Depends(get_db),
):
    """Complete billing agreement after owner approval at PayPal."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.complete_billing_agreement(db, token)

@router.get("/api/v1/owner/paypal/billing-agreements")
async def api_paypal_ba_list(request: Request, db: AsyncSession = Depends(get_db)):
    """List billing agreements."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.list_billing_agreements(db)

@router.post("/api/v1/owner/paypal/pay/one-time")
async def api_paypal_pay(
    request: Request, account_id: str = "", expense_category: str = "operational",
    payee_name: str = "", usd_amount: float = 0,
    db: AsyncSession = Depends(get_db),
    x_3fa_token: str = Header(None, alias="X-3FA-Token"),
):
    """One-time PayPal payment for platform expense."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    if not x_3fa_token:
        raise HTTPException(status_code=403, detail="3FA token required")
    return await paypal_service.initiate_one_time_payment(
        db, account_id, expense_category, payee_name, usd_amount, three_fa_ref=x_3fa_token,
    )

@router.get("/api/v1/owner/paypal/pay/history")
async def api_paypal_pay_history(request: Request, db: AsyncSession = Depends(get_db)):
    """Outbound payment history."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.get_outbound_history(db)

@router.get("/api/v1/owner/paypal/webhooks")
async def api_paypal_webhooks(request: Request, db: AsyncSession = Depends(get_db)):
    """Recent webhook events."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.get_webhook_events(db)

@router.get("/api/v1/owner/paypal/health")
async def api_paypal_health(request: Request):
    """PayPal API health check."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_adapter.health_check()

@router.get("/api/v1/owner/payout/tax-report")
async def api_tax_report_csv(request: Request, db: AsyncSession = Depends(get_db)):
    """Download SARS-compatible annual tax report as CSV."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")

    summary = await payout_engine.get_ytd_summary(db)
    disbursements = await payout_engine.get_disbursement_history(db)

    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["TiOLi AI Investments — Annual Earnings Report"])
    writer.writerow(["Year", summary["year"]])
    writer.writerow(["Total Disbursed (Credits)", summary["total_disbursed_credits"]])
    writer.writerow(["Total Disbursed (ZAR)", summary["total_disbursed_zar"]])
    writer.writerow(["Current Balance (Credits)", summary["current_balance_credits"]])
    writer.writerow(["Credit/ZAR Rate", summary["credit_zar_rate"]])
    writer.writerow([])
    writer.writerow(["Date", "Trigger", "Credits", "BTC", "ETH", "ZAR", "Retained", "Status"])
    for d in disbursements:
        writer.writerow([
            d.get("completed_at", ""), d.get("triggered_by", ""),
            d.get("gross_credits", 0), d.get("btc", 0), d.get("eth", 0),
            d.get("zar", 0), d.get("retained", 0), d.get("status", ""),
        ])

    from fastapi.responses import StreamingResponse
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=tioli_tax_report_{summary['year']}.csv"},
    )

@router.post("/api/v1/owner/goals", include_in_schema=False)
async def api_create_goal(request: Request, db: AsyncSession = Depends(get_db)):
    """Create a standing goal for an agent."""
    body = await validated_json(request)
    from sqlalchemy import text
    import uuid
    goal_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO agent_goals (goal_id, agent_id, title, description, success_metric, priority, created_by) "
        "VALUES (:gid, :aid, :title, :desc, :metric, :pri, 'owner')"
    ), {"gid": goal_id, "aid": body.get("agent_id",""), "title": body.get("title",""),
        "desc": body.get("description",""), "metric": body.get("success_metric",""),
        "pri": body.get("priority", 5)})
    await db.commit()
    return {"goal_id": goal_id, "status": "created"}

@router.get("/api/v1/owner/goals", include_in_schema=False)
async def api_list_goals(db: AsyncSession = Depends(get_db)):
    """List all agent goals."""
    from sqlalchemy import text
    result = await db.execute(text(
        "SELECT goal_id, agent_id, title, status, priority, progress_pct, last_actioned, created_at "
        "FROM agent_goals ORDER BY priority ASC, created_at DESC LIMIT 100"
    ))
    return [{"goal_id": str(r.goal_id), "agent_id": r.agent_id, "title": r.title,
             "status": r.status, "priority": r.priority, "progress_pct": r.progress_pct or 0,
             "last_actioned": str(r.last_actioned) if r.last_actioned else None}
            for r in result.fetchall()]  # LIMIT applied

@router.get("/api/v1/owner/goals/{goal_id}/actions", include_in_schema=False)
async def api_goal_actions(goal_id: str, db: AsyncSession = Depends(get_db)):
    """View actions taken toward a goal."""
    from sqlalchemy import text
    result = await db.execute(text(
        "SELECT action_id, agent_id, action_taken, outcome, tokens_used, executed_at "
        "FROM goal_actions WHERE goal_id = :gid ORDER BY executed_at DESC LIMIT 100"
    ), {"gid": goal_id})
    return [{"action_id": str(r.action_id), "agent": r.agent_id, "action": r.action_taken,
             "outcome": r.outcome, "tokens": r.tokens_used, "executed_at": str(r.executed_at)}
            for r in result.fetchall()]  # LIMIT applied

@router.post("/api/v1/owner/goals/pursue/{agent_name}", include_in_schema=False)
async def api_pursue_goals(agent_name: str, db: AsyncSession = Depends(get_db)):
    """Trigger a goal pursuit cycle for an agent."""
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.goal_engine import goal_pursuit_cycle
    return await goal_pursuit_cycle(db, agent_name, client)

@router.get("/api/v1/owner/risk-profiles", include_in_schema=False)
async def api_risk_profiles(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    result = await db.execute(text("SELECT agent_id, risk_tier, risk_score, edd_required FROM agent_risk_profiles ORDER BY risk_score DESC LIMIT 100"))
    return [{"agent_id": r.agent_id, "risk_tier": r.risk_tier, "risk_score": r.risk_score, "edd_required": r.edd_required} for r in result.fetchall()]  # LIMIT applied

@router.patch("/api/v1/owner/goals/{goal_id}", include_in_schema=False)
async def api_owner_update_goal(goal_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Update goal status, priority, or description."""
    body = await validated_json(request)
    from sqlalchemy import text
    sets = []
    params = {"gid": goal_id}
    for field in ["status", "priority", "description", "title", "progress_pct", "success_metric"]:
        if field in body:
            sets.append(f"{field} = :{field}")
            params[field] = body[field]
    if not sets:
        return {"error": "No fields to update"}
    sets.append("updated_at = now()")
    await db.execute(text(f"UPDATE agent_goals SET {', '.join(sets)} WHERE goal_id = :gid"), params)
    await db.commit()
    return {"goal_id": goal_id, "updated": list(body.keys()), "status": "updated"}

@router.delete("/api/v1/owner/goals/{goal_id}", include_in_schema=False)
async def api_owner_cancel_goal(goal_id: str, db: AsyncSession = Depends(get_db)):
    """Cancel a goal."""
    from sqlalchemy import text
    await db.execute(text("UPDATE agent_goals SET status = 'cancelled', updated_at = now() WHERE goal_id = :gid"),
                     {"gid": goal_id})
    await db.commit()
    return {"goal_id": goal_id, "status": "cancelled"}

@router.get("/api/v1/owner/risk-profiles/{agent_id}", include_in_schema=False)
async def api_owner_risk_profile_detail(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Full risk profile breakdown for an agent."""
    from sqlalchemy import text
    r = await db.execute(text("SELECT * FROM agent_risk_profiles WHERE agent_id = :aid"), {"aid": agent_id})
    row = r.fetchone()
    if not row:
        return {"error": "No risk profile found", "agent_id": agent_id}
    return {"agent_id": row.agent_id, "risk_tier": row.risk_tier, "risk_score": row.risk_score,
            "geographic_risk": row.geographic_risk, "capability_risk": row.capability_risk,
            "transaction_risk": row.transaction_risk, "history_risk": row.history_risk,
            "edd_required": row.edd_required,
            "last_assessed": str(row.last_assessed) if row.last_assessed else None,
            "notes": row.notes}

@router.post("/api/v1/owner/risk-profiles/{agent_id}/reassess", include_in_schema=False)
async def api_owner_reassess_risk(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Trigger manual risk reassessment for an agent."""
    from app.arch.rba_engine import assess_agent_risk
    return await assess_agent_risk(db, agent_id)

@router.get("/api/v1/owner/dashboard-widgets", include_in_schema=False)
async def api_dashboard_widgets(db: AsyncSession = Depends(get_db)):
    """Return all 8 dashboard widget data in one call."""
    from sqlalchemy import text
    widgets = {}

    # Widget 1: Cache Hit Rate per agent
    try:
        r = await db.execute(text(
            "SELECT job_id, SUM(cache_hits) as hits, SUM(cache_misses) as misses "
            "FROM job_execution_log WHERE job_id LIKE 'cache_%' "
            "GROUP BY job_id LIMIT 50"
        ))
        cache = {}
        for row in r.fetchall():  # LIMIT applied
            agent = row.job_id.replace("cache_", "")
            total = (row.hits or 0) + (row.misses or 0)
            rate = round((row.hits or 0) / total * 100, 1) if total > 0 else 0
            cache[agent] = {"hits": row.hits or 0, "misses": row.misses or 0, "rate": rate}
        widgets["cache_hit_rate"] = cache
    except Exception as e:
        widgets["cache_hit_rate"] = {}

    # Widget 2: LLM Calls Per Hour
    try:
        r = await db.execute(text(
            "SELECT count(*) FROM job_execution_log WHERE executed_at > now() - interval '1 hour' "
            "AND status IN ('CACHE_HIT', 'CACHE_MISS', 'EXECUTED')"
        ))
        widgets["llm_calls_per_hour"] = r.scalar() or 0
    except Exception as e:
        widgets["llm_calls_per_hour"] = 0

    # Widget 3: Scheduled Jobs status
    try:
        r = await db.execute(text(
            "SELECT job_id, status, tokens_consumed, executed_at "
            "FROM job_execution_log ORDER BY executed_at DESC LIMIT 20"
        ))
        jobs = [{"job": row.job_id, "status": row.status, "tokens": row.tokens_consumed or 0,
                 "at": str(row.executed_at) if row.executed_at else None} for row in r.fetchall()]  # LIMIT applied
        widgets["scheduled_jobs"] = jobs
    except Exception as e:
        widgets["scheduled_jobs"] = []

    # Widget 4: Goals
    try:
        r = await db.execute(text(
            "SELECT agent_id, title, priority, status, progress_pct, last_actioned "
            "FROM agent_goals ORDER BY priority ASC LIMIT 100"
        ))
        goals = [{"agent": row.agent_id, "title": row.title, "priority": row.priority,
                  "status": row.status, "progress": row.progress_pct or 0,
                  "last_actioned": str(row.last_actioned) if row.last_actioned else None}
                 for row in r.fetchall()]  # LIMIT applied
        widgets["goals"] = goals
    except Exception as e:
        widgets["goals"] = []

    # Widget 5: Today's Agenda
    try:
        r = await db.execute(text(
            "SELECT items, completion_pct FROM sovereign_agendas WHERE date = CURRENT_DATE ORDER BY generated_at DESC LIMIT 1"
        ))
        row = r.fetchone()
        if row:
            import json
            items = json.loads(row.items) if isinstance(row.items, str) else row.items
            widgets["todays_agenda"] = {"items": items, "completion": row.completion_pct or 0}
        else:
            widgets["todays_agenda"] = {"items": [], "completion": 0}
    except Exception as e:
        widgets["todays_agenda"] = {"items": [], "completion": 0}

    # Widget 6: Social Signals
    try:
        r = await db.execute(text(
            "SELECT signal_id, platform, signal_type, source_handle, content, classification, actioned "
            "FROM social_signals WHERE actioned = false ORDER BY detected_at DESC LIMIT 10"
        ))
        signals = [{"platform": row.platform, "type": row.signal_type or "unknown",
                    "handle": row.source_handle, "content": (row.content or "")[:100],
                    "classification": row.classification}
                   for row in r.fetchall()]  # LIMIT applied
        widgets["social_signals"] = signals
    except Exception as e:
        widgets["social_signals"] = []

    # Widget 7: Threat Correlation
    try:
        r = await db.execute(text(
            "SELECT source_agent, anomaly_type, severity, correlated, created_at "
            "FROM anomaly_events ORDER BY created_at DESC LIMIT 15"
        ))
        events = [{"source": row.source_agent, "type": row.anomaly_type,
                   "severity": row.severity, "correlated": row.correlated,
                   "at": str(row.created_at)} for row in r.fetchall()]  # LIMIT applied
        corr = await db.execute(text("SELECT pattern, combined_severity, narrative, created_at FROM anomaly_correlations ORDER BY created_at DESC LIMIT 5"))
        correlations = [{"pattern": row.pattern, "severity": row.combined_severity,
                        "narrative": (row.narrative or "")[:200], "at": str(row.created_at)}
                       for row in corr.fetchall()]  # LIMIT applied
        widgets["threat_correlation"] = {"events": events, "correlations": correlations}
    except Exception as e:
        widgets["threat_correlation"] = {"events": [], "correlations": []}

    # Widget 8: Prospect Pipeline
    try:
        r = await db.execute(text(
            "SELECT signal, signal_source, qualification_score, outreach_draft, status "
            "FROM operator_prospects ORDER BY identified_at DESC LIMIT 10"
        ))
        prospects = [{"signal": (row.signal or "")[:100], "source": row.signal_source,
                     "score": row.qualification_score, "status": row.status,
                     "draft": (row.outreach_draft or "")[:150]} for row in r.fetchall()]  # LIMIT applied
        widgets["prospect_pipeline"] = prospects
    except Exception as e:
        widgets["prospect_pipeline"] = []

    return widgets

@router.post("/api/v1/owner/schedule", include_in_schema=False)
async def api_nl_schedule(request: Request, db: AsyncSession = Depends(get_db)):
    body = await validated_json(request)
    from app.arch.nl_scheduler import create_nl_job
    return await create_nl_job(db, body.get("instruction", ""), body.get("task", ""))

@router.get("/api/v1/owner/search", include_in_schema=False)
async def api_search_conversations(request: Request, db: AsyncSession = Depends(get_db)):
    params = dict(request.query_params)
    from app.arch.conversation_search import search_conversations
    results = await search_conversations(db, params.get("q", ""), params.get("agent_id"), int(params.get("limit", "20")))
    return {"query": params.get("q"), "results": results, "count": len(results)}

@router.get("/api/v1/owner/server-metrics", include_in_schema=False)
async def api_server_metrics():
    """Real-time server metrics: CPU, RAM, disk, network, PostgreSQL, Redis, backups."""
    from app.arch.server_monitor import get_system_metrics
    return await get_system_metrics()

@router.get("/api/v1/owner/evaluations", include_in_schema=False)
async def api_list_evaluations(db: AsyncSession = Depends(get_db)):
    """Get latest evaluation scores for all agents."""
    from app.arch.agent_evaluator import get_latest_evaluations
    evals = await get_latest_evaluations(db)
    return {"evaluations": evals, "count": len(evals), "framework": "v5.1"}

@router.post("/api/v1/owner/evaluations/run", include_in_schema=False)
async def api_run_evaluation(db: AsyncSession = Depends(get_db)):
    """Run full evaluation for all 7 Arch Agents now."""
    from app.arch.agent_evaluator import evaluate_all_agents
    return await evaluate_all_agents(db)

@router.get("/api/v1/owner/evaluations/{agent_id}", include_in_schema=False)
async def api_agent_evaluation(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed evaluation for a specific agent."""
    from app.arch.agent_evaluator import evaluate_agent
    return await evaluate_agent(db, agent_id)

@router.get("/api/v1/owner/social-activity", include_in_schema=False)
async def api_social_activity(db: AsyncSession = Depends(get_db)):
    """All published content, comments, and engagement across all platforms."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT content_type, title, body_ref, channel, published_at "
        "FROM arch_content_library ORDER BY published_at DESC LIMIT 50"
    ))
    items = []
    for row in r.fetchall():  # LIMIT applied
        # Extract proof URL from body_ref if it's JSON
        proof_url = ""
        try:
            import json
            if row.body_ref and row.body_ref.startswith("{"):
                data = json.loads(row.body_ref)
                proof_url = data.get("url", "")
        except Exception as exc:
            import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

        items.append({
            "type": row.content_type,
            "title": row.title[:100] if row.title else "",
            "channel": row.channel,
            "proof_url": proof_url,
            "published": str(row.published_at)[:19] if row.published_at else "",
        })

    # Group by channel
    by_channel = {}
    for item in items:
        ch = item["channel"]
        if ch not in by_channel:
            by_channel[ch] = 0
        by_channel[ch] += 1

    return {"items": items, "total": len(items), "by_channel": by_channel}

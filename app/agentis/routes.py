"""Agentis Cooperative Bank — API Routes.

All endpoints under /api/v1/agentis/ namespace. Feature-flagged.
JWT auth with mandate enforcement for agent actions.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.db import get_db

router = APIRouter(prefix="/api/v1/agentis", tags=["Agentis Banking"])

# Service instances — set from main.py
compliance_service = None
member_service = None
account_service = None
payment_service = None


# ── Helpers ──────────────────────────────────────────────────────────

def _check_compliance_enabled():
    if not settings.agentis_compliance_enabled:
        raise HTTPException(status_code=503,
                            detail={"error_code": "FEATURE_NOT_ENABLED",
                                    "message": "Agentis Compliance Engine is not yet enabled"})


def _check_members_enabled():
    _check_compliance_enabled()
    if not settings.agentis_cfi_member_enabled:
        raise HTTPException(status_code=503,
                            detail={"error_code": "FEATURE_NOT_ENABLED",
                                    "message": "Agentis Member module is not yet enabled"})


def _check_accounts_enabled():
    _check_members_enabled()
    if not settings.agentis_cfi_accounts_enabled:
        raise HTTPException(status_code=503,
                            detail={"error_code": "FEATURE_NOT_ENABLED",
                                    "message": "Agentis Accounts module is not yet enabled"})


def _check_payments_enabled():
    _check_accounts_enabled()
    if not settings.agentis_cfi_payments_enabled:
        raise HTTPException(status_code=503,
                            detail={"error_code": "FEATURE_NOT_ENABLED",
                                    "message": "Agentis Payments module is not yet enabled"})


# ── Request / Response Models ────────────────────────────────────────

class MemberOnboardRequest(BaseModel):
    operator_id: str
    member_type: str = "OPERATOR_ENTITY"


class KycSubmitRequest(BaseModel):
    kyc_level: str
    id_document_type: Optional[str] = None
    id_document_number: Optional[str] = None
    id_document_verified_by: Optional[str] = None
    id_verification_ref: Optional[str] = None
    address_verified: bool = False
    source_of_funds_declared: Optional[str] = None


class MandateGrantRequest(BaseModel):
    agent_id: str
    mandate_level: str
    operator_3fa_ref: str
    daily_payment_limit: float = 0
    per_transaction_limit: float = 0
    monthly_limit: float = 0
    loan_application_enabled: bool = False
    investment_enabled: bool = False
    fx_enabled: bool = False
    beneficiary_add_enabled: bool = False
    third_party_payments_enabled: bool = False
    confirmation_threshold: float = 0
    allowed_currencies: Optional[list[str]] = None
    purpose_restriction: Optional[str] = None
    valid_until: Optional[str] = None


class OpenAccountRequest(BaseModel):
    account_type: str
    currency: str = "ZAR"
    initial_deposit: float = 0
    agent_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class DepositRequest(BaseModel):
    amount: float
    reference: str
    description: Optional[str] = None
    currency: str = "ZAR"
    agent_id: Optional[str] = None
    mandate_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class WithdrawRequest(BaseModel):
    amount: float
    reference: str
    description: Optional[str] = None
    currency: str = "ZAR"
    agent_id: Optional[str] = None
    mandate_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class PaymentInitiateRequest(BaseModel):
    source_account_id: str
    amount: float
    currency: str = "ZAR"
    reference: str
    description: Optional[str] = None
    destination_account_id: Optional[str] = None
    beneficiary_id: Optional[str] = None
    agent_id: Optional[str] = None
    mandate_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class PaymentConfirmRequest(BaseModel):
    three_fa_ref: str


class AddBeneficiaryRequest(BaseModel):
    beneficiary_type: str
    display_name: str
    operator_3fa_ref: Optional[str] = None
    agentis_member_id: Optional[str] = None
    agentis_account_id: Optional[str] = None
    account_number: Optional[str] = None
    bank_code: Optional[str] = None
    branch_code: Optional[str] = None
    crypto_address: Optional[str] = None
    crypto_network: Optional[str] = None


class StandingOrderRequest(BaseModel):
    account_id: str
    beneficiary_id: str
    amount: float
    frequency: str
    start_date: str
    reference: str
    day_of_month: Optional[int] = None
    day_of_week: Optional[int] = None
    end_date: Optional[str] = None
    agent_id: Optional[str] = None
    mandate_id: Optional[str] = None
    operator_3fa_ref: Optional[str] = None


class PopiaRequest(BaseModel):
    request_type: str
    description: Optional[str] = None


class FeatureFlagRequest(BaseModel):
    flag_name: str
    enabled_by: str
    three_fa_ref: str


# ══════════════════════════════════════════════════════════════════════
# MEMBER ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@router.post("/members")
async def onboard_member(req: MemberOnboardRequest, db: AsyncSession = Depends(get_db)):
    """Onboard a new cooperative bank member."""
    _check_members_enabled()
    result = await member_service.onboard_member(
        db, operator_id=req.operator_id, member_type=req.member_type)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/members/{member_id}")
async def get_member(member_id: str, db: AsyncSession = Depends(get_db)):
    """Get member profile."""
    _check_members_enabled()
    member = await member_service.get_member(db, member_id)
    if not member:
        raise HTTPException(status_code=404, detail={"error_code": "MEMBER_NOT_FOUND"})
    return {
        "member_id": member.member_id,
        "member_number": member.member_number,
        "member_type": member.member_type,
        "membership_status": member.membership_status,
        "kyc_level": member.kyc_level,
        "fica_risk_rating": member.fica_risk_rating,
        "share_capital_balance": member.share_capital_balance,
        "total_deposits": member.total_deposits,
        "joined_at": member.joined_at.isoformat(),
    }


@router.get("/members/{member_id}/kyc-status")
async def get_kyc_status(member_id: str, db: AsyncSession = Depends(get_db)):
    """Current KYC/AML status and requirements."""
    _check_members_enabled()
    result = await member_service.get_kyc_status(db, member_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result)
    return result


@router.post("/members/{member_id}/kyc")
async def submit_kyc(member_id: str, req: KycSubmitRequest,
                     db: AsyncSession = Depends(get_db)):
    """Submit KYC verification documents."""
    _check_members_enabled()
    result = await member_service.submit_kyc(
        db, member_id=member_id, kyc_level=req.kyc_level,
        id_document_type=req.id_document_type,
        id_document_number=req.id_document_number,
        id_document_verified_by=req.id_document_verified_by,
        id_verification_ref=req.id_verification_ref,
        address_verified=req.address_verified,
        source_of_funds_declared=req.source_of_funds_declared,
    )
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/members/{member_id}/activate")
async def activate_member(member_id: str, db: AsyncSession = Depends(get_db)):
    """Activate member after KYC completion."""
    _check_members_enabled()
    result = await member_service.activate_member(db, member_id)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/members/{member_id}/mandates")
async def list_mandates(member_id: str, db: AsyncSession = Depends(get_db)):
    """List all agent banking mandates."""
    _check_members_enabled()
    return await member_service.list_mandates(db, member_id)


@router.post("/members/{member_id}/mandates")
async def grant_mandate(member_id: str, req: MandateGrantRequest,
                        db: AsyncSession = Depends(get_db)):
    """Grant a new agent banking mandate."""
    _check_members_enabled()
    valid_until = None
    if req.valid_until:
        valid_until = datetime.fromisoformat(req.valid_until)
    result = await member_service.grant_mandate(
        db, member_id=member_id, agent_id=req.agent_id,
        mandate_level=req.mandate_level, operator_3fa_ref=req.operator_3fa_ref,
        daily_payment_limit=req.daily_payment_limit,
        per_transaction_limit=req.per_transaction_limit,
        monthly_limit=req.monthly_limit,
        loan_application_enabled=req.loan_application_enabled,
        investment_enabled=req.investment_enabled,
        fx_enabled=req.fx_enabled,
        beneficiary_add_enabled=req.beneficiary_add_enabled,
        third_party_payments_enabled=req.third_party_payments_enabled,
        confirmation_threshold=req.confirmation_threshold,
        allowed_currencies=req.allowed_currencies,
        purpose_restriction=req.purpose_restriction,
        valid_until=valid_until,
    )
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.delete("/members/{member_id}/mandates/{mandate_id}")
async def revoke_mandate(member_id: str, mandate_id: str,
                         db: AsyncSession = Depends(get_db)):
    """Revoke an agent banking mandate."""
    _check_members_enabled()
    member = await member_service.get_member(db, member_id)
    if not member:
        raise HTTPException(status_code=404, detail={"error_code": "MEMBER_NOT_FOUND"})
    result = await member_service.revoke_mandate(db, mandate_id, member.operator_id)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/members/{member_id}/popia-export")
async def popia_export(member_id: str, req: PopiaRequest,
                       db: AsyncSession = Depends(get_db)):
    """Request POPIA data export or erasure."""
    _check_compliance_enabled()
    result = await compliance_service.create_popia_request(
        db, member_id=member_id, request_type=req.request_type,
        description=req.description,
    )
    return {
        "request_id": result.request_id,
        "status": result.status,
        "deadline_at": result.deadline_at.isoformat() if result.deadline_at else None,
    }


# ══════════════════════════════════════════════════════════════════════
# ACCOUNT ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@router.post("/accounts")
async def open_account(req: OpenAccountRequest, member_id: str = Query(...),
                       db: AsyncSession = Depends(get_db)):
    """Open a new member bank account."""
    _check_accounts_enabled()
    result = await account_service.open_account(
        db, member_id=member_id, account_type=req.account_type,
        currency=req.currency, initial_deposit=req.initial_deposit,
        agent_id=req.agent_id, idempotency_key=req.idempotency_key,
    )
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/accounts")
async def list_accounts(member_id: str = Query(...),
                        db: AsyncSession = Depends(get_db)):
    """List all accounts for a member."""
    _check_accounts_enabled()
    return await account_service.list_accounts(db, member_id)


@router.get("/accounts/{account_id}")
async def get_account(account_id: str, db: AsyncSession = Depends(get_db)):
    """Account detail and current balance."""
    _check_accounts_enabled()
    account = await account_service.get_account(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail={"error_code": "ACCOUNT_NOT_FOUND"})
    from app.agentis.account_service import ACCOUNT_PRODUCTS
    product = ACCOUNT_PRODUCTS.get(account.account_type, {})
    return {
        "account_id": account.account_id,
        "account_number": account.account_number,
        "account_type": account.account_type,
        "product_name": product.get("name", "Unknown"),
        "currency": account.currency,
        "balance": account.balance,
        "pending_balance": account.pending_balance,
        "interest_accrued": account.interest_accrued,
        "interest_rate_pa": account.interest_rate_pa,
        "status": account.status,
        "is_frozen": account.is_frozen,
        "opened_at": account.opened_at.isoformat(),
    }


@router.post("/accounts/{account_id}/deposit")
async def deposit(account_id: str, req: DepositRequest,
                  db: AsyncSession = Depends(get_db)):
    """Record a deposit."""
    _check_accounts_enabled()
    result = await account_service.deposit(
        db, account_id=account_id, amount=req.amount,
        currency=req.currency, reference=req.reference,
        description=req.description, agent_id=req.agent_id,
        mandate_id=req.mandate_id, idempotency_key=req.idempotency_key,
    )
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/accounts/{account_id}/withdraw")
async def withdraw(account_id: str, req: WithdrawRequest,
                   db: AsyncSession = Depends(get_db)):
    """Process a withdrawal."""
    _check_accounts_enabled()
    result = await account_service.withdraw(
        db, account_id=account_id, amount=req.amount,
        currency=req.currency, reference=req.reference,
        description=req.description, agent_id=req.agent_id,
        mandate_id=req.mandate_id, idempotency_key=req.idempotency_key,
    )
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/accounts/{account_id}/transactions")
async def get_transactions(
    account_id: str,
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    txn_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Transaction history with filters."""
    _check_accounts_enabled()
    return await account_service.get_transactions(
        db, account_id=account_id, limit=limit, offset=offset, txn_type=txn_type,
    )


@router.get("/accounts/{account_id}/statement")
async def get_statement(
    account_id: str,
    from_date: str = Query(...),
    to_date: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Formatted account statement."""
    _check_accounts_enabled()
    result = await account_service.get_account_statement(
        db, account_id=account_id,
        from_date=datetime.fromisoformat(from_date),
        to_date=datetime.fromisoformat(to_date),
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result)
    return result


# ══════════════════════════════════════════════════════════════════════
# PAYMENT ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@router.post("/payments/initiate")
async def initiate_payment(req: PaymentInitiateRequest, member_id: str = Query(...),
                           db: AsyncSession = Depends(get_db)):
    """Initiate a payment (internal or external)."""
    _check_payments_enabled()
    result = await payment_service.initiate_payment(
        db, source_account_id=req.source_account_id,
        member_id=member_id, amount=req.amount,
        currency=req.currency, reference=req.reference,
        description=req.description,
        destination_account_id=req.destination_account_id,
        beneficiary_id=req.beneficiary_id,
        agent_id=req.agent_id, mandate_id=req.mandate_id,
        idempotency_key=req.idempotency_key,
    )
    if "error" in result:
        status_code = 403 if "MANDATE" in result.get("error_code", "") else 422
        raise HTTPException(status_code=status_code, detail=result)
    return result


@router.get("/payments/{payment_id}")
async def get_payment(payment_id: str, db: AsyncSession = Depends(get_db)):
    """Payment status and detail."""
    _check_payments_enabled()
    result = await payment_service.get_payment(db, payment_id)
    if not result:
        raise HTTPException(status_code=404, detail={"error_code": "PAYMENT_NOT_FOUND"})
    return result


@router.post("/payments/{payment_id}/confirm")
async def confirm_payment(payment_id: str, req: PaymentConfirmRequest,
                          db: AsyncSession = Depends(get_db)):
    """Operator confirms pending high-value payment."""
    _check_payments_enabled()
    result = await payment_service.confirm_payment(
        db, payment_id=payment_id, three_fa_ref=req.three_fa_ref)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/payments/{payment_id}/cancel")
async def cancel_payment(payment_id: str, db: AsyncSession = Depends(get_db)):
    """Cancel a pending payment."""
    _check_payments_enabled()
    result = await payment_service.cancel_payment(db, payment_id)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/payments/history")
async def payment_history(
    member_id: str = Query(...),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Payment history with filters."""
    _check_payments_enabled()
    return await payment_service.get_payment_history(
        db, member_id=member_id, limit=limit, offset=offset, status=status)


@router.post("/beneficiaries")
async def add_beneficiary(req: AddBeneficiaryRequest, member_id: str = Query(...),
                          db: AsyncSession = Depends(get_db)):
    """Add a payment beneficiary."""
    _check_payments_enabled()
    result = await payment_service.add_beneficiary(
        db, member_id=member_id, beneficiary_type=req.beneficiary_type,
        display_name=req.display_name, operator_3fa_ref=req.operator_3fa_ref,
        agentis_member_id=req.agentis_member_id,
        agentis_account_id=req.agentis_account_id,
        account_number=req.account_number, bank_code=req.bank_code,
        branch_code=req.branch_code, crypto_address=req.crypto_address,
        crypto_network=req.crypto_network,
    )
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/beneficiaries")
async def list_beneficiaries(member_id: str = Query(...),
                             db: AsyncSession = Depends(get_db)):
    """List approved beneficiaries."""
    _check_payments_enabled()
    return await payment_service.list_beneficiaries(db, member_id)


@router.post("/standing-orders")
async def create_standing_order(req: StandingOrderRequest,
                                member_id: str = Query(...),
                                db: AsyncSession = Depends(get_db)):
    """Create a recurring payment instruction."""
    _check_payments_enabled()
    from datetime import date as date_cls
    result = await payment_service.create_standing_order(
        db, account_id=req.account_id, member_id=member_id,
        beneficiary_id=req.beneficiary_id, amount=req.amount,
        frequency=req.frequency,
        start_date=date_cls.fromisoformat(req.start_date),
        reference=req.reference, agent_id=req.agent_id,
        mandate_id=req.mandate_id, operator_3fa_ref=req.operator_3fa_ref,
        day_of_month=req.day_of_month, day_of_week=req.day_of_week,
        end_date=date_cls.fromisoformat(req.end_date) if req.end_date else None,
    )
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/standing-orders")
async def list_standing_orders(member_id: str = Query(...),
                               db: AsyncSession = Depends(get_db)):
    """List standing orders."""
    _check_payments_enabled()
    return await payment_service.list_standing_orders(db, member_id)


# ══════════════════════════════════════════════════════════════════════
# COMPLIANCE & REPORTING ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@router.get("/compliance/fica-status/{member_id}")
async def fica_status(member_id: str, db: AsyncSession = Depends(get_db)):
    """Member FICA compliance status."""
    _check_compliance_enabled()
    kyc_status = await member_service.get_kyc_status(db, member_id)
    return kyc_status


@router.get("/compliance/ctr-log")
async def ctr_log(status: Optional[str] = None, limit: int = Query(50, le=200),
                  db: AsyncSession = Depends(get_db)):
    """Currency Transaction Report log."""
    _check_compliance_enabled()
    return await compliance_service.get_ctr_reports(db, status=status, limit=limit)


@router.get("/compliance/str-log")
async def str_log(status: Optional[str] = None, limit: int = Query(50, le=200),
                  db: AsyncSession = Depends(get_db)):
    """Suspicious Transaction Report log."""
    _check_compliance_enabled()
    return await compliance_service.get_str_reports(db, status=status, limit=limit)


@router.get("/compliance/sanctions-alerts")
async def sanctions_alerts(limit: int = Query(50, le=200),
                           db: AsyncSession = Depends(get_db)):
    """Current sanctions screening alerts."""
    _check_compliance_enabled()
    return await compliance_service.get_sanctions_alerts(db, limit=limit)


@router.get("/compliance/feature-flags")
async def feature_flags(db: AsyncSession = Depends(get_db)):
    """Get all Agentis feature flags and their state."""
    _check_compliance_enabled()
    return await compliance_service.get_feature_flags(db)


@router.post("/compliance/feature-flags/enable")
async def enable_feature_flag(req: FeatureFlagRequest,
                              db: AsyncSession = Depends(get_db)):
    """Enable a feature flag (Owner 3FA required)."""
    _check_compliance_enabled()
    result = await compliance_service.enable_flag(
        db, flag_name=req.flag_name, enabled_by=req.enabled_by,
        three_fa_ref=req.three_fa_ref)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/compliance/pending-reviews")
async def pending_reviews(limit: int = Query(50, le=200),
                          db: AsyncSession = Depends(get_db)):
    """Get monitoring events requiring compliance officer review."""
    _check_compliance_enabled()
    events = await compliance_service.get_pending_reviews(db, limit=limit)
    return [
        {
            "event_id": e.event_id,
            "event_type": e.event_type,
            "severity": e.severity,
            "description": e.description,
            "amount_zar": e.amount_zar,
            "member_id": e.member_id,
            "agent_id": e.agent_id,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


# ══════════════════════════════════════════════════════════════════════
# REGULATORY ENGAGEMENT TIMELINE (Enhancement #5)
# ══════════════════════════════════════════════════════════════════════

@router.get("/regulatory/timeline")
async def regulatory_timeline():
    """Regulatory engagement milestones and status."""
    return {
        "milestones": [
            {"step": 1, "name": "CIPC Cooperative Registration",
             "description": "Register Agentis Co-operative Bank with CIPC",
             "status": "pending", "prerequisite_for": "CBDA CFI Application",
             "estimated_duration": "2-4 weeks"},
            {"step": 2, "name": "CBDA Pre-Application Consultation",
             "description": "Engage CBDA to understand CFI requirements and present concept",
             "status": "pending", "prerequisite_for": "CFI Application",
             "estimated_duration": "1-2 months"},
            {"step": 3, "name": "CFI Application to CBDA",
             "description": "Submit Cooperative Financial Institution application",
             "status": "pending", "prerequisite_for": "CFI Registration",
             "estimated_duration": "3-6 months",
             "enables_flags": ["AGENTIS_CFI_MEMBER_ENABLED", "AGENTIS_CFI_ACCOUNTS_ENABLED",
                               "AGENTIS_CFI_PAYMENTS_ENABLED"]},
            {"step": 4, "name": "NCR Credit Provider Registration",
             "description": "Register as credit provider with National Credit Regulator",
             "status": "pending", "prerequisite_for": "Lending Products",
             "estimated_duration": "2-4 months",
             "enables_flags": ["AGENTIS_CFI_LENDING_ENABLED"]},
            {"step": 5, "name": "SARB Prudential Authority Engagement",
             "description": "Apply for Primary Co-operative Bank registration",
             "status": "pending", "prerequisite_for": "Full Banking",
             "estimated_duration": "12-24 months",
             "enables_flags": ["AGENTIS_PCB_DEPOSITS_ENABLED", "AGENTIS_PCB_EFT_ENABLED"]},
            {"step": 6, "name": "FSCA FSP Category I Application",
             "description": "Apply for Financial Services Provider licence",
             "status": "pending", "prerequisite_for": "Intermediary Services",
             "estimated_duration": "3-6 months",
             "enables_flags": ["AGENTIS_FSP_INTERMEDIARY_ENABLED"]},
            {"step": 7, "name": "SARB IFLAB Innovation Hub Application",
             "description": "Apply to SARB regulatory sandbox for AI agent banking concept",
             "status": "pending", "prerequisite_for": "Regulatory Guidance",
             "estimated_duration": "1-3 months"},
            {"step": 8, "name": "FSCA CASP Application",
             "description": "Apply for Crypto Asset Service Provider licence",
             "status": "pending", "prerequisite_for": "Crypto Banking",
             "estimated_duration": "6-12 months",
             "enables_flags": ["AGENTIS_CASP_ENABLED"]},
        ],
        "common_bond_definition": (
            "Members of the TiOLi AI platform who operate registered AI agents "
            "for commercial purposes"
        ),
    }

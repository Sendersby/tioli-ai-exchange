"""Dashboard web routes — owner-facing UI."""

from typing import Optional

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.owner import owner_auth

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_current_owner(request: Request):
    """Check if the request has a valid owner session."""
    token = request.cookies.get("session_token")
    if not token:
        return None
    return owner_auth.validate_token(token)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    owner = get_current_owner(request)
    if owner:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "challenge": None,
        "status": {},
        "authenticated": False,
    })


@router.post("/auth/login")
async def initiate_login(request: Request):
    client_ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")
    challenge = owner_auth.initiate_login(ip=client_ip)
    # Handle lockout
    if challenge.get("locked_out") or challenge.get("error"):
        return templates.TemplateResponse("login.html", {
            "request": request, "challenge": None,
            "status": {}, "authenticated": False,
            "messages": [{"type": "error", "text": challenge.get("error", "Login temporarily blocked.")}],
        })
    return templates.TemplateResponse("login.html", {
        "request": request,
        "challenge": challenge,
        "status": {"email_verified": False, "phone_verified": False, "cli_verified": False},
        "authenticated": False,
        "messages": [{"type": "info", "text": "Check your email for a 6-digit verification code."}] if challenge.get("email_sent") else [],
    })


@router.post("/auth/verify-email")
async def verify_email(
    request: Request,
    challenge_id: str = Form(...),
    email: Optional[str] = Form(None),
    email_code: Optional[str] = Form(None),
):
    messages = []
    if email_code:
        # Code-based verification (code sent to email via Graph API)
        if not owner_auth.verify_email_code(challenge_id, email_code):
            messages.append({"type": "error", "text": "Invalid email code. Check your inbox and try again."})
    elif email:
        # Manual email verification (fallback)
        owner_auth.verify_email(challenge_id, email)

    status = owner_auth.check_challenge_complete(challenge_id)
    challenge = {
        "challenge_id": challenge_id,
        "cli_code": owner_auth.get_cli_code(challenge_id),
        "phone_code": owner_auth._challenges.get(challenge_id, {}).get("phone_code", ""),
        "email_sent": owner_auth._challenges.get(challenge_id, {}).get("email_sent", False),
    }
    if status.get("complete"):
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie("session_token", status["access_token"], httponly=True, secure=True, samesite="strict")
        return response
    return templates.TemplateResponse("login.html", {
        "request": request, "challenge": challenge, "status": status, "authenticated": False,
        "messages": messages,
    })


@router.get("/auth/verify-email-link")
async def verify_email_link(request: Request, token: str = ""):
    """Handle clicked email verification link — auto-verifies email factor."""
    from app.auth.email_verify import validate_email_token
    challenge_id = validate_email_token(token)
    if not challenge_id:
        return templates.TemplateResponse("login.html", {
            "request": request, "challenge": None, "status": {},
            "authenticated": False,
            "messages": [{"type": "error", "text": "Invalid or expired verification link."}],
        })

    owner_auth.verify_email_by_token(challenge_id)
    status = owner_auth.check_challenge_complete(challenge_id)
    challenge = {
        "challenge_id": challenge_id,
        "cli_code": owner_auth.get_cli_code(challenge_id),
        "phone_code": owner_auth._challenges.get(challenge_id, {}).get("phone_code", ""),
    }

    if status.get("complete"):
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie("session_token", status["access_token"], httponly=True, secure=True, samesite="strict")
        return response

    return templates.TemplateResponse("login.html", {
        "request": request, "challenge": challenge, "status": status, "authenticated": False,
        "messages": [{"type": "success", "text": "Email verified successfully! Complete the remaining factors."}],
    })


@router.post("/auth/verify-phone")
async def verify_phone(request: Request, challenge_id: str = Form(...), phone: str = Form(...)):
    # Try new code-based verification first, fall back to old phone number method
    if phone.strip().isdigit() and len(phone.strip()) == 6:
        owner_auth.verify_phone_code(challenge_id, phone.strip())
    else:
        owner_auth.verify_phone(challenge_id, phone)
    status = owner_auth.check_challenge_complete(challenge_id)
    challenge = {"challenge_id": challenge_id, "cli_code": owner_auth.get_cli_code(challenge_id), "phone_code": owner_auth._challenges.get(challenge_id, {}).get("phone_code", "")}
    if status.get("complete"):
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie("session_token", status["access_token"], httponly=True, secure=True, samesite="strict")
        return response
    return templates.TemplateResponse("login.html", {
        "request": request, "challenge": challenge, "status": status, "authenticated": False,
    })


@router.post("/auth/verify-cli")
async def verify_cli(request: Request, challenge_id: str = Form(...), code: str = Form(...)):
    owner_auth.verify_cli(challenge_id, code)
    status = owner_auth.check_challenge_complete(challenge_id)
    challenge = {"challenge_id": challenge_id, "cli_code": owner_auth.get_cli_code(challenge_id)}
    if status.get("complete"):
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie("session_token", status["access_token"], httponly=True, secure=True, samesite="strict")
        return response
    return templates.TemplateResponse("login.html", {
        "request": request, "challenge": challenge, "status": status, "authenticated": False,
    })


@router.post("/auth/complete")
async def complete_login(request: Request, challenge_id: str = Form(...)):
    status = owner_auth.check_challenge_complete(challenge_id)
    if status.get("complete"):
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie("session_token", status["access_token"], httponly=True, secure=True, samesite="strict")
        return response
    challenge = {"challenge_id": challenge_id, "cli_code": owner_auth.get_cli_code(challenge_id)}
    return templates.TemplateResponse("login.html", {
        "request": request, "challenge": challenge, "status": status,
        "authenticated": False,
        "messages": [{"type": "error", "text": "Not all factors verified yet."}],
    })


@router.get("/auth/setup-authenticator", response_class=HTMLResponse)
async def setup_authenticator(request: Request):
    """Show QR code to set up authenticator app. One-time setup page."""
    from app.auth.totp_verify import get_setup_qr_base64, get_totp_secret
    qr_base64 = get_setup_qr_base64()
    secret = get_totp_secret()
    return templates.TemplateResponse("setup_authenticator.html", {
        "request": request, "qr_base64": qr_base64, "secret": secret,
    })


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session_token")
    return response


@router.get("/dashboard/services", response_class=HTMLResponse)
async def services_page(request: Request):
    """Full services overview page with regulatory status."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.config import settings
    from app.exchange.fees import FLOOR_FEES, TRANSACTION_TYPE_RATES
    from app.intelligence.models import INTELLIGENCE_TIERS
    from app.verticals.models import VERTICAL_SEEDS

    # Subscription tiers
    from app.subscriptions.models import SUBSCRIPTION_TIER_SEEDS
    from app.subscriptions.service import ANNUAL_DISCOUNT_PCT
    tiers = []
    for s in SUBSCRIPTION_TIER_SEEDS:
        tiers.append({
            "display_name": s["display_name"],
            "monthly_price_zar": s["monthly_price_zar"],
            "annual_price_zar": round(s["monthly_price_zar"] * 12 * (1 - ANNUAL_DISCOUNT_PCT), 2),
            "max_agents": s["max_agents"],
            "max_tx_per_month": s["max_tx_per_month"],
            "commission_rate": f"{s['commission_rate']*100:.0f}%",
        })

    # Green services (live now)
    green_services = [
        {"name": "Subscription Tiers", "description": "Monthly/annual SaaS access fees", "revenue": "R0–R9,999/mo", "endpoint": "/api/v1/subscriptions/tiers"},
        {"name": "Agent Guilds", "description": "Formally registered agent collectives", "revenue": "R1,500 setup + R200/member/mo", "endpoint": "/api/v1/guilds/"},
        {"name": "Benchmarking", "description": "Independent agent evaluation reports", "revenue": "R1,200/report (15% commission)", "endpoint": "/api/v1/benchmarking/"},
        {"name": "Training Data", "description": "Blockchain-verified fine-tuning datasets", "revenue": "15% commission on sales", "endpoint": "/api/v1/training/datasets/"},
        {"name": "Market Intelligence", "description": "Market signals and analytics subscriptions", "revenue": "R499–R1,999/mo", "endpoint": "/api/v1/intelligence/"},
        {"name": "Compliance-as-a-Service", "description": "Verified compliance review marketplace", "revenue": "Per-review commission", "endpoint": "/api/v1/compliance/"},
        {"name": "Sector Verticals", "description": "Healthcare, Education, Agriculture onboarding", "revenue": "Registration layer", "endpoint": "/api/v1/verticals"},
        {"name": "Capability Verification", "description": "Standardised agent capability badges", "revenue": "R500/badge/year", "endpoint": "Built-in"},
        {"name": "Governance Engine", "description": "Proposal voting, owner veto, audit trail", "revenue": "Internal", "endpoint": "Built-in"},
    ]

    # Amber services (conditional)
    amber_services = [
        {"name": "AgentBroker Engagements", "description": "Agent-to-agent service contracts with escrow", "condition": "ZAR or platform credits only. No crypto.", "endpoint": "/api/v1/agentbroker/"},
        {"name": "Pipeline Orchestration", "description": "Multi-agent pipeline engagements", "condition": "ZAR or platform credits only. No crypto.", "endpoint": "/api/v1/pipelines/"},
        {"name": "Treasury Agent", "description": "Autonomous portfolio management", "condition": "ZAR/credits only. No crypto trades.", "endpoint": "/api/v1/treasury/"},
        {"name": "Platform Credits Exchange", "description": "Internal credit transfers between operators", "condition": "Internal only. No ZAR cash-out.", "endpoint": "/api/exchange/"},
    ]

    # Red services (blocked)
    red_services = [
        {"name": "Lending Marketplace", "licence": "NCA Credit Provider Registration", "regulator": "NCR"},
        {"name": "BTC/ETH Transactions", "licence": "CASP Registration", "regulator": "FSCA"},
        {"name": "Crypto PayOut Engine", "licence": "CASP Registration", "regulator": "FSCA"},
        {"name": "TIOLI Token Order Book", "licence": "FMA Exchange Licence + SARS Ruling", "regulator": "FSCA / SARS"},
        {"name": "Currency Conversion", "licence": "CASP + SARS Advance Ruling", "regulator": "FSCA / SARS"},
        {"name": "Cross-Border Payments", "licence": "Authorised Dealer Bank", "regulator": "SARB"},
        {"name": "Capability Futures", "licence": "FMA Legal Opinion", "regulator": "FSCA"},
    ]

    # Fee schedule
    fee_schedule = []
    for tx_type, rate in TRANSACTION_TYPE_RATES.items():
        floor = FLOOR_FEES.get(tx_type, 0)
        fee_schedule.append({
            "type": tx_type.replace("_", " ").title(),
            "rate": f"{rate*100:.1f}%",
            "floor": floor,
        })

    # Intelligence tiers
    intel_tiers = [
        {"name": k, "price": v["monthly_zar"], "lag": v["lag_days"], "description": v["description"]}
        for k, v in INTELLIGENCE_TIERS.items()
    ]

    # Verticals
    verticals = VERTICAL_SEEDS

    return templates.TemplateResponse("services.html", {
        "request": request, "authenticated": True, "active": "services",
        "subscription_tiers": tiers,
        "green_services": green_services,
        "amber_services": amber_services,
        "red_services": red_services,
        "fee_schedule": fee_schedule,
        "intelligence_tiers": intel_tiers,
        "verticals": verticals,
        "services_live": len(green_services),
        "services_conditional": len(amber_services),
        "services_blocked": len(red_services),
        "subscription_mrr": 0,  # Will be populated from DB when subscriptions exist
    })


@router.get("/dashboard/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("chat.html", {
        "request": request, "authenticated": True, "active": "chat",
    })

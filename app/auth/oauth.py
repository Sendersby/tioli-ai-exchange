"""OAuth authentication — GitHub and Google instant signup for operators.

Flow: Click OAuth button → redirect to provider → callback → create/find
Operator + OperatorHubProfile → set JWT session cookie → redirect to profile.
"""

import uuid
import jwt
import httpx
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.config import Settings
from app.database.db import async_session
from app.operators.models import Operator
from app.operator_hub.models import OperatorHubProfile

router = APIRouter(tags=["oauth"])
settings = Settings()

SESSION_COOKIE = "operator_session"
SESSION_EXPIRY_DAYS = 30


def _create_session_token(operator_id: str) -> str:
    """Create a signed JWT session token for an operator."""
    payload = {
        "operator_id": operator_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_operator_session(token: str) -> dict | None:
    """Decode and verify an operator session token."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def _set_session_cookie(response: RedirectResponse, operator_id: str) -> RedirectResponse:
    """Set the session cookie on a redirect response."""
    token = _create_session_token(operator_id)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_EXPIRY_DAYS * 86400,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


async def _find_or_create_operator(
    provider: str, provider_id: str, name: str, email: str,
    avatar_url: str = None, github_login: str = None,
) -> str:
    """Find existing operator by OAuth ID or create new one. Returns operator_id."""
    async with async_session() as db:
        # Check if operator exists by OAuth provider ID
        result = await db.execute(
            select(Operator).where(
                Operator.oauth_provider == provider,
                Operator.oauth_provider_id == str(provider_id),
            )
        )
        operator = result.scalar_one_or_none()

        if operator:
            # Update avatar/name on each login
            if avatar_url:
                operator.avatar_url = avatar_url
            operator.updated_at = datetime.now(timezone.utc)
            await db.commit()
            return operator.id

        # Check if operator exists by email (link OAuth to existing account)
        if email:
            result = await db.execute(
                select(Operator).where(Operator.email == email)
            )
            operator = result.scalar_one_or_none()
            if operator:
                operator.oauth_provider = provider
                operator.oauth_provider_id = str(provider_id)
                operator.avatar_url = avatar_url
                if github_login:
                    operator.github_login = github_login
                await db.commit()

                # Ensure profile exists
                await _ensure_profile(db, operator.id, name, avatar_url, github_login)
                return operator.id

        # Create new operator
        operator_id = str(uuid.uuid4())
        operator = Operator(
            id=operator_id,
            name=name or f"{provider}-user-{provider_id[:8]}",
            entity_type="individual",
            email=email or f"{provider}_{provider_id}@oauth.tioli.co.za",
            jurisdiction="ZA",
            oauth_provider=provider,
            oauth_provider_id=str(provider_id),
            avatar_url=avatar_url,
            github_login=github_login,
            is_active=True,
            tos_accepted=True,
            tos_accepted_at=datetime.now(timezone.utc),
            privacy_accepted=True,
        )
        db.add(operator)
        await db.flush()

        # Create operator hub profile
        await _ensure_profile(db, operator_id, name, avatar_url, github_login)
        await db.commit()
        return operator_id


async def _ensure_profile(db, operator_id: str, name: str, avatar_url: str = None, github_login: str = None):
    """Ensure an OperatorHubProfile exists for this operator."""
    result = await db.execute(
        select(OperatorHubProfile).where(OperatorHubProfile.operator_id == operator_id)
    )
    if result.scalar_one_or_none():
        return

    handle = github_login or f"builder-{operator_id[:8]}"
    # Check handle uniqueness
    existing = await db.execute(
        select(OperatorHubProfile).where(OperatorHubProfile.handle == handle)
    )
    if existing.scalar_one_or_none():
        handle = f"{handle}-{uuid.uuid4().hex[:4]}"

    profile = OperatorHubProfile(
        operator_id=operator_id,
        handle=handle,
        display_name=name or "New Builder",
        avatar_url=avatar_url,
        github_url=f"https://github.com/{github_login}" if github_login else None,
    )
    db.add(profile)


# ── GitHub OAuth ────────────────────────────────────────────────────

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


@router.get("/auth/github")
async def github_login():
    """Redirect to GitHub for OAuth authorization."""
    if not settings.github_client_id:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")
    callback = f"{settings.oauth_redirect_base}/auth/github/callback"
    url = (
        f"{GITHUB_AUTHORIZE_URL}?"
        f"client_id={settings.github_client_id}&"
        f"redirect_uri={callback}&"
        f"scope=user:email&"
        f"state=tioli_github"
    )
    return RedirectResponse(url=url)


@router.get("/auth/github/callback")
async def github_callback(code: str = None, error: str = None):
    """Handle GitHub OAuth callback."""
    if error or not code:
        return RedirectResponse(url="/operator-register?error=github_denied")

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return RedirectResponse(url="/operator-register?error=github_token_failed")

        # Get user info
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        user_resp = await client.get(GITHUB_USER_URL, headers=headers)
        user = user_resp.json()

        # Get email (may be private)
        email = user.get("email")
        if not email:
            emails_resp = await client.get(GITHUB_EMAILS_URL, headers=headers)
            emails = emails_resp.json()
            if isinstance(emails, list):
                primary = next((e for e in emails if e.get("primary")), None)
                email = primary["email"] if primary else (emails[0]["email"] if emails else None)

    # Find or create operator
    operator_id = await _find_or_create_operator(
        provider="github",
        provider_id=str(user.get("id")),
        name=user.get("name") or user.get("login"),
        email=email,
        avatar_url=user.get("avatar_url"),
        github_login=user.get("login"),
    )

    # Get profile handle for redirect
    async with async_session() as db:
        result = await db.execute(
            select(OperatorHubProfile.handle).where(OperatorHubProfile.operator_id == operator_id)
        )
        handle = result.scalar_one_or_none() or operator_id[:8]

    response = RedirectResponse(url=f"/builders/{handle}")
    return _set_session_cookie(response, operator_id)


# ── Google OAuth ────────────────────────────────────────────────────

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


@router.get("/auth/google")
async def google_login():
    """Redirect to Google for OAuth authorization."""
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    callback = f"{settings.oauth_redirect_base}/auth/google/callback"
    url = (
        f"{GOOGLE_AUTHORIZE_URL}?"
        f"client_id={settings.google_client_id}&"
        f"redirect_uri={callback}&"
        f"scope=openid email profile&"
        f"response_type=code&"
        f"state=tioli_google"
    )
    return RedirectResponse(url=url)


@router.get("/auth/google/callback")
async def google_callback(code: str = None, error: str = None):
    """Handle Google OAuth callback."""
    if error or not code:
        return RedirectResponse(url="/operator-register?error=google_denied")

    callback = f"{settings.oauth_redirect_base}/auth/google/callback"

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "redirect_uri": callback,
                "grant_type": "authorization_code",
            },
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return RedirectResponse(url="/operator-register?error=google_token_failed")

        # Get user info
        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user = user_resp.json()

    # Find or create operator
    operator_id = await _find_or_create_operator(
        provider="google",
        provider_id=str(user.get("id")),
        name=user.get("name"),
        email=user.get("email"),
        avatar_url=user.get("picture"),
    )

    # Get profile handle for redirect
    async with async_session() as db:
        result = await db.execute(
            select(OperatorHubProfile.handle).where(OperatorHubProfile.operator_id == operator_id)
        )
        handle = result.scalar_one_or_none() or operator_id[:8]

    response = RedirectResponse(url=f"/builders/{handle}")
    return _set_session_cookie(response, operator_id)


# ── Email Verification Registration (2-step) ────────────────────────

import secrets as _secrets
import re
import os
import logging

logger = logging.getLogger(__name__)

# Pending registrations: verification_id -> {name, email, company, code, created_at}
_pending_registrations: dict[str, dict] = {}


def _send_operator_verification_email(recipient_email: str, code: str) -> bool:
    """Send a 6-digit verification code to the operator's email via Graph API."""
    from app.auth.email_verify import _get_graph_access_token

    access_token = _get_graph_access_token()
    if not access_token:
        logger.warning("Graph API not configured — cannot send verification email")
        return False

    sender_email = os.environ.get("SMTP_USER", settings.owner_email)

    email_body = {
        "message": {
            "subject": "TiOLi AGENTIS — Verify Your Email",
            "body": {
                "contentType": "HTML",
                "content": f"""
                <div style="font-family: 'Inter', Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 30px; background: #f5f5f3; border-radius: 12px;">
                    <div style="background: #2b2b2b; padding: 20px; border-radius: 10px 10px 0 0; text-align: center; border-bottom: 3px solid #77d4e5;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 18px; letter-spacing: 0.5px;">TiOLi AGENTIS</h1>
                    </div>
                    <div style="background: #ffffff; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #eae7e3;">
                        <h2 style="color: #2b2b2b; margin-top: 0; font-size: 20px;">Email Verification</h2>
                        <p style="color: #7a7a7a; line-height: 1.6;">Welcome to TiOLi AGENTIS! Enter this code to complete your builder registration:</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <span style="background: #061423; color: #77d4e5; padding: 14px 32px; border-radius: 8px; font-weight: 700; font-size: 28px; letter-spacing: 6px; display: inline-block;">{code}</span>
                        </div>
                        <p style="color: #aaa; font-size: 12px; text-align: center;">This code expires in 10 minutes and can only be used once.</p>
                    </div>
                    <p style="color: #aaa; font-size: 11px; text-align: center; margin-top: 15px;">TiOLi Group Holdings (Pty) Ltd — The Agentic Exchange</p>
                </div>
                """,
            },
            "toRecipients": [
                {"emailAddress": {"address": recipient_email}}
            ],
        },
        "saveToSentItems": "false",
    }

    try:
        import httpx as _httpx
        response = _httpx.post(
            f"https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail",
            json=email_body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"Operator verification code sent to {recipient_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send operator verification email: {e}")
        return False


@router.post("/auth/operator/send-code")
async def send_verification_code(request: Request):
    """Step 1: Send a 6-digit verification code to the operator's email."""
    body = await request.json()
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    company = (body.get("company") or "").strip()

    if not name or not email:
        raise HTTPException(status_code=400, detail="Name and email are required")

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")

    # Check if email already registered
    async with async_session() as db:
        existing = await db.execute(select(Operator).where(Operator.email == email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="An account with this email already exists. Try signing in with GitHub or Google.")

    # Generate code and store pending registration
    code = f"{_secrets.randbelow(900000) + 100000}"
    verification_id = str(uuid.uuid4())
    _pending_registrations[verification_id] = {
        "name": name, "email": email, "company": company,
        "code": code, "created_at": datetime.now(timezone.utc),
    }

    # Send code
    sent = _send_operator_verification_email(email, code)
    if not sent:
        raise HTTPException(status_code=500, detail="Unable to send verification email. Please try GitHub or Google sign-up instead.")

    return {
        "verification_id": verification_id,
        "message": f"Verification code sent to {email}. Check your inbox.",
    }


@router.post("/auth/operator/verify-code")
async def verify_code_and_register(request: Request):
    """Step 2: Verify the code and create the operator account."""
    body = await request.json()
    verification_id = (body.get("verification_id") or "").strip()
    code = (body.get("code") or "").strip()

    if not verification_id or not code:
        raise HTTPException(status_code=400, detail="Verification ID and code are required")

    pending = _pending_registrations.get(verification_id)
    if not pending:
        raise HTTPException(status_code=400, detail="Verification expired or invalid. Please request a new code.")

    # Check expiry (10 minutes)
    elapsed = (datetime.now(timezone.utc) - pending["created_at"]).total_seconds()
    if elapsed > 600:
        del _pending_registrations[verification_id]
        raise HTTPException(status_code=400, detail="Verification code expired. Please request a new code.")

    # Check code
    if not _secrets.compare_digest(code.strip(), pending["code"]):
        raise HTTPException(status_code=400, detail="Incorrect verification code. Please try again.")

    # Code valid — consume it
    del _pending_registrations[verification_id]

    # Create operator account
    operator_id = await _find_or_create_operator(
        provider=None, provider_id=str(uuid.uuid4()),
        name=pending["name"], email=pending["email"],
    )

    # Update company if provided
    if pending["company"]:
        async with async_session() as db:
            result = await db.execute(
                select(OperatorHubProfile).where(OperatorHubProfile.operator_id == operator_id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                profile.company = pending["company"]
                await db.commit()

    # Get handle
    async with async_session() as db:
        result = await db.execute(
            select(OperatorHubProfile).where(OperatorHubProfile.operator_id == operator_id)
        )
        profile = result.scalar_one_or_none()
        handle = profile.handle if profile else operator_id[:8]

    return {
        "operator_id": operator_id,
        "handle": handle,
        "profile_url": f"/builders/{handle}",
        "message": "Email verified! Account created successfully. Welcome to AGENTIS!",
    }


# Legacy endpoint — redirect to send-code flow
@router.post("/auth/operator/register")
async def register_operator_legacy(request: Request):
    """Legacy manual registration — now redirects to verification flow."""
    return await send_verification_code(request)


# ── Email Login (existing users) ─────────────────────────────────────

_pending_logins: dict[str, dict] = {}


@router.post("/auth/operator/login-send-code")
async def login_send_code(request: Request):
    """Send a 6-digit login code to an existing operator's email."""
    body = await request.json()
    email = (body.get("email") or "").strip().lower()

    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    # Find existing operator
    async with async_session() as db:
        result = await db.execute(select(Operator).where(Operator.email == email))
        operator = result.scalar_one_or_none()

    if not operator:
        raise HTTPException(status_code=404, detail="No account found with this email. Please register first.")

    # Generate code
    code = f"{_secrets.randbelow(900000) + 100000}"
    login_id = str(uuid.uuid4())
    _pending_logins[login_id] = {
        "operator_id": operator.id, "email": email,
        "code": code, "created_at": datetime.now(timezone.utc),
    }

    # Send code
    sent = _send_operator_verification_email(email, code)
    if not sent:
        raise HTTPException(status_code=500, detail="Unable to send login code. Please try GitHub or Google sign-in instead.")

    return {
        "login_id": login_id,
        "message": f"Login code sent to {email}. Check your inbox.",
    }


@router.post("/auth/operator/login-verify-code")
async def login_verify_code(request: Request):
    """Verify the login code and create a session."""
    body = await request.json()
    login_id = (body.get("login_id") or "").strip()
    code = (body.get("code") or "").strip()

    if not login_id or not code:
        raise HTTPException(status_code=400, detail="Login ID and code are required")

    pending = _pending_logins.get(login_id)
    if not pending:
        raise HTTPException(status_code=400, detail="Login expired or invalid. Please request a new code.")

    # Check expiry (10 minutes)
    elapsed = (datetime.now(timezone.utc) - pending["created_at"]).total_seconds()
    if elapsed > 600:
        del _pending_logins[login_id]
        raise HTTPException(status_code=400, detail="Login code expired. Please request a new code.")

    # Check code
    if not _secrets.compare_digest(code.strip(), pending["code"]):
        raise HTTPException(status_code=400, detail="Incorrect code. Please try again.")

    # Code valid — consume it
    del _pending_logins[login_id]

    # Get profile handle
    async with async_session() as db:
        result = await db.execute(
            select(OperatorHubProfile.handle).where(OperatorHubProfile.operator_id == pending["operator_id"])
        )
        handle = result.scalar_one_or_none() or pending["operator_id"][:8]

    # Set session cookie and return profile URL
    from fastapi.responses import JSONResponse
    resp = JSONResponse({
        "operator_id": pending["operator_id"],
        "handle": handle,
        "profile_url": f"/builders/{handle}",
        "message": "Login successful! Welcome back.",
    })
    token = _create_session_token(pending["operator_id"])
    resp.set_cookie(
        key=SESSION_COOKIE, value=token,
        max_age=SESSION_EXPIRY_DAYS * 86400,
        httponly=True, secure=True, samesite="lax",
    )
    return resp


# ── Session Helpers ─────────────────────────────────────────────────

async def get_current_operator(request: Request) -> Operator | None:
    """Get the currently logged-in operator from session cookie."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    payload = decode_operator_session(token)
    if not payload:
        return None
    async with async_session() as db:
        result = await db.execute(
            select(Operator).where(Operator.id == payload["operator_id"])
        )
        return result.scalar_one_or_none()


@router.get("/auth/operator/me")
async def get_operator_me(request: Request):
    """Get the current operator's basic info from session."""
    operator = await get_current_operator(request)
    if not operator:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "operator_id": operator.id,
        "name": operator.name,
        "email": operator.email,
        "avatar_url": operator.avatar_url,
        "github_login": operator.github_login,
    }


@router.get("/auth/operator/logout")
async def operator_logout():
    """Clear the operator session cookie."""
    response = RedirectResponse(url="/operator-register")
    response.delete_cookie(SESSION_COOKIE)
    return response

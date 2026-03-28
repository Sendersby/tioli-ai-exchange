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


# ── Manual Registration ─────────────────────────────────────────────

@router.post("/auth/operator/register")
async def register_operator_manual(request: Request):
    """Manual operator registration (no OAuth). Returns JSON with operator_id."""
    body = await request.json()
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip()
    company = (body.get("company") or "").strip()

    if not name or not email:
        raise HTTPException(status_code=400, detail="Name and email are required")

    # Check existing
    async with async_session() as db:
        existing = await db.execute(select(Operator).where(Operator.email == email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="An account with this email already exists")

    operator_id = await _find_or_create_operator(
        provider=None, provider_id=str(uuid.uuid4()),
        name=name, email=email,
    )

    # Update company if provided
    if company:
        async with async_session() as db:
            result = await db.execute(
                select(OperatorHubProfile).where(OperatorHubProfile.operator_id == operator_id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                profile.company = company
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
        "message": "Account created successfully. Welcome to AGENTIS!",
    }


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

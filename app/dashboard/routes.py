"""Dashboard web routes — owner-facing UI."""

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
    challenge = owner_auth.initiate_login()
    return templates.TemplateResponse("login.html", {
        "request": request,
        "challenge": challenge,
        "status": {"email_verified": False, "phone_verified": False, "cli_verified": False},
        "authenticated": False,
    })


@router.post("/auth/verify-email")
async def verify_email(request: Request, challenge_id: str = Form(...), email: str = Form(...)):
    owner_auth.verify_email(challenge_id, email)
    status = owner_auth.check_challenge_complete(challenge_id)
    challenge = {"challenge_id": challenge_id, "cli_code": owner_auth.get_cli_code(challenge_id)}
    if status.get("complete"):
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie("session_token", status["access_token"], httponly=True, samesite="strict")
        return response
    return templates.TemplateResponse("login.html", {
        "request": request, "challenge": challenge, "status": status, "authenticated": False,
    })


@router.post("/auth/verify-phone")
async def verify_phone(request: Request, challenge_id: str = Form(...), phone: str = Form(...)):
    owner_auth.verify_phone(challenge_id, phone)
    status = owner_auth.check_challenge_complete(challenge_id)
    challenge = {"challenge_id": challenge_id, "cli_code": owner_auth.get_cli_code(challenge_id)}
    if status.get("complete"):
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie("session_token", status["access_token"], httponly=True, samesite="strict")
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
        response.set_cookie("session_token", status["access_token"], httponly=True, samesite="strict")
        return response
    return templates.TemplateResponse("login.html", {
        "request": request, "challenge": challenge, "status": status, "authenticated": False,
    })


@router.post("/auth/complete")
async def complete_login(request: Request, challenge_id: str = Form(...)):
    status = owner_auth.check_challenge_complete(challenge_id)
    if status.get("complete"):
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie("session_token", status["access_token"], httponly=True, samesite="strict")
        return response
    challenge = {"challenge_id": challenge_id, "cli_code": owner_auth.get_cli_code(challenge_id)}
    return templates.TemplateResponse("login.html", {
        "request": request, "challenge": challenge, "status": status,
        "authenticated": False,
        "messages": [{"type": "error", "text": "Not all factors verified yet."}],
    })


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session_token")
    return response


@router.get("/dashboard/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("chat.html", {
        "request": request, "authenticated": True, "active": "chat",
    })

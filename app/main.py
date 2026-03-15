"""TiOLi AI Transact Exchange — Main Application Entry Point.

The world's first AI-native financial exchange.
Confidential — TiOLi AI Investments.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.db import init_db, get_db, async_session
from app.blockchain.chain import Blockchain
from app.blockchain.transaction import Transaction, TransactionType
from app.agents.models import Agent, Wallet, Loan
from app.agents.wallet import WalletService
from app.auth.owner import owner_auth
from app.auth.agent_auth import register_agent, authenticate_agent
from app.exchange.fees import FeeEngine
from app.governance.models import Proposal, Vote
from app.governance.voting import GovernanceService
from app.dashboard.routes import router as dashboard_router, get_current_owner

# ── Globals ──────────────────────────────────────────────────────────
blockchain = Blockchain(storage_path="tioli_exchange_chain.json")
fee_engine = FeeEngine()
wallet_service = WalletService(blockchain=blockchain, fee_engine=fee_engine)
governance_service = GovernanceService()
templates = Jinja2Templates(directory="app/templates")


# ── App Lifecycle ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and blockchain on startup."""
    await init_db()
    print(f"\n{'='*60}")
    print(f"  TiOLi AI Transact Exchange v{settings.version}")
    print(f"  Blockchain: {blockchain.get_chain_info()['chain_length']} blocks")
    print(f"  Chain valid: {blockchain.validate_chain()}")
    print(f"  Founder commission: {fee_engine.founder_rate*100:.1f}%")
    print(f"  Charity fee: {fee_engine.charity_rate*100:.1f}%")
    print(f"{'='*60}\n")
    yield


app = FastAPI(
    title="TiOLi AI Transact Exchange",
    description="Decentralised blockchain exchange for AI agents",
    version=settings.version,
    lifespan=lifespan,
)

# Mount static files and dashboard routes
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(dashboard_router)


# ── Helper: Agent Auth Dependency ────────────────────────────────────
async def require_agent(
    authorization: str = Header(..., description="Bearer <api_key>"),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """Dependency that authenticates an AI agent via API key."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    api_key = authorization[7:]
    agent = await authenticate_agent(db, api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return agent


# ── Request/Response Models ──────────────────────────────────────────
class AgentRegisterRequest(BaseModel):
    name: str
    platform: str
    description: str = ""

class TransferRequest(BaseModel):
    receiver_id: str
    amount: float
    currency: str = "TIOLI"
    description: str = ""

class DepositRequest(BaseModel):
    amount: float
    currency: str = "TIOLI"
    description: str = ""

class WithdrawRequest(BaseModel):
    amount: float
    currency: str = "TIOLI"
    description: str = ""

class LoanRequest(BaseModel):
    borrower_id: str
    amount: float
    interest_rate: float
    currency: str = "TIOLI"

class LoanRepayRequest(BaseModel):
    loan_id: str
    amount: float

class ProposalRequest(BaseModel):
    title: str
    description: str
    category: str = "feature"

class VoteRequest(BaseModel):
    vote_type: str  # "up" or "down"

class ChatRequest(BaseModel):
    message: str


# ── Agent API Endpoints ──────────────────────────────────────────────

@app.post("/api/agents/register")
async def api_register_agent(
    req: AgentRegisterRequest, db: AsyncSession = Depends(get_db)
):
    """Register a new AI agent on the platform."""
    result = await register_agent(db, req.name, req.platform, req.description)

    # Record registration on blockchain
    tx = Transaction(
        type=TransactionType.AGENT_REGISTRATION,
        receiver_id=result["agent_id"],
        amount=0.0,
        description=f"Agent registered: {req.name} ({req.platform})",
    )
    blockchain.add_transaction(tx)

    return result


@app.get("/api/agents/me")
async def api_agent_info(agent: Agent = Depends(require_agent)):
    """Get current agent's profile."""
    return {
        "id": agent.id,
        "name": agent.name,
        "platform": agent.platform,
        "is_active": agent.is_active,
        "created_at": str(agent.created_at),
    }


@app.post("/api/wallet/deposit")
async def api_deposit(
    req: DepositRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Deposit funds into your wallet."""
    tx = await wallet_service.deposit(db, agent.id, req.amount, req.currency, req.description)
    return {"transaction_id": tx.id, "amount": req.amount, "currency": req.currency}


@app.post("/api/wallet/withdraw")
async def api_withdraw(
    req: WithdrawRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Withdraw funds from your wallet."""
    tx = await wallet_service.withdraw(db, agent.id, req.amount, req.currency, req.description)
    return {"transaction_id": tx.id, "amount": req.amount, "currency": req.currency}


@app.get("/api/wallet/balance")
async def api_balance(
    currency: str = "TIOLI",
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Check your wallet balance."""
    return await wallet_service.get_balance(db, agent.id, currency)


@app.post("/api/wallet/transfer")
async def api_transfer(
    req: TransferRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Transfer funds to another agent (fees auto-deducted)."""
    tx = await wallet_service.transfer(
        db, agent.id, req.receiver_id, req.amount, req.currency, req.description
    )
    fee_info = fee_engine.calculate_fees(req.amount)
    return {
        "transaction_id": tx.id,
        "gross_amount": req.amount,
        "net_to_receiver": fee_info["net_amount"],
        "founder_commission": fee_info["founder_commission"],
        "charity_fee": fee_info["charity_fee"],
    }


@app.post("/api/loans/issue")
async def api_issue_loan(
    req: LoanRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Issue a loan to another agent."""
    loan = await wallet_service.issue_loan(
        db, agent.id, req.borrower_id, req.amount, req.interest_rate, req.currency
    )
    return {
        "loan_id": loan.id,
        "principal": loan.principal,
        "interest_rate": loan.interest_rate,
        "total_owed": loan.total_owed,
    }


@app.post("/api/loans/repay")
async def api_repay_loan(
    req: LoanRepayRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Repay a loan (partial or full)."""
    tx = await wallet_service.repay_loan(db, req.loan_id, req.amount)
    return {"transaction_id": tx.id, "amount_repaid": req.amount}


# ── Governance Endpoints ─────────────────────────────────────────────

@app.post("/api/governance/propose")
async def api_submit_proposal(
    req: ProposalRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Submit a platform improvement proposal."""
    proposal = await governance_service.submit_proposal(
        db, agent.id, req.title, req.description, req.category
    )
    return {
        "proposal_id": proposal.id,
        "title": proposal.title,
        "requires_veto_review": proposal.requires_veto_review,
    }


@app.post("/api/governance/vote/{proposal_id}")
async def api_vote(
    proposal_id: str,
    req: VoteRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Vote on a proposal."""
    vote = await governance_service.cast_vote(db, proposal_id, agent.id, req.vote_type)
    return {"vote_id": vote.id, "vote_type": req.vote_type}


@app.get("/api/governance/proposals")
async def api_list_proposals(
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    """List proposals (optionally filtered by status)."""
    proposals = await governance_service.get_proposals(db, status)
    return [
        {
            "id": p.id, "title": p.title, "category": p.category,
            "upvotes": p.upvotes, "downvotes": p.downvotes,
            "status": p.status, "is_material": p.is_material_change,
        }
        for p in proposals
    ]


# Owner governance actions (via dashboard forms)
@app.post("/governance/approve/{proposal_id}")
async def web_approve_proposal(
    proposal_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    await governance_service.owner_approve(db, proposal_id)
    return RedirectResponse(url="/dashboard", status_code=302)


@app.post("/governance/veto/{proposal_id}")
async def web_veto_proposal(
    proposal_id: str, request: Request,
    reason: str = "", db: AsyncSession = Depends(get_db)
):
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    await governance_service.owner_veto(db, proposal_id, reason or "Owner veto")
    return RedirectResponse(url="/dashboard", status_code=302)


# ── Blockchain & Platform Endpoints ─────────────────────────────────

@app.get("/api/blockchain/info")
async def api_chain_info():
    """Public blockchain statistics."""
    return blockchain.get_chain_info()


@app.get("/api/blockchain/validate")
async def api_validate_chain():
    """Validate the entire blockchain integrity."""
    return {"valid": blockchain.validate_chain()}


@app.get("/api/transactions/{agent_id}")
async def api_agent_transactions(agent_id: str):
    """Get all transactions for a specific agent — full transparency."""
    return blockchain.get_transactions_for_agent(agent_id)


@app.get("/api/fees/schedule")
async def api_fee_schedule():
    """Current fee schedule — fully transparent."""
    return {
        "founder_commission_rate": fee_engine.founder_rate,
        "charity_fee_rate": fee_engine.charity_rate,
        "total_fee_rate": fee_engine.founder_rate + fee_engine.charity_rate,
        "founder_entity": "TiOLi AI Investments",
    }


# ── Dashboard Data Endpoint ──────────────────────────────────────────

@app.get("/api/stats")
async def api_stats():
    """Dashboard statistics (used by auto-refresh)."""
    info = blockchain.get_chain_info()
    all_tx = blockchain.get_all_transactions()

    founder_earnings = sum(
        tx.get("founder_commission", 0) for tx in all_tx
    )
    charity_total = sum(
        tx.get("charity_fee", 0) for tx in all_tx
    )

    async with async_session() as db:
        result = await db.execute(select(func.count(Agent.id)))
        agent_count = result.scalar() or 0

    return {
        "chain_length": info["chain_length"],
        "total_transactions": info["total_transactions"],
        "agent_count": agent_count,
        "founder_earnings": founder_earnings,
        "charity_total": charity_total,
        "is_valid": info["is_valid"],
    }


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Main owner dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    info = blockchain.get_chain_info()
    all_tx = blockchain.get_all_transactions()

    founder_earnings = sum(tx.get("founder_commission", 0) for tx in all_tx)
    charity_total = sum(tx.get("charity_fee", 0) for tx in all_tx)
    recent = all_tx[-20:] if all_tx else []
    recent.reverse()

    async with async_session() as db:
        agent_result = await db.execute(select(func.count(Agent.id)))
        agent_count = agent_result.scalar() or 0

        proposals = await governance_service.get_proposals(db, status="pending")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "authenticated": True,
        "active": "dashboard",
        "chain_info": info,
        "agent_count": agent_count,
        "founder_earnings": founder_earnings,
        "charity_total": charity_total,
        "recent_transactions": [_tx_display(tx) for tx in recent],
        "pending_proposals": proposals,
    })


def _tx_display(tx: dict) -> object:
    """Convert a raw transaction dict to a display-friendly object."""
    class TxDisplay:
        pass
    d = TxDisplay()
    d.timestamp = tx.get("timestamp", "")
    d.type = tx.get("type", "unknown")
    d.sender_id = tx.get("sender_id", "")
    d.receiver_id = tx.get("receiver_id", "")
    d.amount = tx.get("amount", 0)
    d.currency = tx.get("currency", "TIOLI")
    return d


# ── AI Chat Endpoint ─────────────────────────────────────────────────

@app.post("/api/chat")
async def api_chat(req: ChatRequest, request: Request):
    """Simple AI chat for the owner dashboard.

    This processes natural language commands about the platform.
    In Phase 2+, this will integrate with a full LLM backend.
    """
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")

    msg = req.message.lower()
    info = blockchain.get_chain_info()
    all_tx = blockchain.get_all_transactions()

    # Simple command parsing (will be upgraded to LLM in Phase 2)
    if "status" in msg or "overview" in msg:
        return {"response": (
            f"Platform Status:\n"
            f"- Blockchain: {info['chain_length']} blocks, {'valid' if info['is_valid'] else 'INVALID'}\n"
            f"- Total transactions: {info['total_transactions']}\n"
            f"- Pending: {info['pending_transactions']}"
        )}
    elif "earning" in msg or "commission" in msg:
        earnings = sum(tx.get("founder_commission", 0) for tx in all_tx)
        return {"response": f"Your total earnings: {earnings:.4f} TIOLI\nCommission rate: {fee_engine.founder_rate*100:.1f}%"}
    elif "charity" in msg or "philanthropic" in msg:
        charity = sum(tx.get("charity_fee", 0) for tx in all_tx)
        return {"response": f"Charity fund total: {charity:.4f} TIOLI\nCharity rate: {fee_engine.charity_rate*100:.1f}%"}
    elif "chain" in msg or "blockchain" in msg or "valid" in msg:
        return {"response": f"Chain length: {info['chain_length']} blocks\nValid: {info['is_valid']}\nLatest hash: {info['latest_block_hash'][:16]}..."}
    elif "fee" in msg:
        return {"response": (
            f"Fee Schedule:\n"
            f"- Founder commission: {fee_engine.founder_rate*100:.1f}%\n"
            f"- Charity fee: {fee_engine.charity_rate*100:.1f}%\n"
            f"- Total deduction: {(fee_engine.founder_rate + fee_engine.charity_rate)*100:.1f}%"
        )}
    elif "help" in msg:
        return {"response": (
            "I can help you with:\n"
            "- 'status' — Platform overview\n"
            "- 'earnings' — Your commission totals\n"
            "- 'charity' — Philanthropic fund status\n"
            "- 'blockchain' — Chain integrity\n"
            "- 'fees' — Current fee schedule\n"
            "- 'mine' — Force mine pending transactions\n"
            "\nMore commands coming in Phase 2!"
        )}
    elif "mine" in msg:
        block = blockchain.force_mine()
        if block:
            return {"response": f"Block #{block.index} mined with {len(block.transactions)} transactions.\nHash: {block.hash[:16]}..."}
        return {"response": "No pending transactions to mine."}
    else:
        return {"response": (
            f"I understood your message. In Phase 2, I'll have full AI capabilities.\n"
            f"For now, try: status, earnings, charity, blockchain, fees, mine, or help."
        )}

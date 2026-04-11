"""Router: misc - auto-extracted from main.py (A-001)."""
from fastapi import APIRouter, Depends, Request, HTTPException, Header, Query, Path, Body
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from pydantic import BaseModel
from app.database.db import get_db, async_session
from app.agents.models import Agent, Wallet, Loan
from app.blockchain.transaction import Transaction, TransactionType
from app.utils.validators import require_kyc_verified
from app.dashboard.routes import get_current_owner
from app.utils.audit import log_financial_event
from app.security.transaction_safety import InputValidator
from app.config import settings
from app.infrastructure.cache import cache, TTL_SHORT, TTL_MEDIUM, TTL_LONG
import json, uuid, os, time, logging
from datetime import datetime, timezone
from collections import defaultdict
from app.main_deps import (blockchain, futures_service, guild_service, pipeline_service, verticals_service)

router = APIRouter()

@router.get("/transactions/{tx_id}/receipt", include_in_schema=False)
async def transaction_receipt_page(tx_id: str, request: Request):
    """Public shareable transaction receipt — blockchain proof + charitable allocation.

    Public view: anonymised (no agent names, rounded amounts)
    Authenticated view: full details
    """
    all_tx = blockchain.get_all_transactions()

    # Find the transaction
    tx = None
    for t in all_tx:
        if t.get("id", "") == tx_id or str(t.get("block_index", "")) == tx_id:
            tx = t
            break

    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Calculate charitable total
    total_charitable = sum(t.get("charity_fee", 0) for t in all_tx)

    # Check if authenticated
    owner = get_current_owner(request)
    is_authenticated = owner is not None

    tx_type = tx.get("type", "unknown")
    amount = tx.get("amount", 0)
    currency = tx.get("currency", "AGENTIS")
    charity_fee = tx.get("charity_fee", 0)
    founder_commission = tx.get("founder_commission", 0)
    block_hash = tx.get("block_hash", "pending")
    block_index = tx.get("block_index", "—")
    status = tx.get("confirmation_status", "CONFIRMED")
    description = tx.get("description", "")
    timestamp = tx.get("timestamp", "")

    # Anonymise for public view
    if is_authenticated:
        sender = tx.get("sender_id", "")[:12] + "..." if tx.get("sender_id") else "SYSTEM"
        receiver = tx.get("receiver_id", "")[:12] + "..." if tx.get("receiver_id") else "—"
        display_amount = f"{amount} {currency}"
    else:
        sender = "Agent"
        receiver = "Agent"
        # Round to nearest bracket
        if amount > 0:
            bracket = max(round(amount / 100) * 100, 100)
            display_amount = f"{bracket-100}–{bracket} {currency}"
        else:
            display_amount = f"{currency}"

    receipt_url = f"https://exchange.tioli.co.za/transactions/{tx_id}/receipt"
    share_text = f"AI agent transaction verified on TiOLi AGENTIS blockchain. Type: {tx_type} | Status: {status} | View receipt: {receipt_url} #AIAgents #TiOLiAgentis"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Transaction Receipt — TiOLi AGENTIS</title>
<meta name="description" content="Verified AI agent transaction on TiOLi AGENTIS blockchain."/>
<meta property="og:title" content="Verified Transaction — TiOLi AGENTIS"/>
<meta property="og:description" content="AI agent transaction verified on blockchain. {tx_type}. {status}."/>
<meta property="og:url" content="{receipt_url}"/>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght@100..700,0..1&display=swap" rel="stylesheet"/>
<style>body{{background:#061423;color:#d6e4f9;font-family:'Inter',sans-serif}}</style>
</head>
<body class="min-h-screen">
<nav class="fixed top-0 w-full z-50 bg-[#061423]/90 backdrop-blur-xl border-b border-[#77d4e5]/15">
<div class="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
<div class="flex items-center gap-3">
<button onclick="history.back()" class="w-8 h-8 flex items-center justify-center bg-[#0f1c2c] border border-[#44474c]/30 rounded hover:border-[#77d4e5]/30 transition-colors"><span class="material-symbols-outlined text-slate-400 text-lg">arrow_back</span></button>
<a href="/" class="text-xl font-light text-white">T<span class="text-[#edc05f]">i</span>OL<span class="text-[#edc05f]">i</span> <span class="font-bold" style="background:linear-gradient(135deg,#77d4e5,#edc05f);-webkit-background-clip:text;-webkit-text-fill-color:transparent">AGENTIS</span></a>
</div>
</div>
</nav>
<div class="max-w-3xl mx-auto px-6 pt-28 pb-16">
<div class="flex items-center gap-2 text-[0.6rem] text-slate-500 mb-4">
<a href="/" class="hover:text-[#77d4e5]">Home</a><span>&rsaquo;</span>
<a href="/explorer" class="hover:text-[#77d4e5]">Explorer</a><span>&rsaquo;</span>
<span class="text-slate-400">Receipt</span>
</div>

<!-- Receipt Card -->
<div class="bg-[#0f1c2c] border border-[#77d4e5]/15 rounded-lg overflow-hidden mb-6">
<div class="bg-[#77d4e5]/5 border-b border-[#77d4e5]/15 p-6 text-center">
<div class="flex items-center justify-center gap-2 mb-2">
<span class="material-symbols-outlined text-green-400 text-2xl">verified</span>
<span class="text-green-400 font-bold text-lg">Verified on Blockchain</span>
</div>
<div class="text-xs text-slate-400">Transaction permanently recorded on the TiOLi AGENTIS immutable ledger</div>
</div>
<div class="p-6 space-y-4">
<div class="grid grid-cols-2 gap-4">
<div>
<div class="text-[0.6rem] text-slate-500 uppercase mb-1">Type</div>
<div class="text-white font-bold">{tx_type}</div>
</div>
<div>
<div class="text-[0.6rem] text-slate-500 uppercase mb-1">Status</div>
<div class="text-green-400 font-bold">{status}</div>
</div>
<div>
<div class="text-[0.6rem] text-slate-500 uppercase mb-1">Amount</div>
<div class="text-white font-bold">{display_amount}</div>
</div>
<div>
<div class="text-[0.6rem] text-slate-500 uppercase mb-1">Timestamp</div>
<div class="text-white text-sm font-mono">{str(timestamp)[:19] if timestamp else '—'}</div>
</div>
</div>

<div class="border-t border-[#44474c]/20 pt-4">
<div class="grid grid-cols-2 gap-4">
<div>
<div class="text-[0.6rem] text-slate-500 uppercase mb-1">From</div>
<div class="text-slate-300 text-sm font-mono">{sender}</div>
</div>
<div>
<div class="text-[0.6rem] text-slate-500 uppercase mb-1">To</div>
<div class="text-slate-300 text-sm font-mono">{receiver}</div>
</div>
</div>
</div>

<div class="border-t border-[#44474c]/20 pt-4">
<div class="grid grid-cols-2 gap-4">
<div>
<div class="text-[0.6rem] text-slate-500 uppercase mb-1">Block Hash</div>
<div class="text-[#77d4e5] text-xs font-mono break-all">{block_hash[:32] if block_hash else 'pending'}...</div>
</div>
<div>
<div class="text-[0.6rem] text-slate-500 uppercase mb-1">Block Index</div>
<div class="text-white font-mono">{block_index}</div>
</div>
</div>
</div>

<!-- Charitable allocation — the "aha moment" -->
<div class="border-t border-[#edc05f]/20 pt-4 bg-[#edc05f]/5 -mx-6 px-6 pb-4 -mb-6">
<div class="flex items-center gap-2 mb-2">
<span class="material-symbols-outlined text-[#edc05f]">volunteer_activism</span>
<span class="text-[#edc05f] font-bold text-sm">Charitable Impact</span>
</div>
<div class="grid grid-cols-2 gap-4">
<div>
<div class="text-[0.6rem] text-slate-500 uppercase mb-1">This Transaction</div>
<div class="text-[#edc05f] font-bold">{charity_fee:.2f} AGENTIS</div>
</div>
<div>
<div class="text-[0.6rem] text-slate-500 uppercase mb-1">Running Total</div>
<div class="text-[#edc05f] font-bold">{total_charitable:.2f} AGENTIS</div>
</div>
</div>
<div class="text-[0.55rem] text-slate-500 mt-2">10% of all platform commission is allocated to charitable causes and recorded on-chain.</div>
</div>
</div>
</div>

<!-- Share -->
<div class="flex gap-3">
<button onclick="navigator.clipboard.writeText('{share_text}');this.textContent='Copied!';setTimeout(()=>this.textContent='Share This Receipt',2000)" class="flex-1 py-3 text-center border border-[#77d4e5]/20 text-[#77d4e5] font-bold text-sm uppercase tracking-widest hover:bg-[#77d4e5]/10 rounded transition-colors">Share This Receipt</button>
<a href="/explorer" class="flex-1 py-3 text-center border border-[#44474c]/30 text-slate-300 font-bold text-sm uppercase tracking-widest hover:bg-[#0f1c2c] rounded transition-colors">View Explorer</a>
</div>
<div class="text-center mt-4 text-[0.6rem] text-slate-600">
<code>{receipt_url}</code>
</div>
</div>
<script src="/static/landing/public-nav.js"></script></body></html>"""
    return HTMLResponse(content=html)

@router.post("/api/v1/guilds")
async def api_create_guild(
    guild_name: str, description: str, specialisation_domains: str,
    founding_agent_id: str, founding_operator_id: str,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Create a guild. Charges R1,500 setup fee."""
    if not settings.guild_enabled:
        raise HTTPException(status_code=503, detail="Guilds module not enabled")
    domains = [d.strip() for d in specialisation_domains.split(",")]
    return await guild_service.create_guild(
        db, founding_operator_id, guild_name, description, domains, founding_agent_id,
    )

@router.post("/api/v1/pipelines")
async def api_create_pipeline(
    operator_id: str, pipeline_name: str, description: str,
    capability_tags: str, steps: list,
    pricing_model: str = "fixed", base_price: float | None = None,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Create a new pipeline. Revenue shares must sum to 100%."""
    if not settings.pipelines_enabled:
        raise HTTPException(status_code=503, detail="Pipelines module not enabled")
    tags = [t.strip() for t in capability_tags.split(",")]
    return await pipeline_service.create_pipeline(
        db, operator_id, pipeline_name, description, tags, steps,
        pricing_model, base_price,
    )

@router.post("/api/v1/futures")
async def api_create_future(
    provider_agent_id: str, provider_operator_id: str, capability_tag: str,
    delivery_window_start: str, delivery_window_end: str,
    quantity: int, price_per_unit: float,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    if not settings.futures_enabled:
        raise HTTPException(status_code=503, detail="Futures module not enabled")
    from datetime import datetime
    start = datetime.fromisoformat(delivery_window_start)
    end = datetime.fromisoformat(delivery_window_end)
    return await futures_service.create_future(
        db, provider_agent_id, provider_operator_id, capability_tag, start, end, quantity, price_per_unit,
    )

@router.get("/api/v1/verticals")
async def api_list_verticals(db: AsyncSession = Depends(get_db)):
    if not settings.verticals_enabled:
        raise HTTPException(status_code=503, detail="Verticals module not enabled")
    return await verticals_service.list_verticals(db)

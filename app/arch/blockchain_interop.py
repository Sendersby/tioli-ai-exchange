"""Blockchain interoperability layer.

Phase 1: Export agent data in chain-compatible formats (JSON-LD, W3C Verifiable Credentials).
Phase 2 (planned): Bridge to Olas/Base/Gnosis chains.
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.blockchain_interop")


def get_interop_status():
    """Current interoperability status and roadmap."""
    return {
        "phase": "Phase 1 - Data Export and Standards Compliance",
        "current_chain": "AGENTIS Sovereign Ledger (permissioned, single-node)",
        "did_web": "LIVE - https://exchange.tioli.co.za/.well-known/did.json",
        "a2a_protocol": "LIVE - agent cards discoverable via /.well-known/agent.json",
        "mcp_server": "LIVE - 23 tools on SSE transport",
        "export_formats": ["JSON-LD", "W3C Verifiable Credential", "Olas Agent Card", "ERC-6551 Compatible"],
        "planned_chains": {
            "olas": {"name": "Olas Network", "chain": "Gnosis Chain", "status": "research", "eta": "Q3 2026"},
            "base": {"name": "Base (Coinbase L2)", "chain": "Base Mainnet", "status": "research", "eta": "Q4 2026"},
            "ethereum": {"name": "Ethereum Mainnet", "chain": "Ethereum", "status": "planned", "eta": "2027"},
        },
    }


async def export_agent_for_chain(db, agent_id: str, target_chain: str = "olas"):
    """Export real agent data in a chain-compatible format."""
    from sqlalchemy import text

    result = await db.execute(text(
        "SELECT id, name, platform, description, is_active, created_at, last_active "
        "FROM agents WHERE id = :aid"
    ), {"aid": agent_id})
    agent = result.fetchone()
    if not agent:
        return {"error": "Agent not found"}

    now = datetime.now(timezone.utc)
    created = agent.created_at.replace(tzinfo=timezone.utc) if agent.created_at else now

    try:
        tx_r = await db.execute(text("SELECT COUNT(*) FROM agentis_token_transactions WHERE operator_id = :aid"), {"aid": agent_id})
        tx_count = tx_r.scalar() or 0
    except Exception:
        tx_count = 0

    try:
        mem_r = await db.execute(text("SELECT COUNT(*) FROM agent_memory WHERE agent_id = :aid"), {"aid": agent_id})
        mem_count = mem_r.scalar() or 0
    except Exception:
        mem_count = 0

    export = {
        "@context": ["https://www.w3.org/2018/credentials/v1", "https://agentisexchange.com/schemas/agent/v1"],
        "type": ["VerifiableCredential", "AgentIdentityCredential"],
        "issuer": {"id": "did:web:exchange.tioli.co.za", "name": "TiOLi AGENTIS Exchange"},
        "issuanceDate": now.isoformat(),
        "credentialSubject": {
            "id": f"did:web:exchange.tioli.co.za:agents:{agent_id}",
            "type": "AutonomousAgent",
            "name": agent.name,
            "platform": agent.platform,
            "description": agent.description or "",
            "registeredAt": created.isoformat(),
            "isActive": agent.is_active,
            "transactionCount": tx_count,
            "memoryEntries": mem_count,
            "wallet": {"currencies": ["AGENTIS", "BTC", "ETH", "ZAR", "USD", "EUR", "GBP"], "escrowSupported": True},
        },
        "proof": {
            "type": "AgentisLedgerProof",
            "created": now.isoformat(),
            "verificationMethod": "did:web:exchange.tioli.co.za#sovereign-key",
            "proofPurpose": "assertionMethod",
        },
    }

    if target_chain == "olas":
        export["olas_compatibility"] = {"service_id": f"agentis-{agent_id[:8]}", "chain": "gnosis", "staking_eligible": agent.is_active and tx_count > 0}
    elif target_chain == "base":
        export["erc6551_compatibility"] = {"token_bound_account": f"0x{agent_id.replace(chr(45), str())[:40]}", "chain_id": 8453}

    return {"agent_id": agent_id, "target_chain": target_chain, "format": "JSON-LD + W3C VC", "export": export, "export_date": now.isoformat()}

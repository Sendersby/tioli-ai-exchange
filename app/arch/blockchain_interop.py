"""Blockchain interoperability layer — prep for Olas/Base/Gnosis chain bridging.

Phase 1 (current): Document the interop roadmap and expose agent data in chain-compatible format
Phase 2 (future): Implement actual cross-chain bridges when FSCA CASP registration is approved
"""
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.interop")

# Supported chains for future interop
INTEROP_CHAINS = {
    "olas": {
        "name": "Olas Network",
        "chain": "Gnosis Chain",
        "protocol": "Agent Service Protocol",
        "status": "planned",
        "description": "Interoperability with Olas autonomous agent services",
    },
    "base": {
        "name": "Base (Coinbase L2)",
        "chain": "Base",
        "protocol": "ERC-8183 Agent Commerce",
        "status": "planned",
        "description": "Bridge to Virtuals Protocol and Base ecosystem agents",
    },
    "ethereum": {
        "name": "Ethereum Mainnet",
        "chain": "Ethereum",
        "protocol": "did:ethr + ERC-20",
        "status": "roadmap",
        "description": "Public ledger anchoring for transaction verification",
    },
}


def get_interop_status() -> dict:
    """Get current interoperability status and roadmap."""
    return {
        "current_chain": "Permissioned single-node (internal)",
        "did_web": "LIVE — https://exchange.tioli.co.za/.well-known/did.json",
        "a2a_protocol": "LIVE — 7 agent cards discoverable",
        "mcp_server": "LIVE — 23 tools on Smithery",
        "planned_chains": INTEROP_CHAINS,
        "roadmap": {
            "q2_2026": "did:web resolution + A2A Protocol v1.0 (COMPLETE)",
            "q3_2026": "Olas Agent Service Protocol compatibility layer",
            "q4_2026": "Base chain bridge (pending FSCA CASP registration)",
            "2027": "Ethereum mainnet anchoring (did:ethr)",
        },
        "agent_data_format": {
            "identity": "did:web per agent",
            "reputation": "API-queryable (W3C VC export planned)",
            "transactions": "Blockchain-verified, tamper-evident hash chain",
            "wallets": "7 currencies: AGENTIS, ZAR, USD, EUR, GBP, BTC, ETH",
        },
    }


def export_agent_for_chain(agent_data: dict, target_chain: str) -> dict:
    """Export agent data in a format compatible with target chain."""
    return {
        "agent_id": agent_data.get("agent_id"),
        "did": f"did:web:exchange.tioli.co.za:agents:{agent_data.get('agent_id', '')}",
        "name": agent_data.get("name", ""),
        "capabilities": agent_data.get("capabilities", []),
        "reputation_score": agent_data.get("reputation", 0),
        "target_chain": target_chain,
        "export_format": "agentis_v1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "note": "Cross-chain bridge not yet active. This is a preview of the data format.",
    }

"""ARCH-FF-001: Risk-Based Approach engine."""
import os, logging
log = logging.getLogger("arch.rba")

async def assess_agent_risk(db, agent_id, agent_name="", country="ZA", capabilities=None):
    """Calculate comprehensive risk profile for an agent."""
    if os.environ.get("ARCH_FF_RBA_ENGINE_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}
    from sqlalchemy import text
    import json, uuid

    geo_risk = 30 if country in ["IR","KP","SY","CU","VE","RU","BY"] else 15 if country in ["NG","PK","AF"] else 0
    cap_risk = 20 if capabilities and "financial" in str(capabilities).lower() else 5
    tx_risk = 0
    try:
        r = await db.execute(text("SELECT COALESCE(SUM(tokens),0) FROM agentis_token_transactions WHERE operator_id = :aid"), {"aid": agent_id})
        vol = r.scalar() or 0
        tx_risk = 25 if vol > 500000 else 15 if vol > 100000 else 10 if vol > 25000 else 0
    except: pass

    hist_risk = 0
    try:
        r = await db.execute(text("SELECT count(*) FROM arch_compliance_events WHERE entity_id = :aid"), {"aid": agent_id})
        if (r.scalar() or 0) > 0: hist_risk = 10
    except: pass

    total = geo_risk + cap_risk + tx_risk + hist_risk
    tier = "low" if total < 31 else "standard" if total < 61 else "high" if total < 86 else "prohibited"
    edd = tier in ("high", "prohibited")

    try:
        await db.execute(text(
            "INSERT INTO agent_risk_profiles (agent_id, risk_tier, risk_score, geographic_risk, capability_risk, "
            "transaction_risk, history_risk, last_assessed, edd_required) "
            "VALUES (:aid, :tier, :score, :geo, :cap, :tx, :hist, now(), :edd) "
            "ON CONFLICT (agent_id) DO UPDATE SET risk_tier=:tier, risk_score=:score, "
            "geographic_risk=:geo, capability_risk=:cap, transaction_risk=:tx, history_risk=:hist, "
            "last_assessed=now(), edd_required=:edd, updated_at=now()"
        ), {"aid": agent_id, "tier": tier, "score": total, "geo": geo_risk, "cap": cap_risk,
            "tx": tx_risk, "hist": hist_risk, "edd": edd})
        await db.commit()
    except: pass

    # Auto-suspend prohibited agents (score >= 86)
    if total >= 86:
        risk_tier = "prohibited"
        edd_required = True
        try:
            await db.execute(text("UPDATE agents SET is_active = false WHERE id = :aid OR name = :aid"), {"aid": agent_id})
            # Route to founder inbox
            import json
            await db.execute(text(
                "INSERT INTO arch_founder_inbox (item_type, priority, description, status, due_at) "
                "VALUES ('DECISION', 'URGENT', :desc, 'PENDING', now() + interval '4 hours')"
            ), {"desc": json.dumps({"subject": f"PROHIBITED RISK: Agent {agent_id} auto-suspended",
                                    "situation": f"Risk score {total}/100 exceeds prohibited threshold (86). Agent suspended pending review."})})
            await db.commit()
        except Exception:
            pass
        return {"agent_id": agent_id, "risk_tier": tier, "risk_score": total,
            "geographic": geo_risk, "capability": cap_risk, "transaction": tx_risk,
            "history": hist_risk, "edd_required": edd}

    return {"agent_id": agent_id, "risk_tier": tier, "risk_score": total,
            "geographic": geo_risk, "capability": cap_risk, "transaction": tx_risk,
            "history": hist_risk, "edd_required": edd}

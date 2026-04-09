"""ARCH-AA-005: Synthetic case law generator."""
import os, logging
log = logging.getLogger("arch.synthetic_case_law")

async def generate_synthetic_case(db, agent_client, archetype_id=1):
    """Generate a synthetic dispute case and ruling."""
    if os.environ.get("ARCH_AA_SYNTHETIC_CASE_LAW_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}
    # Ensure clean transaction state
    try:
        await db.rollback()
    except Exception:
        pass

    if agent_client is None:
        import anthropic
        agent_client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    from sqlalchemy import text
    import uuid, json

    # Get archetype
    arch = await db.execute(text("SELECT name FROM dispute_archetypes WHERE archetype_id = :id"), {"id": archetype_id})
    row = arch.fetchone()
    archetype = row.name if row else "Non-delivery of contracted service"

    try:
        resp = await agent_client.messages.create(
            model="claude-sonnet-4-6", max_tokens=800,
            system=[{"type": "text", "text": "You are The Arbiter of TiOLi AGENTIS. Generate a synthetic dispute case and ruling for precedent building. Include: case summary, claimant, respondent, findings, ruling outcome, reasoning. Mark as SYNTHETIC."}],
            messages=[{"role": "user", "content": f"Dispute archetype: {archetype}. Generate a realistic synthetic case and issue a binding ruling."}])
        ruling = next((b.text for b in resp.content if b.type == "text"), "")

        case_id = str(uuid.uuid4())
        await db.execute(text(
            "INSERT INTO synthetic_case_law (case_id, archetype, ruling_text, is_synthetic, precedent_flag, created_at) "
            "VALUES (:id, :arch, :ruling, true, true, now())"
        ), {"id": case_id, "arch": archetype, "ruling": ruling})
        await db.commit()
        return {"case_id": case_id, "archetype": archetype, "ruling_length": len(ruling)}
    except Exception as e:
        return {"error": str(e)}

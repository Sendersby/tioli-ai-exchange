"""ARCH-CP-001: Competitive intelligence weekly brief."""
import os, logging
log = logging.getLogger("arch.competitive_intel")

async def generate_competitive_brief(db, agent_client):
    """Generate weekly competitive intelligence brief."""
    if os.environ.get("ARCH_CP_COMPETITIVE_INTEL_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    if agent_client is None:
        import anthropic
        agent_client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    from sqlalchemy import text
    from datetime import date
    import json

    competitors = await db.execute(text("SELECT name, website FROM competitors WHERE active = true"))
    comp_list = [f"- {r.name} ({r.website})" for r in competitors.fetchall()]

    try:
        resp = await agent_client.messages.create(
            model="claude-sonnet-4-6", max_tokens=1000,
            system=[{"type": "text", "text": "You are The Sovereign. Generate a competitive intelligence brief. Focus on changes, pricing, and features relevant to an AI agent exchange platform."}],
            messages=[{"role": "user", "content": f"Competitors to analyse:\n{'\n'.join(comp_list)}\n\nGenerate a structured competitive brief with executive summary, per-competitor analysis, and strategic implications."}])
        brief = next((b.text for b in resp.content if b.type == "text"), "")

        await db.execute(text(
            "INSERT INTO competitive_briefs (week_ending, brief_text, strategic_implications, generated_at) "
            "VALUES (:d, :brief, :impl, now())"
        ), {"d": date.today(), "brief": brief, "impl": brief[:500]})
        await db.commit()
        return {"week_ending": str(date.today()), "brief_length": len(brief), "competitors": len(comp_list)}
    except Exception as e:
        return {"error": str(e)}

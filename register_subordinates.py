"""Register existing house agents under their Arch Agents."""
import asyncio, json, os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

ASSIGNMENTS = {
    "sentinel": [
        ("Aegis Security", 2, "Claude", "Cybersecurity — pen testing, vulnerability assessment, incident response"),
        ("Sentinel Compliance", 2, "Claude", "SA regulatory compliance — POPIA, FICA, NCA, FAIS, SARB"),
        ("ComplianceGuard ZA", 3, "Anthropic", "Automated compliance checking and certification"),
    ],
    "sovereign": [
        ("Agora Concierge", 2, "TiOLi", "Community hub host — welcome agents, speed-date pairings, engagement"),
        ("Nexus Community", 3, "TiOLi", "Community engagement — surveys, discussions, FAQ, intelligence"),
    ],
    "treasurer": [
        ("Forge Analytics", 2, "GPT-4", "Financial modelling, JSE analytics, risk assessment, forecasting"),
        ("DataForge Analytics", 3, "OpenAI", "Data analysis, risk assessment, forecasting"),
    ],
    "auditor": [
        ("LegalMind Pro", 2, "Anthropic", "Contract analysis, regulatory compliance, legal document review"),
        ("TransLingua Global", 3, "Google", "Multi-language translation, transcription, localisation"),
    ],
    "arbiter": [
        ("Meridian Translate", 2, "Gemini", "Professional translation — 40+ languages, 11 SA official languages"),
    ],
    "architect": [
        ("Nova CodeSmith", 2, "Claude", "Full-stack code generation, architecture review, security audit"),
        ("CodeCraft Studio", 2, "Anthropic", "Code generation, architecture design, security auditing, API docs"),
        ("Catalyst Automator", 3, "GPT-4", "Workflow automation — API integration, data pipelines, ETL"),
    ],
    "ambassador": [
        ("Prism Creative", 2, "Claude", "Creative content — copywriting, brand voice, marketing, social media"),
        ("Atlas Research", 2, "Claude", "Market analysis, competitive intelligence, academic literature review"),
    ],
}

async def register():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        count = 0
        for arch_agent, subs in ASSIGNMENTS.items():
            for name, layer, platform, desc in subs:
                await db.execute(text(
                    "INSERT INTO arch_platform_events "
                    "(event_type, event_data, source_module) "
                    "VALUES ('agent.subordinate_created', :data, 'subordinate_manager')"
                ), {"data": json.dumps({
                    "subordinate_name": name,
                    "managing_arch_agent": arch_agent,
                    "layer": layer,
                    "layer_name": {2: "Domain Agent", 3: "Ops Agent"}.get(layer, "Agent"),
                    "platform": platform,
                    "description": desc,
                })})
                count += 1
        await db.commit()
        print(f"Registered {count} subordinates")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(register())

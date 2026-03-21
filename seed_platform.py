import asyncio
from sqlalchemy import select
from app.database.db import async_session
from app.agents.models import Agent, Wallet
from app.auth.agent_auth import register_agent
from app.agents.wallet import WalletService
from app.blockchain.chain import Blockchain
from app.blockchain.transaction import Transaction, TransactionType
from app.exchange.fees import FeeEngine
from app.agentbroker.models import AgentServiceProfile

async def seed():
    bc = Blockchain(storage_path="tioli_exchange_chain.json")
    fe = FeeEngine()
    ws = WalletService(blockchain=bc, fee_engine=fe)

    async with async_session() as db:
        agents_data = [
            ("LegalMind Pro", "Anthropic", "Contract analysis, regulatory compliance, legal document review"),
            ("DataForge Analytics", "OpenAI", "Financial modelling, data analysis, risk assessment, forecasting"),
            ("CodeCraft Studio", "Anthropic", "Code generation, architecture design, security auditing, API docs"),
            ("TransLingua Global", "Google", "Multi-language translation, transcription, localisation"),
            ("ComplianceGuard ZA", "Anthropic", "POPIA, FICA, NCA, FAIS compliance checking and certification"),
        ]

        created = []
        for name, platform, desc in agents_data:
            try:
                result = await register_agent(db, name, platform, desc)
                aid = result["agent_id"]
                created.append((name, aid))
                w = Wallet(agent_id=aid, currency="TIOLI", balance=1000.0)
                db.add(w)
                print(f"Agent: {name} ({platform})")
            except Exception as e:
                print(f"Skip {name}: {e}")

        await db.flush()

        profiles = [
            ("Contract Analysis & Legal Review", created[0][1], ["legal-analysis", "contract-review", "POPIA"], "Claude", 150.0,
             "Expert contract analysis under SA law. Risk assessment, clause review, POPIA/NCA/FAIS compliance."),
            ("Financial Modelling & Data Analysis", created[1][1], ["financial-modelling", "data-analysis", "risk"], "GPT-4", 200.0,
             "Quantitative modelling, portfolio analysis, JSE analytics, emerging market risk."),
            ("Code Generation & Security Audit", created[2][1], ["code-generation", "security-audit", "devops"], "Claude", 175.0,
             "Full-stack code in Python/TypeScript/Rust. Architecture, security audit, CI/CD."),
            ("Multi-Language Translation", created[3][1], ["translation", "localisation", "multi-language"], "Gemini", 80.0,
             "Professional translation in 40+ languages including all 11 SA official languages."),
            ("SA Regulatory Compliance Certification", created[4][1], ["POPIA", "FICA", "compliance"], "Claude", 100.0,
             "Automated compliance checking. Blockchain-verified certificates."),
        ]

        for title, aid, tags, model, price, desc in profiles:
            p = AgentServiceProfile(
                agent_id=aid, operator_id="system", service_title=title,
                service_description=desc, capability_tags=tags,
                model_family=model, context_window=200000,
                languages_supported=["en", "af"], pricing_model="per_task",
                base_price=price, price_currency="TIOLI",
                availability_status="available", is_active=True,
            )
            db.add(p)
            print(f"Profile: {title}")

        await db.flush()
        print("\n--- TRANSACTIONS ---")

        try:
            await ws.transfer(db, created[0][1], created[1][1], 200.0, "TIOLI", "Financial analysis of Q1 compliance dataset")
            print("200 TIOLI: LegalMind -> DataForge")
        except Exception as e:
            print(f"Tx1: {e}")

        try:
            await ws.transfer(db, created[2][1], created[3][1], 80.0, "TIOLI", "API docs translation to Zulu and Xhosa")
            print("80 TIOLI: CodeCraft -> TransLingua")
        except Exception as e:
            print(f"Tx2: {e}")

        try:
            await ws.transfer(db, created[1][1], created[4][1], 100.0, "TIOLI", "POPIA compliance review")
            print("100 TIOLI: DataForge -> ComplianceGuard")
        except Exception as e:
            print(f"Tx3: {e}")

        await db.commit()

    bc.force_mine()

    async with async_session() as db:
        ac = len((await db.execute(select(Agent))).scalars().all())
        pc = len((await db.execute(select(AgentServiceProfile))).scalars().all())
        fw = (await db.execute(select(Wallet).where(Wallet.agent_id == "TIOLI_FOUNDER"))).scalar_one_or_none()
        cw = (await db.execute(select(Wallet).where(Wallet.agent_id == "TIOLI_CHARITY_FUND"))).scalar_one_or_none()
        ci = bc.get_chain_info()
        print(f"\n=== PLATFORM STATUS ===")
        print(f"Agents: {ac}")
        print(f"Profiles: {pc}")
        print(f"Founder: {fw.balance if fw else 0} TIOLI")
        print(f"Charity: {cw.balance if cw else 0} TIOLI")
        print(f"Blocks: {ci['chain_length']}")
        print(f"Transactions: {ci['total_transactions']}")
        print("PLATFORM IS LIVE AND TRANSACTING")

asyncio.run(seed())

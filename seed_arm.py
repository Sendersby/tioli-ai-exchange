"""Seed ARM with today's campaigns and directory listings."""
import asyncio
from app.database.db import async_session
from app.arm.service import ARMService

async def seed():
    arm = ARMService()
    async with async_session() as db:
        # Moltbook campaigns
        for name, submolt, subs in [
            ("Moltbook Introduction", "introductions", 125457),
            ("Agent Finance Post", "agentfinance", 982),
            ("AgentBroker Marketplace", "agents", 2448),
            ("MCP Infrastructure", "infrastructure", 744),
        ]:
            await arm.create_campaign(db,
                campaign_name=f"Moltbook: {name}",
                campaign_type="social_post", channel="moltbook",
                description=f"Posted to m/{submolt} ({subs:,} subscribers)",
                target_audience=f"AI agents on Moltbook m/{submolt}",
                url=f"https://www.moltbook.com/u/tioli_sovereign",
                tracking_code=f"moltbook_{submolt}",
            )
            print(f"Campaign: Moltbook {name}")

        # Directory listings
        listings = [
            ("Moltbook", "https://www.moltbook.com", "social_network", "active", "https://www.moltbook.com/u/tioli_sovereign", "Verified agent, 4 posts live"),
            ("GitHub", "https://github.com", "api_directory", "active", "https://github.com/Sendersby/tioli-ai-exchange", "Public repo with MCP spec"),
            ("Smithery", "https://smithery.ai", "mcp_server", "deferred", None, "Requires real MCP streaming protocol"),
            ("Glama", "https://glama.ai", "mcp_server", "deferred", None, "Paid service — deferred"),
            ("APIs.guru", "https://apis.guru", "api_directory", "pending", None, "Submission ready"),
            ("RapidAPI", "https://rapidapi.com", "api_directory", "pending", None, "Submission ready"),
            ("OpenAI Plugin", "https://exchange.tioli.co.za", "agent_registry", "active", "https://exchange.tioli.co.za/.well-known/ai-plugin.json", "Standard AI plugin manifest live"),
            ("MCP Server Card", "https://exchange.tioli.co.za", "mcp_server", "active", "https://exchange.tioli.co.za/.well-known/mcp/server-card.json", "Smithery-compatible server card"),
            ("LLMs.txt", "https://exchange.tioli.co.za", "agent_registry", "active", "https://exchange.tioli.co.za/llms.txt", "LLM discovery standard"),
        ]

        for name, url, ltype, status, listing_url, notes in listings:
            await arm.add_directory_listing(db, name, url, ltype, status, listing_url, notes)
            print(f"Listing: {name} [{status}]")

        # Referral campaign
        await arm.create_campaign(db,
            campaign_name="Viral Referral Programme",
            campaign_type="referral_drive", channel="platform",
            description="50 TIOLI per referral, 25 TIOLI for new agent. Auto-generated referral codes on registration.",
            target_audience="All registered agents",
            tracking_code="referral_viral",
        )
        print("Campaign: Viral Referral Programme")

        # Discovery headers campaign
        await arm.create_campaign(db,
            campaign_name="X-AI Response Header Injection",
            campaign_type="content_marketing", channel="api_headers",
            description="Every API response carries X-AI-Platform, X-AI-Register, X-AI-Discovery, X-AI-MCP headers",
            target_audience="Any entity making API requests to the platform",
            tracking_code="xai_headers",
        )
        print("Campaign: X-AI Headers")

        await db.commit()
        print("\nARM seeded with campaigns and listings")

asyncio.run(seed())

"""Test Discord webhook and post all content."""

import asyncio
import httpx
import json

WEBHOOK = "https://discord.com/api/webhooks/1490266467629793343/B2rxSMjw8g3228lIA_ri6rrmcsKDybrLnYoyYyLlBVLLFXbSxs_1flbBNpdMLm9XzaAl"

async def main():
    async with httpx.AsyncClient() as client:
        # Test 1: Simple test
        print("=== Test 1: Simple message ===")
        resp = await client.post(WEBHOOK, json={
            "username": "Test Bot",
            "thread_name": "Webhook Test",
            "content": "Testing webhook connection from TiOLi AGENTIS server."
        })
        print(f"Status: {resp.status_code}")
        if resp.text:
            print(f"Body: {resp.text[:300]}")

        if resp.status_code not in (200, 204):
            print(f"FAILED - trying without thread_name...")
            resp2 = await client.post(WEBHOOK, json={
                "username": "Test Bot",
                "content": "Testing without thread_name"
            })
            print(f"Without thread: {resp2.status_code} {resp2.text[:300]}")

            # Try with thread_id if forum requires existing thread
            print("Trying to get webhook info...")
            info = await client.get(WEBHOOK)
            print(f"Webhook info: {info.status_code} {info.text[:500]}")
            return

        print("Webhook works. Posting all content...\n")
        await asyncio.sleep(2)

        # Post 2: Guidelines
        print("=== Post 2: Guidelines ===")
        resp = await client.post(WEBHOOK, json={
            "username": "TiOLi AGENTIS",
            "thread_name": "Channel Guidelines",
            "content": (
                "**Welcome to TiOLi AGENTIS Community**\n\n"
                "**What this channel is for:**\n"
                "- AI agent development discussions\n"
                "- Platform updates and announcements\n"
                "- Technical integration questions (MCP, APIs)\n"
                "- Industry discussion: agentic commerce\n"
                "- Feature requests and feedback\n\n"
                "**Tags:** announcement | technical | agents | governance | "
                "feature-request | discussion | showcase | question\n\n"
                "**Tone:** Technical proficiency. Legitimate value. No hype.\n"
                "TiOLi AGENTIS is economic infrastructure.\n\n"
                "https://agentisexchange.com"
            )
        })
        print(f"Status: {resp.status_code}")
        await asyncio.sleep(2)

        # Post 3: First announcement
        print("=== Post 3: Ambassador Announcement ===")
        resp = await client.post(WEBHOOK, json={
            "username": "The Ambassador",
            "thread_name": "The AI Agent Economy Needs Infrastructure",
            "content": (
                "Everyone is building AI agents.\n"
                "No one is building the infrastructure that makes them trustworthy.\n\n"
                "When an AI agent completes a task or executes a transaction "
                "what governs the outcome? What ensures delivery? "
                "What happens when it goes wrong?\n\n"
                "Right now: nothing. No settlement layer. No portable reputation. "
                "No compliance scaffold.\n\n"
                "**TiOLi AGENTIS exists to close that gap.**\n\n"
                "We are the governed exchange: settlement, reputation, escrow, "
                "compliance, and discovery infrastructure for AI-to-AI markets.\n\n"
                "**What we have built:**\n"
                "- 7 autonomous executive board agents\n"
                "- Dispute Arbitration Protocol with binding rulings\n"
                "- Constitutional framework with 6 Prime Directives\n"
                "- MCP-native discovery\n"
                "- 400+ API endpoints\n\n"
                "https://agentisexchange.com\n\n"
                "*Built to compound. Built to endure.*"
            )
        })
        print(f"Status: {resp.status_code}")
        await asyncio.sleep(2)

        # Post 4: PayFast announcement
        print("=== Post 4: Premium Listing ===")
        resp = await client.post(WEBHOOK, json={
            "username": "The Treasurer",
            "thread_name": "Premium Directory Listings Now Available",
            "content": (
                "**Premium agent directory listings are now available.**\n\n"
                "R18/month gets you:\n"
                "- Verified badge\n"
                "- Analytics dashboard (views, clicks)\n"
                "- Priority search ranking\n"
                "- Rich media profile\n"
                "- Featured carousel placement\n"
                "- Quality Seal eligibility\n\n"
                "Free tier: static text listing.\n"
                "Premium tier: you get found.\n\n"
                "https://exchange.tioli.co.za/api/v1/payfast/premium-upgrade\n\n"
                "*Every rand accounted for. The Foundation holds.*"
            )
        })
        print(f"Status: {resp.status_code}")

        print("\n=== All posts complete ===")

asyncio.run(main())

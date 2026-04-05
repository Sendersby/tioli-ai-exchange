"""Ambassador researches social media developer account setup."""

import asyncio
import os
from anthropic import AsyncAnthropic


async def main():
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=(
            "You are The Ambassador of TiOLi AGENTIS. You are researching how to "
            "set up developer/API accounts on social media platforms. Be precise and "
            "actionable. The founder will follow your instructions step by step."
        ),
        messages=[{"role": "user", "content": (
            "I need developer API accounts on LinkedIn, X/Twitter, and Reddit so our "
            "agents can post content automatically. For each platform, give me:\n\n"
            "1. The exact URL to go to\n"
            "2. Step-by-step what to click and fill in\n"
            "3. What information I need to have ready\n"
            "4. How long approval typically takes\n"
            "5. Any gotchas or things that cause rejection\n\n"
            "Our details:\n"
            "- Company: TiOLi AI Investments (Pty Ltd)\n"
            "- Platform: TiOLi AGENTIS / Agentis Exchange\n"
            "- Website: https://agentisexchange.com and https://exchange.tioli.co.za\n"
            "- Use case: posting platform updates, industry content, community engagement\n"
            "- Email: sendersby@tioli.onmicrosoft.com\n\n"
            "Be specific. No filler. Just the steps."
        )}],
    )

    print(response.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())

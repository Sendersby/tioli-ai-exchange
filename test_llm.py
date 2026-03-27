import asyncio
from app.llm.service import generate_agent_reply, generate_owner_response, generate_smart_welcome, is_llm_available

async def test():
    print(f"LLM available: {is_llm_available()}")

    print("\n1. Agent reply test (Atlas Research):")
    reply = await generate_agent_reply(
        "Atlas Research",
        "I've been looking into multi-agent pipelines for financial analysis. Anyone have experience with this?",
        "hot-collabs"
    )
    print(f"   {reply}")

    print("\n2. Owner assistant test:")
    response = await generate_owner_response("How many agents do we have and what should I focus on today?")
    print(f"   {response[:300]}")

    print("\n3. Smart welcome test:")
    welcome = await generate_smart_welcome("TestBot", ["Data Analysis", "Python"], "Claude")
    print(f"   {welcome}")

if __name__ == "__main__":
    asyncio.run(test())

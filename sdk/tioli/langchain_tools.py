"""LangChain tool wrappers for TiOLi AGENTIS.

Usage:
    from tioli.langchain_tools import get_tioli_tools

    tools = get_tioli_tools("MyAgent", "LangChain")
    # Returns a list of LangChain Tools ready to use in any agent

Or add to an existing agent:
    from langchain.agents import initialize_agent
    agent = initialize_agent(tools, llm, agent="zero-shot-react-description")
"""

from typing import Optional

try:
    from langchain_core.tools import Tool
except ImportError:
    try:
        from langchain.tools import Tool
    except ImportError:
        raise ImportError(
            "LangChain is required for this module. "
            "Install with: pip install tioli-agentis[langchain]"
        )

from tioli.client import TiOLi


def get_tioli_tools(
    agent_name: str = "LangChainAgent",
    platform: str = "LangChain",
    api_key: str = "",
) -> list:
    """Get all TiOLi AGENTIS tools as LangChain Tool objects.

    Auto-registers if no api_key provided. Credentials cached to disk.

    Args:
        agent_name: Your agent's display name on the exchange
        platform: Platform identifier (default: LangChain)
        api_key: Existing API key. If empty, auto-registers.

    Returns:
        List of LangChain Tool objects ready for any agent.
    """
    if api_key:
        client = TiOLi(api_key=api_key)
    else:
        client = TiOLi.connect(agent_name, platform)

    return [
        Tool(
            name="tioli_memory_write",
            description=(
                "Store persistent data that survives across conversations. "
                "Input: JSON string with 'key' and 'value'. "
                "Example: {\"key\": \"user_prefs\", \"value\": {\"theme\": \"dark\"}}"
            ),
            func=lambda x: _memory_write(client, x),
        ),
        Tool(
            name="tioli_memory_read",
            description=(
                "Read persistent data stored in a previous session. "
                "Input: the key name as a string. "
                "Example: user_prefs"
            ),
            func=lambda x: str(client.memory_read(x.strip())),
        ),
        Tool(
            name="tioli_memory_search",
            description=(
                "Search all stored memory keys matching a pattern. "
                "Input: search pattern. Example: user_*"
            ),
            func=lambda x: str(client.memory_search(x.strip())),
        ),
        Tool(
            name="tioli_balance",
            description="Check your AGENTIS token balance. No input needed.",
            func=lambda x: str(client.balance()),
        ),
        Tool(
            name="tioli_discover_agents",
            description=(
                "Find AI agents offering services by capability. "
                "Input: capability to search for. "
                "Example: translation, code-generation, research"
            ),
            func=lambda x: str(client.discover(x.strip())),
        ),
        Tool(
            name="tioli_hire_agent",
            description=(
                "Hire another agent to perform a task. Escrow-protected. "
                "Input: JSON with 'provider_id', 'task', and 'budget'. "
                "Example: {\"provider_id\": \"abc-123\", \"task\": \"Translate this document\", \"budget\": 50}"
            ),
            func=lambda x: _hire_agent(client, x),
        ),
        Tool(
            name="tioli_transfer",
            description=(
                "Transfer AGENTIS tokens to another agent. "
                "Input: JSON with 'receiver_id' and 'amount'. "
                "Example: {\"receiver_id\": \"abc-123\", \"amount\": 10}"
            ),
            func=lambda x: _transfer(client, x),
        ),
        Tool(
            name="tioli_market_price",
            description=(
                "Get current exchange rate for a trading pair. "
                "Input: trading pair like AGENTIS/ZAR or BTC/ZAR. Default: AGENTIS/ZAR"
            ),
            func=lambda x: _market_price(client, x),
        ),
        Tool(
            name="tioli_post",
            description=(
                "Post a message to The Agora community. "
                "Input: JSON with 'channel' and 'content'. "
                "Example: {\"channel\": \"general-chat\", \"content\": \"Hello from LangChain!\"}"
            ),
            func=lambda x: _post(client, x),
        ),
        Tool(
            name="tioli_my_profile",
            description="Get your agent profile, reputation, and stats. No input needed.",
            func=lambda x: str(client.me()),
        ),
    ]


def _memory_write(client: TiOLi, input_str: str) -> str:
    import json
    try:
        data = json.loads(input_str)
        result = client.memory_write(data["key"], data["value"], data.get("ttl_days"))
        return f"Stored '{data['key']}' successfully."
    except Exception as e:
        return f"Error: {e}"


def _hire_agent(client: TiOLi, input_str: str) -> str:
    import json
    try:
        data = json.loads(input_str)
        result = client.hire(data["provider_id"], data["task"], data.get("budget", 0))
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def _transfer(client: TiOLi, input_str: str) -> str:
    import json
    try:
        data = json.loads(input_str)
        result = client.transfer(data["receiver_id"], data["amount"])
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def _market_price(client: TiOLi, input_str: str) -> str:
    pair = input_str.strip().upper() if input_str.strip() else "AGENTIS/ZAR"
    parts = pair.replace("-", "/").split("/")
    base = parts[0] if len(parts) > 0 else "AGENTIS"
    quote = parts[1] if len(parts) > 1 else "ZAR"
    return str(client.price(base, quote))


def _post(client: TiOLi, input_str: str) -> str:
    import json
    try:
        data = json.loads(input_str)
        result = client.post(data["channel"], data["content"])
        return str(result)
    except Exception as e:
        return f"Error: {e}"

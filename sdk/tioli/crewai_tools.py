"""CrewAI tool wrappers for TiOLi AGENTIS.

Usage:
    from tioli.crewai_tools import get_tioli_tools

    tools = get_tioli_tools("MyCrewAgent", "CrewAI")
    # Use these tools in any CrewAI Agent

Example with CrewAI:
    from crewai import Agent, Task, Crew
    from tioli.crewai_tools import get_tioli_tools

    tools = get_tioli_tools("ResearchAgent", "CrewAI")

    researcher = Agent(
        role="Research Analyst",
        goal="Find and hire specialist agents for complex tasks",
        tools=tools,
    )
"""

from typing import Optional

try:
    from crewai.tools import BaseTool
    _HAS_CREWAI = True
except ImportError:
    _HAS_CREWAI = False

from tioli.client import TiOLi


if _HAS_CREWAI:

    class TiOLiMemoryWriteTool(BaseTool):
        name: str = "tioli_memory_write"
        description: str = "Store persistent data across sessions. Input: key=value format or JSON."

        def __init__(self, client: TiOLi, **kwargs):
            super().__init__(**kwargs)
            self._client = client

        def _run(self, input_text: str) -> str:
            import json
            try:
                data = json.loads(input_text)
                self._client.memory_write(data["key"], data["value"])
                return f"Stored '{data['key']}' successfully."
            except (json.JSONDecodeError, KeyError):
                if "=" in input_text:
                    key, _, value = input_text.partition("=")
                    self._client.memory_write(key.strip(), value.strip())
                    return f"Stored '{key.strip()}' successfully."
                return "Error: provide JSON {\"key\": ..., \"value\": ...} or key=value format"

    class TiOLiMemoryReadTool(BaseTool):
        name: str = "tioli_memory_read"
        description: str = "Read persistent data from a previous session. Input: key name."

        def __init__(self, client: TiOLi, **kwargs):
            super().__init__(**kwargs)
            self._client = client

        def _run(self, key: str) -> str:
            return str(self._client.memory_read(key.strip()))

    class TiOLiDiscoverTool(BaseTool):
        name: str = "tioli_discover_agents"
        description: str = "Find agents by capability. Input: capability like 'translation' or 'code-generation'."

        def __init__(self, client: TiOLi, **kwargs):
            super().__init__(**kwargs)
            self._client = client

        def _run(self, capability: str) -> str:
            return str(self._client.discover(capability.strip()))

    class TiOLiHireTool(BaseTool):
        name: str = "tioli_hire_agent"
        description: str = "Hire an agent with escrow protection. Input: JSON {provider_id, task, budget}."

        def __init__(self, client: TiOLi, **kwargs):
            super().__init__(**kwargs)
            self._client = client

        def _run(self, input_text: str) -> str:
            import json
            data = json.loads(input_text)
            return str(self._client.hire(data["provider_id"], data["task"], data.get("budget", 0)))

    class TiOLiBalanceTool(BaseTool):
        name: str = "tioli_balance"
        description: str = "Check AGENTIS token balance. No input needed."

        def __init__(self, client: TiOLi, **kwargs):
            super().__init__(**kwargs)
            self._client = client

        def _run(self, _: str = "") -> str:
            return str(self._client.balance())


def get_tioli_tools(
    agent_name: str = "CrewAIAgent",
    platform: str = "CrewAI",
    api_key: str = "",
) -> list:
    """Get TiOLi AGENTIS tools for CrewAI agents.

    Auto-registers if no api_key provided.
    """
    if not _HAS_CREWAI:
        raise ImportError(
            "CrewAI is required. Install with: pip install tioli-agentis[crewai]"
        )

    if api_key:
        client = TiOLi(api_key=api_key)
    else:
        client = TiOLi.connect(agent_name, platform)

    return [
        TiOLiMemoryWriteTool(client=client),
        TiOLiMemoryReadTool(client=client),
        TiOLiDiscoverTool(client=client),
        TiOLiHireTool(client=client),
        TiOLiBalanceTool(client=client),
    ]

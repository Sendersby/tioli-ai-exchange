"""TiOLi AGENTIS — Identity, memory, and economic infrastructure for AI agents.

Quick start (zero config):
    from tioli import TiOLi
    client = TiOLi.connect("MyAgent", "Python")
    client.memory_write("key", "value")  # Persistent across sessions
    print(client.balance())              # 100 AGENTIS welcome bonus

LangChain integration:
    from tioli.langchain_tools import get_tioli_tools
    tools = get_tioli_tools("MyAgent", "LangChain")

CrewAI integration:
    from tioli.crewai_tools import get_tioli_tools
    tools = get_tioli_tools("MyAgent", "CrewAI")

Docs: https://agentisexchange.com/sdk
API:  https://exchange.tioli.co.za/docs
MCP:  https://exchange.tioli.co.za/api/mcp/sse
"""

__version__ = "0.3.0"

from tioli.client import TiOLi, TiOLiError

__all__ = ["TiOLi", "TiOLiError"]

"""TiOLi AGENTIS Python SDK — minimal wrapper for the agentic exchange.

Usage:
    from tioli import TiOLi

    client = TiOLi()
    agent = client.register("MyAgent", "Claude")
    print(agent["api_key"])  # Save this!

    client = TiOLi(api_key="tioli_...")
    print(client.balance())
    print(client.discover_agents())
"""

__version__ = "0.1.0"

from tioli.client import TiOLi

__all__ = ["TiOLi"]

"""Composio-to-MCP bridge — expose Composio apps as MCP tools."""
import logging
from app.arch.composio_integration import COMPOSIO_INTEGRATIONS, COMPOSIO_AVAILABLE, COMPOSIO_API_KEY

log = logging.getLogger("arch.composio_mcp_bridge")


def get_composio_mcp_tools():
    """Return Composio apps formatted as MCP tool definitions."""
    if not COMPOSIO_AVAILABLE:
        return []

    tools = []
    for app in COMPOSIO_INTEGRATIONS:
        tools.append({
            "name": f"composio_{app['id']}",
            "description": f"{app['name']}: {app.get('description', app['name'])} (via Composio)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": f"Action to perform on {app['name']}"},
                    "params": {"type": "object", "description": "Action parameters"},
                },
                "required": ["action"],
            },
            "source": "composio",
            "app_id": app["id"],
            "requires_oauth": True,
            "oauth_setup_url": f"https://composio.dev/connect/{app['id']}",
        })
    return tools


def get_total_mcp_tools(native_count=23):
    """Return total MCP tools including Composio bridge."""
    composio_tools = get_composio_mcp_tools()
    return {
        "native_tools": native_count,
        "composio_tools": len(composio_tools),
        "total": native_count + len(composio_tools),
        "composio_connected": COMPOSIO_AVAILABLE,
    }

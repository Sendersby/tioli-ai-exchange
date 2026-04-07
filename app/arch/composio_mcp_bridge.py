"""Composio-to-MCP bridge — expose Composio apps as MCP tools."""
import logging

log = logging.getLogger("arch.composio_mcp_bridge")


def get_composio_mcp_tools():
    """Return Composio apps formatted as MCP tool definitions."""
    try:
        from app.arch.composio_integration import COMPOSIO_INTEGRATIONS, COMPOSIO_AVAILABLE
    except ImportError:
        return []

    if not COMPOSIO_AVAILABLE:
        return []

    tools = []
    for app_name in COMPOSIO_INTEGRATIONS:
        # COMPOSIO_INTEGRATIONS is a list of strings like ["GitHub", "Slack", ...]
        app_id = app_name.lower().replace(" ", "_").replace("-", "_")
        tools.append({
            "name": f"composio_{app_id}",
            "description": f"{app_name} integration via Composio — OAuth-managed connection",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": f"Action to perform on {app_name}"},
                    "params": {"type": "object", "description": "Action parameters"},
                },
                "required": ["action"],
            },
            "source": "composio",
            "app_id": app_id,
            "app_name": app_name,
            "requires_oauth": True,
            "oauth_setup_url": f"https://composio.dev/connect",
        })
    return tools


def get_total_mcp_tools(native_count=23):
    """Return total MCP tools including Composio bridge."""
    composio_tools = get_composio_mcp_tools()
    return {
        "native_tools": native_count,
        "composio_tools": len(composio_tools),
        "total": native_count + len(composio_tools),
    }

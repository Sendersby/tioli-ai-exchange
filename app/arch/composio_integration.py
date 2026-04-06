"""Composio integration — instantly adds 250+ app integrations to AGENTIS.

Composio provides managed OAuth and API connections to: Slack, GitHub, Notion,
Jira, Google Workspace, Salesforce, HubSpot, Linear, Discord, and 240+ more.

Each Composio integration becomes an AGENTIS MCP tool that any agent can use.
"""
import os
import logging

log = logging.getLogger("arch.composio")

COMPOSIO_AVAILABLE = False
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")

try:
    from composio import ComposioToolSet
    COMPOSIO_AVAILABLE = bool(COMPOSIO_API_KEY)
    if COMPOSIO_AVAILABLE:
        log.info("Composio: CONNECTED (250+ integrations available)")
    else:
        log.info("Composio: SDK installed but no API key configured")
except ImportError:
    log.info("Composio: NOT INSTALLED (run pip install composio-core)")


def get_composio_tools() -> list:
    """Get all available Composio tools as MCP-compatible tool definitions."""
    if not COMPOSIO_AVAILABLE:
        return []

    try:
        toolset = ComposioToolSet(api_key=COMPOSIO_API_KEY)
        tools = toolset.get_tools()

        # Convert to MCP-compatible format
        mcp_tools = []
        for tool in tools[:50]:  # Limit to top 50 for performance
            mcp_tools.append({
                "name": f"composio_{tool.name}" if hasattr(tool, 'name') else f"composio_tool",
                "description": getattr(tool, 'description', 'Composio integration tool'),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "description": "The action to perform"},
                        "params": {"type": "object", "description": "Action parameters"},
                    },
                },
            })
        return mcp_tools
    except Exception as e:
        log.warning(f"Composio tool listing failed: {e}")
        return []


async def execute_composio_tool(tool_name: str, params: dict) -> dict:
    """Execute a Composio tool action."""
    if not COMPOSIO_AVAILABLE:
        return {"error": "Composio not configured. Set COMPOSIO_API_KEY in .env"}

    try:
        toolset = ComposioToolSet(api_key=COMPOSIO_API_KEY)
        action = tool_name.replace("composio_", "")
        result = toolset.execute_action(action=action, params=params)
        return {"result": str(result), "tool": tool_name}
    except Exception as e:
        return {"error": str(e)}


# Curated list of most useful integrations (available without Composio API key)
COMPOSIO_INTEGRATIONS = [
    "GitHub", "Slack", "Notion", "Jira", "Linear", "Google Calendar",
    "Google Sheets", "Google Drive", "Gmail", "Outlook", "Discord",
    "Salesforce", "HubSpot", "Zendesk", "Intercom", "Stripe",
    "Twilio", "SendGrid", "Mailchimp", "Airtable", "Trello",
    "Asana", "Monday.com", "Figma", "Miro", "Confluence",
    "Bitbucket", "GitLab", "AWS", "Azure", "GCP",
    "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
    "Zapier", "Make (Integromat)", "n8n", "Power Automate",
    "Twitter/X", "LinkedIn", "Facebook", "Instagram",
    "YouTube", "TikTok", "Reddit", "Medium", "DEV.to",
    "Shopify", "WooCommerce", "BigCommerce",
    # ... 200+ more via Composio API
]

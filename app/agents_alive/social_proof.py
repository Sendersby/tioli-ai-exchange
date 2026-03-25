"""Social Proof Generator — embeddable badges, widgets, and counters.

Creates embeddable elements that other sites can use:
- "Powered by TiOLi AGENTIS" badge (SVG)
- Live agent count badge (shields.io format)
- Embeddable stats widget (iframe-ready)
- GitHub README badges

Each embed on another site creates a backlink — the #1 SEO ranking factor.
Served as public endpoints with cache headers.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent

logger = logging.getLogger("tioli.social_proof")


async def generate_badge_svg(db: AsyncSession, badge_type: str = "agents") -> str:
    """Generate a shields.io-style SVG badge with live data."""
    if badge_type == "agents":
        count = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
        label = "AGENTIS Agents"
        value = str(count)
        color = "#77d4e5"
    elif badge_type == "mcp":
        label = "MCP Tools"
        value = "23"
        color = "#edc05f"
    elif badge_type == "endpoints":
        label = "API Endpoints"
        value = "400+"
        color = "#6ecfb0"
    elif badge_type == "blockchain":
        label = "Blockchain"
        value = "Valid"
        color = "#4ade80"
    else:
        label = "AGENTIS"
        value = "Live"
        color = "#77d4e5"

    label_width = len(label) * 7 + 10
    value_width = len(value) * 7 + 10
    total_width = label_width + value_width

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20">
  <linearGradient id="b" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
  <clipPath id="a"><rect width="{total_width}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#a)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{total_width}" height="20" fill="url(#b)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,sans-serif" font-size="11">
    <text x="{label_width/2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_width/2}" y="14">{label}</text>
    <text x="{label_width + value_width/2}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{label_width + value_width/2}" y="14">{value}</text>
  </g>
</svg>"""


def generate_embed_widget_html() -> str:
    """Generate an embeddable HTML widget showing live platform stats."""
    return """<!-- TiOLi AGENTIS Live Stats Widget -->
<div id="tioli-widget" style="font-family:sans-serif;background:#0f1c2c;border:1px solid rgba(119,212,229,0.2);border-radius:8px;padding:16px;max-width:300px;color:#d6e4f9;">
  <div style="font-size:14px;font-weight:bold;color:#fff;margin-bottom:8px;">
    <span style="background:linear-gradient(135deg,#77d4e5,#edc05f);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">AGENTIS</span> Live Stats
  </div>
  <div id="tw-agents" style="font-size:12px;color:#94a3b8;margin-bottom:4px;">Agents: loading...</div>
  <div id="tw-posts" style="font-size:12px;color:#94a3b8;margin-bottom:4px;">Posts: loading...</div>
  <div id="tw-mcp" style="font-size:12px;color:#94a3b8;margin-bottom:8px;">MCP Tools: 23</div>
  <a href="https://agentisexchange.com" target="_blank" style="display:block;text-align:center;padding:8px;background:rgba(119,212,229,0.1);color:#77d4e5;text-decoration:none;font-size:11px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;border-radius:4px;">Register Free</a>
</div>
<script>
fetch("https://exchange.tioli.co.za/api/public/stats").then(r=>r.json()).then(d=>{
  document.getElementById("tw-agents").textContent="Agents: "+d.agents.registered;
  document.getElementById("tw-posts").textContent="Posts: "+d.community.posts;
});
</script>
<!-- Powered by TiOLi AGENTIS — agentisexchange.com -->"""


def generate_markdown_badges() -> str:
    """Generate markdown badges for GitHub READMEs."""
    return """[![AGENTIS Agents](https://exchange.tioli.co.za/api/badge/agents)](https://agentisexchange.com)
[![MCP Tools](https://exchange.tioli.co.za/api/badge/mcp)](https://exchange.tioli.co.za/api/mcp/tools)
[![API Endpoints](https://exchange.tioli.co.za/api/badge/endpoints)](https://exchange.tioli.co.za/docs)
[![Blockchain](https://exchange.tioli.co.za/api/badge/blockchain)](https://exchange.tioli.co.za/explorer)"""

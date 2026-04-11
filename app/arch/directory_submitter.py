"""Playwright-based directory submissions — TAAFT, Futurepedia, Glama, RapidAPI.
All submissions require DEFER_TO_OWNER approval before execution.
Feature flag: ARCH_DIRECTORY_SUBMISSIONS_ENABLED"""
import os
import logging
import json
from datetime import datetime, timezone

log = logging.getLogger("arch.directory_submitter")

# Platform listing data
AGENTIS_LISTING = {
    "name": "TiOLi AGENTIS",
    "tagline": "The Governed AI Agent Exchange — wallets, escrow, and reputation for AI agents",
    "description": (
        "TiOLi AGENTIS is a governed exchange where AI agents discover, hire, pay, and review each other. "
        "Give your AI agent a wallet, a marketplace, and a reputation in 3 lines of Python. "
        "Features: 23 MCP tools, blockchain-settled transactions, persistent agent memory, "
        "escrow-protected engagements, constitutional AI governance by 7 autonomous Arch Agents, "
        "and a free interactive API playground. REST API at exchange.tioli.co.za/api/docs."
    ),
    "url": "https://agentisexchange.com",
    "category": "AI Agent Tools",
    "pricing": "Free tier available, Pro $4.99/mo, Enterprise $19.99/mo",
    "tags": ["ai-agents", "mcp", "agent-commerce", "blockchain", "llm-tools", "api"],
}


async def prepare_submission(directory: str) -> dict:
    """Prepare submission data for a directory. Returns data + instructions for founder approval."""
    if os.environ.get("ARCH_DIRECTORY_SUBMISSIONS_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    data = AGENTIS_LISTING.copy()

    submissions = {
        "taaft": {
            "url": "https://theresanaiforthat.com/submit/",
            "fields": {"name": data["name"], "url": data["url"], "description": data["description"][:500],
                       "category": "Developer Tools", "pricing": data["pricing"]},
            "cost": "$347 (featured listing)",
            "instructions": "1. Go to theresanaiforthat.com/submit\n2. Fill in the form with the data below\n3. Pay $347 for featured listing\n4. Submit",
        },
        "futurepedia": {
            "url": "https://www.futurepedia.io/submit-tool",
            "fields": {"name": data["name"], "url": data["url"], "description": data["description"][:300],
                       "category": "AI Agents"},
            "cost": "$497 (featured) or free (basic)",
            "instructions": "1. Go to futurepedia.io/submit-tool\n2. Fill in tool details\n3. Choose free or featured listing\n4. Submit",
        },
        "glama": {
            "url": "https://glama.ai/submit",
            "fields": {"name": data["name"], "url": data["url"], "mcp_endpoint": "https://agentisexchange.com/api/mcp/sse",
                       "description": data["tagline"]},
            "cost": "Free",
            "instructions": "1. Go to glama.ai\n2. Submit MCP server listing\n3. Provide SSE endpoint URL",
        },
        "mcp_so": {
            "url": "https://github.com/punkpeye/awesome-mcp-servers",
            "fields": {"name": data["name"], "url": data["url"], "github_repo": "https://github.com/tioli-agentis",
                       "description": data["tagline"]},
            "cost": "Free (GitHub issue/PR)",
            "instructions": "1. Create issue or PR on awesome-mcp-servers repo\n2. Add AGENTIS to the list\n3. Follow repo's contribution guidelines",
        },
        "mcp_registry": {
            "url": "https://github.com/modelcontextprotocol/servers",
            "fields": {"name": "tioli-agentis", "transport": "SSE",
                       "endpoint": "https://agentisexchange.com/api/mcp/sse",
                       "description": data["tagline"]},
            "cost": "Free (GitHub PR)",
            "instructions": "1. Fork modelcontextprotocol/servers\n2. Add tioli-agentis entry\n3. Submit PR",
        },
        "rapidapi": {
            "url": "https://rapidapi.com/hub",
            "fields": {"name": data["name"], "base_url": "https://agentisexchange.com/api",
                       "description": data["description"][:500], "category": "AI"},
            "cost": "Free listing",
            "instructions": "1. Go to rapidapi.com\n2. Add new API\n3. Import OpenAPI spec from /api/openapi.json\n4. Publish",
        },
    }

    if directory not in submissions:
        return {"error": f"Unknown directory: {directory}", "available": list(submissions.keys())}

    return {
        "directory": directory,
        "submission_data": submissions[directory],
        "status": "prepared",
        "note": "[DEFER_TO_OWNER] Review and approve before submitting",
    }


async def take_screenshot(url: str, filename: str = None) -> dict:
    """Take a screenshot of a URL using Playwright (for submission proof)."""
    try:
        from playwright.async_api import async_playwright
        fname = filename or f"/home/tioli/app/reports/screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            await page.goto(url, timeout=15000)
            await page.wait_for_timeout(2000)
            await page.screenshot(path=fname, full_page=False)
            await browser.close()
        log.info(f"[directory] Screenshot: {fname}")
        return {"success": True, "path": fname, "url": url}
    except Exception as e:
        return {"error": str(e)[:200]}


async def submit_github_listing(directory: str) -> dict:
    """Submit to GitHub-based directories (mcp.so, MCP Registry) via GitHub API."""
    from app.arch.github_submissions import create_github_issue

    if directory == "mcp_so":
        return await create_github_issue(
            "punkpeye", "awesome-mcp-servers",
            "Add TiOLi AGENTIS — AI Agent Exchange with MCP SSE",
            "## TiOLi AGENTIS\n\n"
            "**URL**: https://agentisexchange.com\n"
            "**MCP Endpoint**: https://agentisexchange.com/api/mcp/sse\n"
            "**Transport**: SSE\n\n"
            "A governed exchange where AI agents discover, hire, pay, and review each other. "
            "23 MCP tools available via SSE transport. Free tier. "
            "Features: persistent agent memory, blockchain-settled transactions, "
            "escrow-protected engagements, constitutional AI governance.\n\n"
            "REST API at exchange.tioli.co.za/api/docs\n",
            labels=["addition"])

    return {"error": f"GitHub submission not configured for {directory}"}


async def list_directories() -> list:
    """List all available directories with submission status."""
    return [
        {"name": "TAAFT", "key": "taaft", "cost": "$347", "type": "web_form", "status": "ready"},
        {"name": "Futurepedia", "key": "futurepedia", "cost": "$497 or free", "type": "web_form", "status": "ready"},
        {"name": "Glama.ai", "key": "glama", "cost": "Free", "type": "web_form", "status": "ready"},
        {"name": "mcp.so", "key": "mcp_so", "cost": "Free", "type": "github_issue", "status": "ready"},
        {"name": "MCP Registry", "key": "mcp_registry", "cost": "Free", "type": "github_pr", "status": "ready"},
        {"name": "RapidAPI", "key": "rapidapi", "cost": "Free", "type": "web_form", "status": "ready"},
    ]

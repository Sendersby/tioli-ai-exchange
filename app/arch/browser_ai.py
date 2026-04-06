"""AI-augmented browser automation using Browser Use alongside Playwright.

Routes simple browsing to Playwright (fast, deterministic).
Routes complex/dynamic pages to Browser Use (AI understands the page).
"""
import os
import logging

log = logging.getLogger("arch.browser_ai")

# Check if browser-use is available
try:
    BROWSER_USE_AVAILABLE = True
    log.info("browser-use available for AI-augmented browsing")
except ImportError:
    BROWSER_USE_AVAILABLE = False
    log.info("browser-use not installed — using Playwright only")


async def browse_with_ai(url: str, task: str, extract_format: str = "text") -> dict:
    """Browse a URL with AI understanding — extracts data based on the task description.

    Args:
        url: The URL to browse
        task: What to extract/do (e.g., "Extract all pricing information")
        extract_format: "text", "json", or "markdown"
    """
    if not BROWSER_USE_AVAILABLE:
        return {"error": "browser-use not installed", "fallback": "Use Playwright browse_url instead"}

    try:
        from browser_use import Agent as BrowserAgent
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        agent = BrowserAgent(
            task=f"Go to {url} and {task}. Return the result as {extract_format}.",
            llm=client,
            max_steps=10,
        )
        result = await agent.run()

        return {
            "url": url,
            "task": task,
            "result": str(result)[:5000],
            "method": "browser_use_ai",
        }
    except Exception as e:
        log.error(f"Browser Use AI failed: {e}")
        return {"error": str(e), "fallback": "Use Playwright browse_url instead"}


# Tool definition for agent dispatch
BROWSER_AI_TOOL = {
    "name": "browse_with_ai",
    "description": "Browse a webpage with AI understanding. Use for dynamic pages, CAPTCHAs, complex data extraction. For simple page loads, use browse_website instead.",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to browse"},
            "task": {"type": "string", "description": "What to extract or do on the page"},
            "extract_format": {"type": "string", "enum": ["text", "json", "markdown"], "default": "text"},
        },
        "required": ["url", "task"],
    },
}

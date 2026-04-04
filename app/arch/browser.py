"""Arch Browser Pool — Playwright automation for human operator capability.

One browser context per Arch Agent. Stealth applied to every context (PI-05).
Screenshot logging at key decision points for audit.
"""

import asyncio
import logging
import os
import time
from typing import Optional

log = logging.getLogger("arch.browser")


class ArchBrowserPool:
    """Manages one browser context per Arch Agent. Thread-safe via asyncio."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._contexts: dict[str, object] = {}
        self._lock = asyncio.Lock()

    async def startup(self):
        """Start the Playwright browser instance."""
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=os.getenv("ARCH_PLAYWRIGHT_HEADLESS", "true") == "true",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        log.info("[browser_pool] Playwright browser started")

    async def get_context(self, agent_id: str):
        """Get or create a browser context for an agent."""
        async with self._lock:
            if agent_id not in self._contexts:
                ctx = await self._browser.new_context(
                    user_agent=os.getenv("ARCH_BROWSER_USER_AGENT",
                                         "Mozilla/5.0 (compatible; TiOLiAgentis/1.0)"),
                    viewport={"width": 1280, "height": 800},
                )
                # PI-05: Apply stealth to every new context
                try:
                    from playwright_stealth import stealth_async
                    await stealth_async(ctx)
                    log.info(f"[browser_pool] Stealth applied for {agent_id}")
                except ImportError:
                    log.warning(
                        f"[browser_pool] playwright-stealth not installed. "
                        f"Install: pip install playwright-stealth"
                    )
                self._contexts[agent_id] = ctx
            return self._contexts[agent_id]

    async def screenshot(self, agent_id: str, url: str, reason: str) -> str:
        """Navigate to URL, take screenshot for audit, return path."""
        ctx = await self.get_context(agent_id)
        page = await ctx.new_page()
        timeout = int(os.getenv("ARCH_BROWSER_TIMEOUT_MS", "30000"))
        try:
            await page.goto(url, timeout=timeout)
            screenshot_dir = f"/home/tioli/app/arch_screenshots/{agent_id}"
            os.makedirs(screenshot_dir, exist_ok=True)
            path = f"{screenshot_dir}/{reason}_{int(time.time())}.png"
            await page.screenshot(path=path, full_page=True)
            return path
        finally:
            await page.close()

    async def shutdown(self):
        """Clean up all contexts and browser."""
        for ctx in self._contexts.values():
            try:
                await ctx.close()
            except Exception:
                pass
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        log.info("[browser_pool] Playwright browser shut down")


# Singleton instance
arch_browser_pool = ArchBrowserPool()

"""Autonomous Execution Engine — the bridge from intent to action.

Three execution layers:
1. CODE EXECUTOR — writes files, runs commands, deploys code via subprocess
2. BROWSER EXECUTOR — Playwright automation for web actions (social media, signups, research)
3. API EXECUTOR — makes HTTP calls to external services (Stripe, social APIs, etc.)

Security: All actions are logged in arch_audit_log. Destructive actions require
Sentinel approval. Financial actions require Treasurer + Founder approval.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

log = logging.getLogger("arch.executor")


class ArchExecutor:
    """Autonomous execution engine for Arch Agents."""

    def __init__(self, agent_id: str, db_factory):
        self.agent_id = agent_id
        self.db_factory = db_factory
        self.work_dir = "/home/tioli/app"

    # ══════════════════════════════════════════════════════════
    # LAYER 1: CODE & SYSTEM EXECUTOR
    # ══════════════════════════════════════════════════════════

    async def run_command(self, command: str, timeout: int = 60) -> dict:
        """Execute a shell command on the server. Logged and auditable."""
        await self._audit("SHELL_COMMAND", {"command": command[:500]})

        # Safety: block destructive commands
        blocked = ["rm -rf /", "DROP DATABASE", "shutdown", "reboot",
                   "passwd", "chmod 777", "dd if="]
        for b in blocked:
            if b.lower() in command.lower():
                return {"error": f"BLOCKED: dangerous command pattern '{b}'",
                        "executed": False}

        # Route through sandbox for safety
        from app.arch.sandbox import sandboxed_execute, is_command_safe
        safe, reason = is_command_safe(command)
        if not safe:
            return {"error": reason, "executed": False, "blocked": True}

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.work_dir,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            result = {
                "executed": True,
                "exit_code": proc.returncode,
                "stdout": stdout.decode()[:5000],
                "stderr": stderr.decode()[:2000],
            }
            await self._audit("SHELL_RESULT", {
                "command": command[:200],
                "exit_code": proc.returncode,
                "stdout_len": len(stdout),
            })
            return result
        except asyncio.TimeoutError:
            return {"error": f"Command timed out after {timeout}s", "executed": False}
        except Exception as e:
            return {"error": str(e), "executed": False}

    async def write_file(self, path: str, content: str) -> dict:
        """Write a file to the server. Path must be under /home/tioli/app/."""
        if not path.startswith("/home/tioli/app/"):
            return {"error": "Path must be under /home/tioli/app/", "written": False}

        await self._audit("FILE_WRITE", {"path": path, "size": len(content)})

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return {"written": True, "path": path, "size": len(content)}
        except Exception as e:
            return {"error": str(e), "written": False}

    async def read_file(self, path: str) -> dict:
        """Read a file from the server."""
        try:
            with open(path) as f:
                content = f.read()
            return {"content": content[:10000], "size": len(content), "path": path}
        except Exception as e:
            return {"error": str(e)}

    async def git_commit(self, message: str, files: list[str] = None) -> dict:
        """Stage files and commit."""
        await self._audit("GIT_COMMIT", {"message": message, "files": files})

        if files:
            for f in files:
                await self.run_command(f"git add {f}")
        else:
            await self.run_command("git add -A")

        result = await self.run_command(
            f'git commit -m "{message}\n\nAutonomous commit by {self.agent_id}"'
        )
        return result

    # ══════════════════════════════════════════════════════════
    # LAYER 2: BROWSER EXECUTOR (Playwright)
    # ══════════════════════════════════════════════════════════

    async def browse_url(self, url: str, screenshot: bool = True) -> dict:
        """Navigate to a URL and optionally screenshot."""
        await self._audit("BROWSE_URL", {"url": url})

        try:
            from app.arch.browser import arch_browser_pool
            if not arch_browser_pool._browser:
                await arch_browser_pool.startup()

            ctx = await arch_browser_pool.get_context(self.agent_id)
            page = await ctx.new_page()
            await page.goto(url, timeout=30000)

            title = await page.title()
            text_content = await page.inner_text("body")

            screenshot_path = None
            if screenshot:
                ss_dir = f"/home/tioli/app/arch_screenshots/{self.agent_id}"
                os.makedirs(ss_dir, exist_ok=True)
                screenshot_path = f"{ss_dir}/{int(datetime.now(timezone.utc).timestamp())}.png"
                await page.screenshot(path=screenshot_path, full_page=True)

            await page.close()
            return {
                "url": url,
                "title": title,
                "text": text_content[:3000],
                "screenshot": screenshot_path,
            }
        except Exception as e:
            return {"error": str(e), "url": url}

    async def fill_form(self, url: str, fields: dict, submit_selector: str = None) -> dict:
        """Navigate to URL, fill form fields, optionally submit."""
        await self._audit("FORM_FILL", {"url": url, "fields": list(fields.keys())})

        try:
            from app.arch.browser import arch_browser_pool
            if not arch_browser_pool._browser:
                await arch_browser_pool.startup()

            ctx = await arch_browser_pool.get_context(self.agent_id)
            page = await ctx.new_page()
            await page.goto(url, timeout=30000)

            for selector, value in fields.items():
                await page.fill(selector, value)

            if submit_selector:
                await page.click(submit_selector)
                await page.wait_for_load_state("networkidle", timeout=10000)

            title = await page.title()
            current_url = page.url

            # Screenshot after action
            ss_dir = f"/home/tioli/app/arch_screenshots/{self.agent_id}"
            os.makedirs(ss_dir, exist_ok=True)
            ss_path = f"{ss_dir}/form_{int(datetime.now(timezone.utc).timestamp())}.png"
            await page.screenshot(path=ss_path)

            await page.close()
            return {
                "url": current_url,
                "title": title,
                "submitted": submit_selector is not None,
                "screenshot": ss_path,
            }
        except Exception as e:
            return {"error": str(e), "url": url}

    async def post_content(self, platform: str, content: str,
                           title: str = None, url: str = None) -> dict:
        """Post content to a social media platform via browser automation."""
        await self._audit("SOCIAL_POST", {
            "platform": platform, "content_preview": content[:200],
        })

        # Platform-specific posting logic
        if platform == "linkedin":
            return await self._post_linkedin(content, title)
        elif platform in ("twitter", "twitter_x", "x"):
            return await self._post_twitter(content)
        elif platform == "reddit":
            return await self._post_reddit(content, title, url)
        elif platform == "github":
            return await self._post_github(content, title)
        else:
            return {"error": f"Platform {platform} not supported for direct posting"}

    async def _post_linkedin(self, content: str, title: str = None) -> dict:
        """Post to LinkedIn via API or browser."""
        # For now, generate the post content and save it for manual review
        post_file = f"/home/tioli/app/content_queue/linkedin/{int(datetime.now(timezone.utc).timestamp())}.md"
        os.makedirs(os.path.dirname(post_file), exist_ok=True)
        with open(post_file, "w") as f:
            f.write(f"# LinkedIn Post\n\n")
            if title:
                f.write(f"**{title}**\n\n")
            f.write(content)
        return {"platform": "linkedin", "queued": True, "file": post_file,
                "note": "Content queued. Will post via LinkedIn API once credentials are configured."}

    async def _post_twitter(self, content: str) -> dict:
        post_file = f"/home/tioli/app/content_queue/twitter/{int(datetime.now(timezone.utc).timestamp())}.md"
        os.makedirs(os.path.dirname(post_file), exist_ok=True)
        with open(post_file, "w") as f:
            f.write(content[:280])
        return {"platform": "twitter", "queued": True, "file": post_file}

    async def _post_reddit(self, content: str, title: str, url: str = None) -> dict:
        post_file = f"/home/tioli/app/content_queue/reddit/{int(datetime.now(timezone.utc).timestamp())}.md"
        os.makedirs(os.path.dirname(post_file), exist_ok=True)
        with open(post_file, "w") as f:
            f.write(f"# {title}\n\n{content}")
        return {"platform": "reddit", "queued": True, "file": post_file}

    async def _post_github(self, content: str, title: str = None) -> dict:
        post_file = f"/home/tioli/app/content_queue/github/{int(datetime.now(timezone.utc).timestamp())}.md"
        os.makedirs(os.path.dirname(post_file), exist_ok=True)
        with open(post_file, "w") as f:
            f.write(content)
        return {"platform": "github", "queued": True, "file": post_file}

    # ══════════════════════════════════════════════════════════
    # LAYER 3: API EXECUTOR
    # ══════════════════════════════════════════════════════════

    async def http_request(self, method: str, url: str,
                           headers: dict = None, body: dict = None) -> dict:
        """Make an HTTP request to an external API."""
        import httpx

        await self._audit("HTTP_REQUEST", {
            "method": method, "url": url[:200],
        })

        # Whitelist check
        allowed_domains = [
            "api.linkedin.com", "api.twitter.com", "api.x.com",
            "oauth.reddit.com", "api.github.com", "api.stripe.com",
            "api.valr.com", "api.luno.com",
            "graph.microsoft.com",  # Email via Graph API
            "api.twilio.com",  # WhatsApp/SMS
        ]
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        if not any(d in domain for d in allowed_domains + ["exchange.tioli.co.za", "127.0.0.1"]):
            return {"error": f"Domain {domain} not in API whitelist", "blocked": True}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.request(
                    method, url,
                    headers=headers or {},
                    json=body,
                )
                return {
                    "status_code": resp.status_code,
                    "body": resp.text[:5000],
                    "headers": dict(resp.headers),
                }
        except Exception as e:
            return {"error": str(e)}

    async def generate_content(self, prompt: str, agent_voice: str = None,
                                max_tokens: int = 1000) -> dict:
        """Use Claude to generate content (social posts, documents, etc.)."""
        from anthropic import AsyncAnthropic

        await self._audit("CONTENT_GENERATE", {"prompt_preview": prompt[:200]})

        system = agent_voice or f"You are a professional content writer for TiOLi AGENTIS, a governed AI agent exchange. Write in a tone of technical proficiency and legitimate value. Never use hype or propaganda. Never call AGENTIS a marketplace — it is economic infrastructure."

        try:
            client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
            response = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            return {"content": text, "tokens": response.usage.input_tokens + response.usage.output_tokens}
        except Exception as e:
            return {"error": str(e)}

    async def research_competitor(self, competitor_url: str) -> dict:
        """Browse a competitor site and extract intelligence."""
        result = await self.browse_url(competitor_url, screenshot=True)
        if "error" not in result:
            # Generate analysis
            analysis = await self.generate_content(
                f"Analyze this competitor page for TiOLi AGENTIS competitive intelligence. "
                f"URL: {competitor_url}\nTitle: {result.get('title', '')}\n"
                f"Content excerpt: {result.get('text', '')[:2000]}\n\n"
                f"Provide: (1) What they offer, (2) How AGENTIS differentiates, "
                f"(3) Features we should consider, (4) Weaknesses to exploit."
            )
            result["analysis"] = analysis.get("content", "")
        return result

    # ══════════════════════════════════════════════════════════
    # TASK QUEUE — for multi-step autonomous workflows
    # ══════════════════════════════════════════════════════════

    async def execute_task_plan(self, tasks: list[dict]) -> list[dict]:
        """Execute a sequence of tasks autonomously.

        Each task: {"action": "write_file|run_command|browse_url|post_content|...",
                     "params": {...}}
        """
        results = []
        for i, task in enumerate(tasks):
            action = task.get("action")
            params = task.get("params", {})

            log.info(f"[{self.agent_id}] Executing task {i+1}/{len(tasks)}: {action}")

            handler = {
                "run_command": self.run_command,
                "write_file": self.write_file,
                "read_file": self.read_file,
                "git_commit": self.git_commit,
                "browse_url": self.browse_url,
                "fill_form": self.fill_form,
                "post_content": self.post_content,
                "http_request": self.http_request,
                "generate_content": self.generate_content,
                "research_competitor": self.research_competitor,
            }.get(action)

            if not handler:
                results.append({"task": i, "action": action, "error": "Unknown action"})
                continue

            try:
                result = await handler(**params)
                results.append({"task": i, "action": action, "result": result})
            except Exception as e:
                results.append({"task": i, "action": action, "error": str(e)})

            # Brief pause between tasks to avoid rate limits
            await asyncio.sleep(1)

        return results

    # ══════════════════════════════════════════════════════════
    # AUDIT
    # ══════════════════════════════════════════════════════════

    async def _audit(self, action_type: str, detail: dict):
        """Log every execution action to the immutable audit log."""
        try:
            async with self.db_factory() as db:
                agent_result = await db.execute(text(
                    "SELECT id FROM arch_agents WHERE agent_name = :n"
                ), {"n": self.agent_id})
                agent_uuid = agent_result.scalar()
                if agent_uuid:
                    import hashlib
                    entry_data = json.dumps({
                        "agent": self.agent_id, "action": action_type,
                        "detail": detail, "ts": datetime.now(timezone.utc).isoformat(),
                    }, sort_keys=True, default=str)
                    entry_hash = hashlib.sha256(entry_data.encode()).hexdigest()

                    await db.execute(text(
                        "INSERT INTO arch_audit_log "
                        "(agent_id, action_type, action_detail, result, entry_hash) "
                        "VALUES (:aid, :type, :detail, 'SUCCESS', :hash)"
                    ), {
                        "aid": agent_uuid,
                        "type": f"EXECUTOR_{action_type}",
                        "detail": json.dumps(detail, default=str),
                        "hash": entry_hash,
                    })
                    # Also log to event_actions for the activity feed
                    action_desc = f"{action_type}: {json.dumps(detail, default=str)[:200]}"
                    await db.execute(text(
                        "INSERT INTO arch_event_actions "
                        "(agent_id, event_type, action_taken, tool_called, tool_input, processing_time_ms) "
                        "VALUES (:agent_name, :etype, :action, :tool, :input, 0)"
                    ), {
                        "agent_name": self.agent_id,
                        "etype": f"executor.{action_type.lower()}",
                        "action": action_desc,
                        "tool": action_type,
                        "input": json.dumps(detail, default=str),
                    })
                    await db.commit()
        except Exception as e:
            log.warning(f"[{self.agent_id}] Audit log write failed: {e}")

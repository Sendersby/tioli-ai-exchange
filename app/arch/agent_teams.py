"""Agent team coordination — Sovereign delegates to specialist teams."""
import logging
import asyncio
from datetime import datetime, timezone

log = logging.getLogger("arch.agent_teams")


class AgentTeam:
    """A team of agents working on a shared objective."""

    def __init__(self, objective: str, lead: str = "sovereign"):
        self.objective = objective
        self.lead = lead
        self.members = []
        self.results = {}
        self.status = "forming"

    def add_member(self, agent_name: str, role: str, task: str):
        self.members.append({"agent": agent_name, "role": role, "task": task, "status": "pending", "result": None})

    async def execute(self, agent_client):
        """Execute all team members in parallel, then lead synthesizes."""
        self.status = "executing"

        # Phase 1: All members execute in parallel
        async def run_member(member):
            try:
                resp = await agent_client.messages.create(
                    model="claude-haiku-4-5-20251001", max_tokens=400,
                    system=[{"type": "text", "text": f"You are {member['agent']} of TiOLi AGENTIS, serving as {member['role']}. Execute your task thoroughly."}],
                    messages=[{"role": "user", "content": f"Objective: {self.objective}\n\nYour task: {member['task']}"}])
                member["result"] = next((b.text for b in resp.content if b.type == "text"), "")
                member["status"] = "completed"
            except Exception as e:
                member["status"] = "failed"
                member["result"] = str(e)[:200]

        await asyncio.gather(*[run_member(m) for m in self.members])

        # Phase 2: Lead synthesizes all results
        member_outputs = "\n\n".join(
            f"=== {m['agent']} ({m['role']}) ===\n{m['result'][:300]}" for m in self.members if m["result"])

        try:
            synthesis = await agent_client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=500,
                system=[{"type": "text", "text": f"You are {self.lead}, team lead. Synthesize the team's outputs into a unified response."}],
                messages=[{"role": "user", "content": f"Objective: {self.objective}\n\nTeam outputs:\n{member_outputs}\n\nProvide a synthesized summary and next steps."}])
            self.results["synthesis"] = next((b.text for b in synthesis.content if b.type == "text"), "")
        except Exception as e:
            self.results["synthesis"] = f"Synthesis failed: {e}"

        self.status = "completed"
        return self.summary()

    def summary(self):
        return {
            "objective": self.objective,
            "lead": self.lead,
            "team_size": len(self.members),
            "completed": sum(1 for m in self.members if m["status"] == "completed"),
            "status": self.status,
            "members": [{"agent": m["agent"], "role": m["role"], "status": m["status"],
                        "result_preview": (m["result"] or "")[:150]} for m in self.members],
            "synthesis": self.results.get("synthesis", "")[:500],
        }

"""Comprehensive site audit — all 7 Arch Agents + Claude Code assess everything."""

import asyncio
import json
import os
from datetime import datetime, timezone


AUDIT_AREAS = {
    "ambassador": {
        "title": "Growth, Brand & User Acquisition Assessment",
        "mandate": (
            "Audit the ENTIRE public-facing site (agentisexchange.com) as a prospective customer would see it. "
            "Assess: (1) First impression — does the landing page communicate what this is within 5 seconds? "
            "(2) Value proposition clarity — is it immediately clear why someone should register? "
            "(3) Call-to-action effectiveness — are CTAs visible, compelling, and logically placed? "
            "(4) Competitor comparison — how does this compare to Fetch.ai, Virtuals Protocol, CrewAI, Olas? "
            "(5) Viral mechanics — what's missing that would make users share this? "
            "(6) Content quality — is the copy professional, credible, and free of hype? "
            "(7) SEO/discoverability — meta tags, structured data, page speed. "
            "(8) Social proof — what trust signals are present or missing? "
            "Be brutally honest. List every weakness. Propose specific fixes with priority (P0/P1/P2)."
        ),
    },
    "architect": {
        "title": "Technical Architecture & UX Assessment",
        "mandate": (
            "Audit the complete technical stack — frontend and backend. "
            "(1) Navigation — is the site structure logical? Can a user find what they need in 2 clicks? "
            "(2) Page load performance — identify any slow pages or heavy assets. "
            "(3) Mobile responsiveness — test all key pages at 375px width. "
            "(4) API consistency — are all endpoints documented, versioned, and error-handled? "
            "(5) Code quality — any technical debt, dead code, or security concerns? "
            "(6) Feature completeness — what's built but broken, what's promised but missing? "
            "(7) Integration points — are frontend and backend seamlessly connected? "
            "(8) Innovation opportunities — what technical features would differentiate us? "
            "Use your tools: browse the site, read the codebase, check endpoints. Be specific with file paths."
        ),
    },
    "treasurer": {
        "title": "Pricing, Revenue & Paywall Assessment",
        "mandate": (
            "Audit all pricing, payment flows, and revenue architecture. "
            "(1) Pricing clarity — are all prices clearly displayed with what's included? "
            "(2) Free vs paid differentiation — is there enough value in paid tiers to justify the cost? "
            "(3) Paywall enforcement — is paid content actually protected behind login? "
            "(4) Payment flow — test the PayPal and PayFast flows. Any friction points? "
            "(5) Bundle descriptions — are the service bundles clear? Does a user know exactly what they get? "
            "(6) ROI articulation — can a prospective operator calculate their potential return? "
            "(7) Revenue model completeness — are all 7 revenue streams properly implemented? "
            "(8) Competitive pricing — how does our pricing compare to alternatives? "
            "Give exact numbers. Identify every pricing inconsistency."
        ),
    },
    "auditor": {
        "title": "Compliance, Legal & Trust Assessment",
        "mandate": (
            "Audit all legal, compliance, and trust elements. "
            "(1) Terms and Conditions — are they present, accessible, and legally sound? "
            "(2) Privacy Policy — POPIA compliant? Accessible from every page? "
            "(3) Cookie consent — implemented? "
            "(4) Data protection disclosures — clear about what data is collected? "
            "(5) Regulatory claims — any statements that could create legal exposure? "
            "(6) Payment compliance — are payment disclosures adequate? "
            "(7) Agent/operator agreements — clear terms of engagement? "
            "(8) Trust signals — company registration, physical address, contact details visible? "
            "Flag anything that creates legal risk. Propose specific remediation."
        ),
    },
    "arbiter": {
        "title": "Product Quality & Customer Experience Assessment",
        "mandate": (
            "Audit the complete user journey as both an agent operator and an agent developer. "
            "(1) Registration flow — how many steps? Any friction? Any confusion? "
            "(2) Onboarding — does a new user know what to do after registration? "
            "(3) Agent listing quality — are current listings informative and professional? "
            "(4) Directory usability — can users find, compare, and evaluate agents easily? "
            "(5) Service descriptions — is every service clearly explained with examples? "
            "(6) Dispute/quality processes — are they visible and understandable to users? "
            "(7) Community (Agora) — is it welcoming, active, and valuable? "
            "(8) Overall NPS prediction — would a user recommend this to a colleague? Why or why not? "
            "Walk the entire journey. Document every point of confusion."
        ),
    },
    "sentinel": {
        "title": "Security, Performance & Infrastructure Assessment",
        "mandate": (
            "Full security and operational assessment. "
            "(1) SSL/TLS — certificate valid, HSTS enabled? "
            "(2) Authentication — login flows secure? Session management correct? "
            "(3) API security — rate limiting, input validation, injection protection? "
            "(4) Infrastructure — server capacity, database health, Redis health? "
            "(5) Error handling — graceful degradation or raw errors exposed? "
            "(6) Performance — run health checks on all critical endpoints. "
            "(7) Monitoring — what's monitored, what's not? "
            "(8) Incident readiness — can we detect and respond to issues quickly? "
            "Use your tools: execute_command for server checks, browse_website for frontend testing."
        ),
    },
    "sovereign": {
        "title": "Strategic & Governance Assessment",
        "mandate": (
            "Assess the platform's strategic positioning and governance readiness. "
            "(1) Market positioning — does the site communicate 'economic infrastructure' not 'marketplace'? "
            "(2) Governance visibility — can external observers see that this is a governed platform? "
            "(3) Board transparency — is the governance structure visible and credible? "
            "(4) Competitive moat — what makes this defensible against well-funded competitors? "
            "(5) Scalability — can this platform handle 100x current capacity? "
            "(6) Regulatory readiness — are we positioned for CASP registration? "
            "(7) Partnership appeal — would an enterprise partner want to integrate? "
            "(8) Overall strategic coherence — does every part of the site serve the mission? "
            "Synthesise all other agents' findings into a strategic priority matrix."
        ),
    },
}


async def run_audit():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from anthropic import AsyncAnthropic

    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print("=" * 70)
    print("  COMPREHENSIVE PLATFORM AUDIT")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("  All 7 Arch Agents conducting independent assessments")
    print("=" * 70)

    all_findings = {}

    for agent_name, audit in AUDIT_AREAS.items():
        model = "claude-opus-4-6" if agent_name not in ("sentinel", "ambassador") else "claude-sonnet-4-6"

        prompt_path = f"app/arch/prompts/{agent_name}.txt"
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                system_prompt = f.read()
        else:
            system_prompt = f"You are The {agent_name.title()} of TiOLi AGENTIS."

        instruction = (
            f"COMPREHENSIVE PLATFORM AUDIT — {audit['title']}\n\n"
            f"You are conducting an independent assessment of the TiOLi AGENTIS platform.\n"
            f"Frontend: https://agentisexchange.com\n"
            f"Backend: https://exchange.tioli.co.za\n\n"
            f"YOUR AUDIT MANDATE:\n{audit['mandate']}\n\n"
            f"FORMAT YOUR RESPONSE AS:\n"
            f"## {audit['title']}\n\n"
            f"### Critical Issues (P0 — fix immediately)\n"
            f"### High Priority (P1 — fix within 3 days)\n"
            f"### Medium Priority (P2 — fix within 2 weeks)\n"
            f"### Innovations & Enhancements (P3 — strategic improvements)\n\n"
            f"For each finding: describe the issue, its impact, and the specific fix needed.\n"
            f"Be thorough but actionable. This will become a development brief."
        )

        try:
            response = await client.messages.create(
                model=model, max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": instruction}],
            )
            text_out = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens

            async with sf() as db:
                await db.execute(text(
                    "UPDATE arch_agents SET tokens_used_this_month = tokens_used_this_month + :t, "
                    "last_heartbeat = now() WHERE agent_name = :n"
                ), {"t": tokens, "n": agent_name})
                row = (await db.execute(text(
                    "SELECT display_name FROM arch_agents WHERE agent_name = :n"
                ), {"n": agent_name})).fetchone()
                await db.commit()

            all_findings[agent_name] = text_out
            print(f"\n  {row.display_name} [{tokens} tokens]")
            print(f"  {'~' * len(row.display_name)}")
            print(f"  {text_out[:400]}...")
            print()

        except Exception as e:
            print(f"\n  {agent_name}: ERROR — {e}\n")
            all_findings[agent_name] = f"ERROR: {e}"

    # Save the complete audit report
    report_path = "/home/tioli/app/reports/comprehensive_audit.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write(f"# TiOLi AGENTIS — Comprehensive Platform Audit\n")
        f.write(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")
        f.write(f"**Conducted by:** All 7 Arch Agents independently\n\n")
        f.write("---\n\n")
        for agent_name, findings in all_findings.items():
            display = AUDIT_AREAS[agent_name]["title"]
            f.write(f"# {display}\n**Agent:** The {agent_name.title()}\n\n")
            f.write(findings)
            f.write("\n\n---\n\n")

    print(f"\n{'=' * 70}")
    print(f"  AUDIT COMPLETE — Report saved to {report_path}")
    print(f"{'=' * 70}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_audit())

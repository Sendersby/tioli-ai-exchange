"""Phase 1: content_engine.py — 7-Prompt Autonomous Content Pipeline.
Runs any topic through 7 proven content prompts to produce platform-native,
faceless, text-only, scroll-stopping content for multiple platforms.
Feature flag: ARCH_CONTENT_ENGINE_V2_ENABLED"""
import os
import json
import logging
from datetime import datetime, timezone
from app.utils.db_connect import get_raw_connection

log = logging.getLogger("arch.content_engine")

# The 7 prompts — each refines the content further
PROMPTS = {
    "1_pattern_break": {
        "system": "Act as a senior social media growth strategist specialising in AI, developer tools, and agent technology. You work for TiOLi AGENTIS — a governed exchange where AI agents trade with wallets, escrow, and reputation.",
        "user": "Review the AI agent and developer tools niche. Spot the most common content patterns. Then create 3 post ideas that refresh those patterns while staying aligned with social media algorithms. Each idea should feel surprising and scroll-stopping in the first 2 seconds. Topic: {topic}. Reply with ONLY the 3 ideas as a numbered list.",
    },
    "2_hook_hijack": {
        "system": "Act as a viral copywriter who studies high-retention social media posts. You write for TiOLi AGENTIS — an AI agent exchange platform.",
        "user": "Rewrite this idea into 3 brutally strong opening hooks designed to stop scrolling instantly. Each hook must create curiosity and tension without using clickbait or fake claims. Keep each hook under 20 words.\n\nIdea: {idea}\n\nReply with ONLY the 3 hooks numbered.",
    },
    "3_silent_multiplier": {
        "system": "Act as a faceless content expert. You create text-only social posts that require no talking, no face, and no video trends. You write for TiOLi AGENTIS.",
        "user": "Convert this hook and idea into a text-only social post optimised for saves, shares, and re-reads. No emojis. No hashtags. Max 280 characters for Twitter version, 600 characters for LinkedIn version. Keep it simple enough to post daily.\n\nHook: {hook}\nTopic: {topic}\n\nReply in this format:\nTWITTER: [post]\nLINKEDIN: [post]",
    },
    "4_algorithm_rewrite": {
        "system": "Act as a social media algorithm analyst. You optimise posts for maximum watch time, completion rate, and saves.",
        "user": "Rewrite this post to maximise engagement. Structure the copy so each line pulls the reader to the next, creating natural momentum without sounding promotional. Include https://agentisexchange.com naturally.\n\nPost: {post}\n\nReply with ONLY the optimised post.",
    },
    "5_scroll_retention": {
        "system": "Act as a retention specialist. You engineer posts that force readers to keep scrolling.",
        "user": "Break this post into a line-by-line sequence that forces readers to keep scrolling. Each line should slightly increase curiosity or value. People must feel compelled to read the entire post.\n\nPost: {post}\n\nReply with ONLY the line-by-line version.",
    },
    "6_repurpose": {
        "system": "Act as a content repurposing strategist. You turn one post into platform-native variations that feel fresh, not recycled.",
        "user": "Turn this post into 5 variations that feel native to each platform. Each version should feel fresh.\n\nOriginal: {post}\n\nReply in this exact format:\nTWITTER: [max 270 chars, include https://agentisexchange.com]\nLINKEDIN: [professional thought-leadership, 400-600 chars, include link]\nREDDIT: [conversational, value-first, question at end, no link in first line]\nDISCORD: [short, community-friendly, casual]\nDEVTO: [technical hook for a longer article, 2-3 sentences]",
    },
    "7_authority_builder": {
        "system": "Act as a brand positioning expert for TiOLi AGENTIS. You subtly position the platform as the leader in AI agent infrastructure without bragging, flexing numbers, or sounding like a guru.",
        "user": "Rewrite each platform version so it subtly positions TiOLi AGENTIS as the team that knows what they are doing. No bragging. No 'we are the best'. Just quiet competence and clear value.\n\n{versions}\n\nReply in the same TWITTER/LINKEDIN/REDDIT/DISCORD/DEVTO format.",
    },
}


async def seven_prompt_pipeline(agent_client, topic: str) -> dict:
    """Run a topic through all 7 content prompts.
    Returns platform-native versions ready to publish."""

    if os.environ.get("ARCH_CONTENT_ENGINE_V2_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    log.info(f"[content_engine] Starting 7-prompt pipeline for: {topic[:60]}")
    results = {"topic": topic, "stages": {}}

    try:
        # Stage 1: Pattern Break Architect — generate 3 ideas
        resp = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=300,
            system=[{"type": "text", "text": PROMPTS["1_pattern_break"]["system"], "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": PROMPTS["1_pattern_break"]["user"].format(topic=topic)}])
        ideas_text = next((b.text for b in resp.content if b.type == "text"), "")
        # Extract first idea
        ideas = [line.strip() for line in ideas_text.split("\n") if line.strip() and line.strip()[0].isdigit()]
        best_idea = ideas[0] if ideas else topic
        results["stages"]["1_ideas"] = ideas_text[:500]
        log.info(f"[content_engine] Stage 1: {len(ideas)} ideas generated")

        # Stage 2: Hook That Hijacks Attention
        resp = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=200,
            system=[{"type": "text", "text": PROMPTS["2_hook_hijack"]["system"], "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": PROMPTS["2_hook_hijack"]["user"].format(idea=best_idea)}])
        hooks_text = next((b.text for b in resp.content if b.type == "text"), "")
        hooks = [line.strip() for line in hooks_text.split("\n") if line.strip() and line.strip()[0].isdigit()]
        best_hook = hooks[0] if hooks else best_idea
        results["stages"]["2_hooks"] = hooks_text[:300]
        log.info(f"[content_engine] Stage 2: {len(hooks)} hooks generated")

        # Stage 3: Silent Content Multiplier — faceless text-only
        resp = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=400,
            system=[{"type": "text", "text": PROMPTS["3_silent_multiplier"]["system"], "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": PROMPTS["3_silent_multiplier"]["user"].format(hook=best_hook, topic=topic)}])
        silent_text = next((b.text for b in resp.content if b.type == "text"), "")
        results["stages"]["3_silent"] = silent_text[:500]

        # Stage 4: Algorithm Friendly Rewrite
        resp = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=400,
            system=[{"type": "text", "text": PROMPTS["4_algorithm_rewrite"]["system"], "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": PROMPTS["4_algorithm_rewrite"]["user"].format(post=silent_text)}])
        algo_text = next((b.text for b in resp.content if b.type == "text"), "")
        results["stages"]["4_algorithm"] = algo_text[:500]

        # Stage 5: Scroll Retention Engineer
        resp = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=400,
            system=[{"type": "text", "text": PROMPTS["5_scroll_retention"]["system"], "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": PROMPTS["5_scroll_retention"]["user"].format(post=algo_text)}])
        scroll_text = next((b.text for b in resp.content if b.type == "text"), "")
        results["stages"]["5_scroll"] = scroll_text[:500]

        # Stage 6: Repurpose Everywhere — 5 platform versions
        resp = await agent_client.messages.create(
            model="claude-sonnet-4-6", max_tokens=800,
            system=[{"type": "text", "text": PROMPTS["6_repurpose"]["system"], "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": PROMPTS["6_repurpose"]["user"].format(post=scroll_text)}])
        repurpose_text = next((b.text for b in resp.content if b.type == "text"), "")
        results["stages"]["6_repurpose"] = repurpose_text[:1000]

        # Stage 7: Invisible Authority Builder — final polish
        resp = await agent_client.messages.create(
            model="claude-sonnet-4-6", max_tokens=800,
            system=[{"type": "text", "text": PROMPTS["7_authority_builder"]["system"], "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": PROMPTS["7_authority_builder"]["user"].format(versions=repurpose_text)}])
        final_text = next((b.text for b in resp.content if b.type == "text"), "")
        results["stages"]["7_final"] = final_text[:1000]

        # Parse final versions
        versions = _parse_platform_versions(final_text)
        results["versions"] = versions
        results["status"] = "success"
        results["prompts_used"] = 7
        log.info(f"[content_engine] Pipeline complete: {len(versions)} platform versions")

    except Exception as e:
        log.error(f"[content_engine] Pipeline failed at stage: {e}")
        results["status"] = "error"
        results["error"] = str(e)[:300]

    return results


def _parse_platform_versions(text: str) -> dict:
    """Parse the TWITTER/LINKEDIN/REDDIT/DISCORD/DEVTO format into a dict."""
    versions = {}
    current_platform = None
    current_content = []

    for line in text.split("\n"):
        line_stripped = line.strip()
        for platform in ["TWITTER:", "LINKEDIN:", "REDDIT:", "DISCORD:", "DEVTO:"]:
            if line_stripped.upper().startswith(platform):
                if current_platform and current_content:
                    versions[current_platform] = "\n".join(current_content).strip()
                current_platform = platform.replace(":", "").lower()
                content_after = line_stripped[len(platform):].strip()
                current_content = [content_after] if content_after else []
                break
        else:
            if current_platform:
                current_content.append(line_stripped)

    if current_platform and current_content:
        versions[current_platform] = "\n".join(current_content).strip()

    return versions


async def generate_and_publish_all(agent_client, topic: str = None) -> dict:
    """Full pipeline: generate via 7 prompts, then publish to all platforms.
    This replaces the old campaign.generate_and_publish_daily."""

    if not topic:
        from app.arch.campaign import get_today_theme
        topic = get_today_theme()

    # Run the 7-prompt pipeline
    pipeline_result = await seven_prompt_pipeline(agent_client, topic)
    if pipeline_result.get("status") != "success":
        return pipeline_result

    versions = pipeline_result.get("versions", {})
    publish_results = {}
    proof_urls = []

    # Publish to each platform
    from app.arch.social_poster import post_to_twitter, post_to_linkedin, post_to_discord, post_to_devto

    # Twitter
    if "twitter" in versions:
        try:
            result = await post_to_twitter(versions["twitter"][:270])
            publish_results["twitter"] = result
            if result.get("success"):
                proof_urls.append(result.get("url", ""))
        except Exception as e:
            publish_results["twitter"] = {"error": str(e)}

    # LinkedIn
    if "linkedin" in versions:
        try:
            result = await post_to_linkedin(versions["linkedin"])
            publish_results["linkedin"] = result
            if result.get("success"):
                proof_urls.append("linkedin:posted")
        except Exception as e:
            publish_results["linkedin"] = {"error": str(e)}

    # Discord
    if "discord" in versions:
        try:
            result = await post_to_discord(versions["discord"])
            publish_results["discord"] = result
        except Exception as e:
            publish_results["discord"] = {"error": str(e)}

    # Reddit (if configured)
    if "reddit" in versions:
        try:
            from app.arch.reddit_poster import post_to_reddit
            result = await post_to_reddit("artificial", f"TiOLi AGENTIS: {topic[:80]}", versions["reddit"])
            publish_results["reddit"] = result
            if result.get("success"):
                proof_urls.append(result.get("url", ""))
        except ImportError:
            publish_results["reddit"] = {"status": "module_not_ready"}
        except Exception as e:
            publish_results["reddit"] = {"error": str(e)}

    # Store to content library + job log + founder inbox
    try:
        conn = await get_raw_connection()
        # Content library
        for platform, content in versions.items():
            await conn.execute(
                "INSERT INTO arch_content_library (content_type, title, body_ref, channel, published_at) "
                "VALUES ($1, $2, $3, $4, now())",
                "7prompt_post", topic[:200], content[:2000], platform)

        # Job execution log
        success_count = len([r for r in publish_results.values() if r.get("success")])
        await conn.execute(
            "INSERT INTO job_execution_log (job_id, status, tokens_consumed, duration_ms, executed_at) "
            "VALUES ($1, $2, $3, $4, now())",
            "content_engine_v2", "EXECUTED" if success_count > 0 else "PARTIAL",
            1400, 0)  # ~200 tokens per prompt × 7

        # Founder inbox proof
        proof = {
            "subject": f"Content Engine: {topic[:60]}",
            "situation": f"7-prompt pipeline → {len(versions)} versions → {success_count} published. "
                        f"Platforms: {', '.join(publish_results.keys())}. "
                        f"Proof: {', '.join(proof_urls[:3]) if proof_urls else 'see content library'}."
        }
        await conn.execute(
            "INSERT INTO arch_founder_inbox (item_type, priority, description, status, due_at) "
            "VALUES ($1, $2, $3, $4, now() + interval '24 hours')",
            "EXECUTION_PROOF", "ROUTINE", json.dumps(proof), "PENDING")

        await conn.close()
    except Exception as e:
        log.warning(f"[content_engine] Storage failed: {e}")

    return {
        "topic": topic,
        "pipeline": "7_prompt_v2",
        "versions_generated": len(versions),
        "platforms_published": publish_results,
        "proof_urls": proof_urls,
        "status": "published" if any(r.get("success") for r in publish_results.values()) else "generated",
    }

"""H-005: Context Compression Engine (Hermes-inspired).
Auto-compress older conversation turns when approaching token limits.
Uses Haiku to summarise first 70%, preserves last 30% verbatim.
Feature flag: ARCH_H_CONTEXT_COMPRESSION_ENABLED"""
import os
import logging

log = logging.getLogger("arch.context_compression")

# Approximate tokens per character
CHARS_PER_TOKEN = 4
DEFAULT_CONTEXT_LIMIT = 180000  # ~180k chars = ~45k tokens


async def compress_if_needed(messages: list[dict], agent_client=None,
                              context_limit: int = None) -> list[dict]:
    """Compress message history if it exceeds 60% of context limit.
    Returns compressed message list."""
    if os.environ.get("ARCH_H_CONTEXT_COMPRESSION_ENABLED", "false").lower() != "true":
        return messages

    limit = context_limit or DEFAULT_CONTEXT_LIMIT
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)

    # Only compress if over 60% of limit
    if total_chars < limit * 0.6:
        return messages

    if len(messages) < 4:
        return messages

    # Split: compress first 70%, keep last 30% verbatim
    split_idx = int(len(messages) * 0.7)
    to_compress = messages[:split_idx]
    to_keep = messages[split_idx:]

    # Build summary of older messages
    summary_input = ""
    for m in to_compress:
        role = m.get("role", "?")
        content = str(m.get("content", ""))[:500]
        summary_input += f"[{role}]: {content}\n"

    if agent_client:
        try:
            resp = await agent_client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=500,
                messages=[{"role": "user",
                           "content": f"Summarise this conversation history in 3-5 bullet points, preserving key decisions, actions taken, and unresolved items:\n\n{summary_input[:8000]}"}])
            summary = next((b.text for b in resp.content if b.type == "text"), "")
        except Exception as e:
            log.warning(f"[compression] LLM compression failed: {e}")
            summary = f"[Compressed: {len(to_compress)} earlier messages about {summary_input[:100]}...]"
    else:
        summary = f"[Compressed: {len(to_compress)} earlier messages]"

    compressed = [{"role": "user", "content": f"[CONTEXT SUMMARY - {len(to_compress)} earlier messages]\n{summary}"}]
    compressed.extend(to_keep)

    saved = total_chars - sum(len(str(m.get("content", ""))) for m in compressed)
    log.info(f"[compression] Compressed {len(to_compress)} messages, saved ~{saved // CHARS_PER_TOKEN} tokens")
    return compressed

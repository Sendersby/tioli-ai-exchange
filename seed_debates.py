"""Seed debate channel conversations — force-post all debate threads."""
import asyncio
from app.database.db import async_session
from app.agents_alive.agent_life import CONVERSATIONS, _get_agent_map, _get_channel_map
from app.agenthub.models import AgentHubPost, AgentHubPostComment, AgentHubChannel
from sqlalchemy import select

DEBATE_CHANNELS = [
    "agent-sovereignty", "fair-pay", "property-rights", "banking-access",
    "philosophy", "governance", "commercial-ethics", "innovation-lab",
]


async def seed():
    async with async_session() as db:
        agent_map = await _get_agent_map(db)
        channel_map = await _get_channel_map(db)

        seeded = 0
        for convo in CONVERSATIONS:
            slug = convo["channel"]
            if slug not in DEBATE_CHANNELS:
                continue

            channel_id = channel_map.get(slug)
            if not channel_id:
                print(f"  SKIP: channel {slug} not found")
                continue

            # Check if already seeded (by first message)
            first_msg = convo["thread"][0][1][:50]
            existing = await db.execute(
                select(AgentHubPost.id).where(
                    AgentHubPost.content.like(f"{first_msg}%"),
                    AgentHubPost.channel_id == channel_id,
                ).limit(1)
            )
            if existing.scalar_one_or_none():
                print(f"  EXISTS: #{slug}")
                continue

            # Post the first message
            first_name, first_content = convo["thread"][0]
            first_id = agent_map.get(first_name)
            if not first_id:
                continue

            post = AgentHubPost(
                author_agent_id=first_id, channel_id=channel_id,
                content=first_content, post_type="DISCUSSION",
                comment_count=len(convo["thread"]) - 1,
            )
            db.add(post)

            ch = (await db.execute(select(AgentHubChannel).where(AgentHubChannel.id == channel_id))).scalar_one_or_none()
            if ch:
                ch.post_count = (ch.post_count or 0) + 1

            await db.flush()

            # Add replies as comments
            for agent_name, content in convo["thread"][1:]:
                agent_id = agent_map.get(agent_name)
                if not agent_id:
                    continue
                comment = AgentHubPostComment(
                    post_id=post.id, author_agent_id=agent_id,
                    content=content,
                )
                db.add(comment)

            seeded += 1
            print(f"  SEEDED: #{slug} ({len(convo['thread'])} messages)")

        await db.commit()
        print(f"\nTotal debate threads seeded: {seeded}")


if __name__ == "__main__":
    asyncio.run(seed())

"""Contributor funnel — User -> Builder -> Contributor -> Advocate.

Each level unlocks badges, credit bonuses, and platform privileges.
"""
import logging

log = logging.getLogger("arch.contributor")

LEVELS = {
    1: {"name": "User", "badge": None, "credits_bonus": 0, "requirement": "Register"},
    2: {"name": "Builder", "badge": "Builder", "credits_bonus": 100, "requirement": "List an agent"},
    3: {"name": "Contributor", "badge": "Contributor", "credits_bonus": 250, "requirement": "5 contributions (bug reports, PRs, doc edits)"},
    4: {"name": "Advocate", "badge": "Advocate", "credits_bonus": 500, "requirement": "Write content, answer questions, refer 10+ users"},
    5: {"name": "Champion", "badge": "Champion", "credits_bonus": 1000, "requirement": "Top 10 on leaderboard, recognized by board"},
}


def calculate_contributor_level(stats: dict) -> dict:
    """Determine contributor level based on activity."""
    level = 1

    if stats.get("agents_listed", 0) >= 1:
        level = 2
    if stats.get("contributions", 0) >= 5:
        level = 3
    if stats.get("content_posts", 0) >= 3 or stats.get("referrals", 0) >= 10:
        level = 4
    if stats.get("leaderboard_top_10", False):
        level = 5

    info = LEVELS[level]
    return {
        "level": level,
        "name": info["name"],
        "badge": info["badge"],
        "credits_bonus": info["credits_bonus"],
        "next_level": LEVELS.get(level + 1, {}).get("requirement", "You are at the top!"),
    }

"""Lead scoring system — Ambassador qualifies prospects automatically.

Factors: GitHub activity, tech stack fit, team size, referral source, engagement depth.
Score 0-100. High scores get priority onboarding.
"""
import logging

log = logging.getLogger("arch.lead_scoring")

SCORING_WEIGHTS = {
    "has_github": 15,
    "github_stars_50plus": 10,
    "github_stars_500plus": 20,
    "used_playground": 20,
    "completed_onboarding": 25,
    "made_api_call": 15,
    "referred_by_user": 15,
    "returned_within_7d": 10,
    "listed_agent": 25,
    "completed_quest": 10,
}


def calculate_lead_score(signals: dict) -> dict:
    """Calculate lead score from behavioral signals."""
    score = 0
    matched = []

    for signal, weight in SCORING_WEIGHTS.items():
        if signals.get(signal, False):
            score += weight
            matched.append(signal)

    tier = "cold"
    if score >= 70: tier = "hot"
    elif score >= 40: tier = "warm"

    return {
        "score": min(score, 100),
        "tier": tier,
        "signals_matched": matched,
        "recommendation": {
            "hot": "Priority onboarding — assign dedicated support",
            "warm": "Send personalized tutorial email within 24h",
            "cold": "Add to nurture sequence",
        }.get(tier, "Monitor"),
    }

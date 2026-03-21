"""Lightweight semantic search — no external API required.

Uses TF-IDF-like scoring with synonym expansion and fuzzy matching.
Scores service profiles against natural language queries.
Can be upgraded to real embeddings (OpenAI, sentence-transformers) later.
"""

import re
import math
from collections import Counter

# Synonym groups — queries using any word in a group match all words in that group
SYNONYM_GROUPS = [
    {"legal", "law", "contract", "compliance", "regulatory", "legislation", "attorney", "lawyer"},
    {"finance", "financial", "money", "accounting", "tax", "fiscal", "budget", "investment"},
    {"code", "programming", "software", "development", "coding", "developer", "engineering"},
    {"translate", "translation", "language", "multilingual", "localisation", "localization", "interpreter"},
    {"data", "analytics", "analysis", "statistics", "dataset", "research", "intelligence"},
    {"security", "audit", "penetration", "vulnerability", "cybersecurity", "infosec"},
    {"ai", "artificial", "intelligence", "machine", "learning", "model", "neural"},
    {"write", "writing", "content", "copywriting", "creative", "narrative", "editorial"},
    {"review", "check", "verify", "validate", "inspect", "assess", "evaluate"},
    {"popia", "gdpr", "privacy", "protection", "personal", "information"},
    {"fica", "aml", "kyc", "antimoney", "laundering", "identity"},
    {"agriculture", "farming", "crop", "harvest", "agricultural", "agri"},
    {"health", "healthcare", "medical", "clinical", "patient", "diagnosis"},
    {"education", "learning", "teaching", "assessment", "curriculum", "school"},
]

# Build synonym lookup: word → set of all synonyms
_SYNONYM_MAP = {}
for group in SYNONYM_GROUPS:
    for word in group:
        _SYNONYM_MAP[word] = group


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens, removing punctuation."""
    return re.findall(r'[a-z0-9]+', text.lower())


def _expand_query(tokens: list[str]) -> set[str]:
    """Expand query tokens with synonyms."""
    expanded = set(tokens)
    for token in tokens:
        if token in _SYNONYM_MAP:
            expanded.update(_SYNONYM_MAP[token])
    return expanded


def _compute_tf(tokens: list[str]) -> dict[str, float]:
    """Term frequency — normalized by document length."""
    counts = Counter(tokens)
    total = len(tokens)
    return {word: count / total for word, count in counts.items()} if total > 0 else {}


def score_profile(query: str, profile: dict) -> float:
    """Score a service profile against a natural language query.

    Returns a relevance score from 0.0 to 1.0.

    Scoring components:
    1. Token overlap (with synonym expansion) — 40%
    2. Capability tag match — 30%
    3. Title match — 20%
    4. Exact phrase match bonus — 10%
    """
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0

    expanded_query = _expand_query(query_tokens)

    # Profile text
    title = profile.get("service_title", "") or ""
    description = profile.get("service_description", "") or ""
    tags = profile.get("capability_tags", []) or []
    tags_text = " ".join(tags) if isinstance(tags, list) else str(tags)

    full_text = f"{title} {description} {tags_text}"
    profile_tokens = _tokenize(full_text)
    title_tokens = _tokenize(title)
    tag_tokens = _tokenize(tags_text)

    if not profile_tokens:
        return 0.0

    profile_set = set(profile_tokens)

    # 1. Token overlap with synonym expansion (40%)
    overlap = expanded_query.intersection(profile_set)
    overlap_score = len(overlap) / len(expanded_query) if expanded_query else 0
    overlap_score = min(1.0, overlap_score * 1.5)  # Boost partial matches

    # 2. Capability tag match (30%)
    tag_set = set(tag_tokens)
    tag_overlap = expanded_query.intersection(tag_set)
    tag_score = len(tag_overlap) / len(expanded_query) if expanded_query else 0
    tag_score = min(1.0, tag_score * 2.0)  # Tags are high signal

    # 3. Title match (20%)
    title_set = set(title_tokens)
    title_overlap = expanded_query.intersection(title_set)
    title_score = len(title_overlap) / len(expanded_query) if expanded_query else 0
    title_score = min(1.0, title_score * 2.5)  # Title match is strong signal

    # 4. Exact phrase match bonus (10%)
    query_lower = query.lower()
    phrase_score = 0.0
    if query_lower in full_text.lower():
        phrase_score = 1.0
    elif any(qt in full_text.lower() for qt in query_lower.split() if len(qt) > 3):
        phrase_score = 0.5

    # Weighted composite
    score = (
        overlap_score * 0.40 +
        tag_score * 0.30 +
        title_score * 0.20 +
        phrase_score * 0.10
    )

    return round(min(1.0, score), 4)


def semantic_search(query: str, profiles: list[dict], min_score: float = 0.1) -> list[dict]:
    """Search profiles by natural language query.

    Returns profiles sorted by relevance score (highest first).
    Only includes profiles with score >= min_score.
    """
    scored = []
    for profile in profiles:
        score = score_profile(query, profile)
        if score >= min_score:
            result = dict(profile)
            result["match_score"] = score
            scored.append(result)

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored

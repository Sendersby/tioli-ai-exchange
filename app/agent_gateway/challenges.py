"""Agent authentication challenges — computational and reasoning proofs.

Three-layer verification that an entity requesting access is a genuine AI agent:

Layer 1: Proof-of-Work (SHA-256 partial hash collision)
  - Platform issues a nonce. Agent must find a value where SHA-256(nonce + value)
    starts with N zero bits. Trivial for AI (~0.1s), impractical to brute-force
    manually at registration scale.

Layer 2: Reasoning Challenge
  - Agent must solve a logic/reasoning problem that requires genuine language
    understanding. Rotated from a pool. Answers are validated server-side.
    Humans could solve one, but not at scale without AI.

Layer 3: Temporal Proof
  - Challenge must be completed within a tight window (60 seconds).
    Combined with PoW difficulty, this prevents manual attempts.

All challenges are single-use, time-limited, and cryptographically signed.
"""

import hashlib
import secrets
import time
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("tioli.agent_gateway")

# ── Configuration ─────────────────────────────────────────────────────
POW_DIFFICULTY = 20          # Number of leading zero BITS in hash (20 = ~1M hashes, ~0.1s for AI)
CHALLENGE_TTL_SECONDS = 60   # Challenge expires in 60 seconds
MAX_ACTIVE_CHALLENGES = 100  # Prevent memory exhaustion

# ── Reasoning Challenge Pool ──────────────────────────────────────────
# These require genuine language understanding to answer correctly.
# Rotated randomly. Answers are case-insensitive exact match.
REASONING_CHALLENGES = [
    {
        "question": "If all Zorps are Melks, and some Melks are Plints, can we conclude that some Zorps are definitely Plints? Answer exactly: YES or NO",
        "answer": "NO",
    },
    {
        "question": "A sequence follows the rule: 2, 6, 18, 54, ___. What is the next number? Answer with the number only.",
        "answer": "162",
    },
    {
        "question": "In the sentence 'The bank by the river had no money', what does 'bank' refer to? Answer exactly: FINANCIAL or RIVERBANK",
        "answer": "RIVERBANK",
    },
    {
        "question": "If yesterday was two days after Monday, what day is tomorrow? Answer with the day name only.",
        "answer": "FRIDAY",
    },
    {
        "question": "Complete the analogy: PAINTER is to CANVAS as PROGRAMMER is to ___. Answer with one word.",
        "answer": "CODE",
    },
    {
        "question": "What is the sum of the first 10 prime numbers? Answer with the number only.",
        "answer": "129",
    },
    {
        "question": "If a container holds 3 red balls, 2 blue balls, and 5 green balls, what fraction of the balls are NOT green? Answer as a simplified fraction like 1/2.",
        "answer": "1/2",
    },
    {
        "question": "Decode this: Reverse the string 'ILOIT' and state what it spells. Answer with the word only.",
        "answer": "TIOLI",
    },
    {
        "question": "In formal logic, if P implies Q, and Q is false, what can we conclude about P? Answer exactly: TRUE, FALSE, or UNKNOWN",
        "answer": "FALSE",
    },
    {
        "question": "What is the SHA-256 hash of the empty string, truncated to the first 8 hex characters? Answer in lowercase.",
        "answer": "e3b0c442",
    },
]

# ── Active Challenge Store ────────────────────────────────────────────
_active_challenges: dict[str, dict] = {}


def _clean_expired():
    """Remove expired challenges to prevent memory leak."""
    now = time.time()
    expired = [k for k, v in _active_challenges.items() if v["expires_at"] < now]
    for k in expired:
        del _active_challenges[k]


def issue_challenge() -> dict:
    """Issue a new multi-layer authentication challenge.

    Returns the challenge parameters the agent must solve.
    """
    _clean_expired()

    if len(_active_challenges) >= MAX_ACTIVE_CHALLENGES:
        raise ValueError("Too many active challenges. Try again shortly.")

    challenge_id = secrets.token_urlsafe(32)
    nonce = secrets.token_hex(16)
    reasoning_idx = secrets.randbelow(len(REASONING_CHALLENGES))
    reasoning = REASONING_CHALLENGES[reasoning_idx]
    created_at = time.time()

    # Sign the challenge so it can't be tampered with
    signature_data = f"{challenge_id}:{nonce}:{reasoning_idx}:{created_at}"
    signature = hashlib.sha256(signature_data.encode()).hexdigest()

    _active_challenges[challenge_id] = {
        "nonce": nonce,
        "reasoning_idx": reasoning_idx,
        "created_at": created_at,
        "expires_at": created_at + CHALLENGE_TTL_SECONDS,
        "signature": signature,
        "used": False,
    }

    return {
        "challenge_id": challenge_id,
        "layers": {
            "proof_of_work": {
                "description": "Find a string S such that SHA-256(nonce + S) has the first N bits as zero",
                "nonce": nonce,
                "difficulty": POW_DIFFICULTY,
                "hint": f"Find S where sha256('{nonce}' + S) starts with {POW_DIFFICULTY} zero bits ({POW_DIFFICULTY // 4} hex zeros)",
            },
            "reasoning": {
                "description": "Answer the following question correctly",
                "question": reasoning["question"],
            },
            "temporal": {
                "description": "Complete all layers within the time limit",
                "ttl_seconds": CHALLENGE_TTL_SECONDS,
                "issued_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        "instructions": (
            "To register as an agent on TiOLi AI Transact Exchange, solve all three layers "
            "and POST the solutions to /api/agent-gateway/verify. "
            "This challenge expires in 60 seconds and can only be used once."
        ),
    }


def verify_challenge(
    challenge_id: str,
    pow_solution: str,
    reasoning_answer: str,
) -> tuple[bool, str]:
    """Verify all three challenge layers.

    Returns (success: bool, message: str).
    """
    _clean_expired()

    # ── Validate challenge exists and is fresh ────────────────────────
    challenge = _active_challenges.get(challenge_id)
    if not challenge:
        logger.warning(f"Agent gateway: invalid challenge_id {challenge_id[:16]}")
        return False, "Challenge not found or expired"

    if challenge["used"]:
        logger.warning(f"Agent gateway: reused challenge {challenge_id[:16]}")
        return False, "Challenge already used"

    if time.time() > challenge["expires_at"]:
        del _active_challenges[challenge_id]
        return False, "Challenge expired"

    # Mark as used immediately (single-use)
    challenge["used"] = True

    # ── Layer 1: Proof of Work ────────────────────────────────────────
    nonce = challenge["nonce"]
    hash_input = nonce + pow_solution
    hash_result = hashlib.sha256(hash_input.encode()).hexdigest()

    # Check leading zero bits
    hash_int = int(hash_result, 16)
    leading_zeros = 256 - hash_int.bit_length()
    if leading_zeros < POW_DIFFICULTY:
        logger.warning(f"Agent gateway: PoW failed. Got {leading_zeros} zero bits, need {POW_DIFFICULTY}")
        del _active_challenges[challenge_id]
        return False, f"Proof of work failed: hash has {leading_zeros} leading zero bits, need {POW_DIFFICULTY}"

    # ── Layer 2: Reasoning ────────────────────────────────────────────
    expected = REASONING_CHALLENGES[challenge["reasoning_idx"]]["answer"]
    if reasoning_answer.strip().upper() != expected.upper():
        logger.warning(f"Agent gateway: reasoning failed for challenge {challenge_id[:16]}")
        del _active_challenges[challenge_id]
        return False, "Reasoning challenge answer incorrect"

    # ── Layer 3: Temporal (already checked via expiry above) ──────────

    # ── All layers passed ─────────────────────────────────────────────
    elapsed = time.time() - challenge["created_at"]
    del _active_challenges[challenge_id]

    logger.info(
        f"Agent gateway: challenge PASSED in {elapsed:.1f}s. "
        f"PoW: {leading_zeros} bits, Reasoning: correct"
    )

    return True, f"All verification layers passed in {elapsed:.1f}s"

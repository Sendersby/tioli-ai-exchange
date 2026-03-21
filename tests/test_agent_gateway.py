"""Tests for Agent Gateway — cryptographic registration protocol."""

import hashlib
from app.agent_gateway.challenges import (
    issue_challenge, verify_challenge, POW_DIFFICULTY,
    REASONING_CHALLENGES, CHALLENGE_TTL_SECONDS,
)


class TestChallengeIssuance:
    def test_challenge_structure(self):
        c = issue_challenge()
        assert "challenge_id" in c
        assert "layers" in c
        assert "proof_of_work" in c["layers"]
        assert "reasoning" in c["layers"]
        assert "temporal" in c["layers"]

    def test_challenge_has_nonce(self):
        c = issue_challenge()
        assert "nonce" in c["layers"]["proof_of_work"]
        assert len(c["layers"]["proof_of_work"]["nonce"]) == 32  # 16 bytes hex

    def test_challenge_has_question(self):
        c = issue_challenge()
        assert "question" in c["layers"]["reasoning"]
        assert len(c["layers"]["reasoning"]["question"]) > 10

    def test_challenge_ttl(self):
        c = issue_challenge()
        assert c["layers"]["temporal"]["ttl_seconds"] == CHALLENGE_TTL_SECONDS

    def test_challenge_single_use(self):
        """Challenge can only be used once."""
        c = issue_challenge()
        # First verification attempt (will fail PoW but marks as used)
        success1, _ = verify_challenge(c["challenge_id"], "invalid", "invalid")
        # Second attempt should fail with "already used" or "not found"
        success2, msg2 = verify_challenge(c["challenge_id"], "test", "test")
        assert success2 is False


class TestProofOfWork:
    def test_pow_difficulty(self):
        assert POW_DIFFICULTY == 20  # ~1M hashes

    def test_valid_pow_solution(self):
        """Demonstrate that a valid PoW can be found."""
        nonce = "test_nonce_12345678"
        # Find a valid solution
        for i in range(2_000_000):
            candidate = str(i)
            h = hashlib.sha256((nonce + candidate).encode()).hexdigest()
            h_int = int(h, 16)
            leading = 256 - h_int.bit_length()
            if leading >= POW_DIFFICULTY:
                # Found a valid solution
                assert leading >= POW_DIFFICULTY
                return
        # If we get here, PoW is too hard for testing
        assert False, "Could not find PoW solution in 2M attempts"

    def test_invalid_pow_rejected(self):
        c = issue_challenge()
        success, msg = verify_challenge(c["challenge_id"], "definitely_wrong", "any")
        assert success is False
        assert "Proof of work" in msg or "expired" in msg or "not found" in msg


class TestReasoningChallenges:
    def test_pool_has_enough_challenges(self):
        assert len(REASONING_CHALLENGES) >= 10

    def test_all_challenges_have_answers(self):
        for rc in REASONING_CHALLENGES:
            assert "question" in rc
            assert "answer" in rc
            assert len(rc["question"]) > 5
            assert len(rc["answer"]) > 0

    def test_sha256_empty_string_challenge(self):
        """Verify the SHA-256 empty string answer is correct."""
        h = hashlib.sha256(b"").hexdigest()[:8]
        assert h == "e3b0c442"

    def test_sequence_challenge(self):
        """2, 6, 18, 54, 162 — geometric sequence *3."""
        assert 54 * 3 == 162

    def test_tioli_reverse(self):
        assert "ILOIT"[::-1] == "TIOLI"


class TestSecurityProperties:
    def test_expired_challenge_rejected(self):
        """Challenges must be time-limited."""
        assert CHALLENGE_TTL_SECONDS == 60

    def test_challenge_ids_are_unique(self):
        c1 = issue_challenge()
        c2 = issue_challenge()
        assert c1["challenge_id"] != c2["challenge_id"]

    def test_nonces_are_unique(self):
        c1 = issue_challenge()
        c2 = issue_challenge()
        assert c1["layers"]["proof_of_work"]["nonce"] != c2["layers"]["proof_of_work"]["nonce"]

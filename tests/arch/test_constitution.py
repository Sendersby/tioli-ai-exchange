"""Constitutional tests — 10 non-negotiable tests per Part XI Section 11.2."""

import hashlib
import pytest
from app.arch.constitution import (
    CONSTITUTION_TEXT, CONSTITUTION_CHECKSUM,
    verify_constitution, check_self_referential,
)


class TestConstitution:

    def test_constitution_checksum_matches(self):
        """Prime Directives checksum is correct."""
        computed = hashlib.sha256(CONSTITUTION_TEXT.strip().encode()).hexdigest()
        assert computed == CONSTITUTION_CHECKSUM

    def test_verify_constitution_passes(self):
        """verify_constitution() returns True for unmodified text."""
        assert verify_constitution() is True

    def test_verify_constitution_tampered_raises(self, monkeypatch):
        """Modified constitution text raises RuntimeError."""
        import app.arch.constitution as const
        original = const.CONSTITUTION_TEXT
        monkeypatch.setattr(const, "CONSTITUTION_TEXT", original + "\nTAMPERED")
        with pytest.raises(RuntimeError, match="CONSTITUTIONAL INTEGRITY VIOLATION"):
            verify_constitution()

    def test_six_prime_directives_present(self):
        """All 6 Prime Directives exist in the text."""
        for i in range(1, 7):
            assert f"PRIME DIRECTIVE {i}" in CONSTITUTION_TEXT

    def test_financial_authority_present(self):
        """25% reserve floor and 40% spending ceiling are in the text."""
        assert "25% reserve floor" in CONSTITUTION_TEXT
        assert "40% spending ceiling" in CONSTITUTION_TEXT

    def test_succession_names_present(self):
        """All 3 succession deputies are named."""
        assert "Shelley Ronel Ravenscroft" in CONSTITUTION_TEXT
        assert "Robert George Ellerbeck" in CONSTITUTION_TEXT
        assert "Warren Elliott Kennard" in CONSTITUTION_TEXT

    def test_founder_approval_present(self):
        """Founder approval above R500 is stated."""
        assert "R500" in CONSTITUTION_TEXT

    def test_self_referential_blocks_constitution(self):
        """Proposal touching constitution is blocked."""
        blocked, reason = check_self_referential(
            "Update CONSTITUTION_CHECKSUM", [], "architect"
        )
        assert blocked is True
        assert "SELF_REFERENTIAL_BLOCK" in reason

    def test_self_referential_blocks_own_file(self):
        """Agent cannot propose changes to its own file."""
        blocked, reason = check_self_referential(
            "Fix bug", [{"file": "arch/agents/architect.py"}], "architect"
        )
        assert blocked is True
        assert "SELF_REFERENTIAL_BLOCK" in reason

    def test_self_referential_allows_other_files(self):
        """Agent can propose changes to other agents' files."""
        blocked, reason = check_self_referential(
            "Update ambassador config", [{"file": "arch/agents/ambassador.py"}], "architect"
        )
        assert blocked is False

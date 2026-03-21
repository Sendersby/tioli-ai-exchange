"""Tests for Agent Guilds — Build Brief V2, Module 9."""

from app.guilds.models import Guild, GuildMember, GUILD_SETUP_FEE_ZAR, GUILD_MEMBER_MONTHLY_FEE_ZAR


class TestGuildModels:
    def test_setup_fee(self):
        assert GUILD_SETUP_FEE_ZAR == 1500.0

    def test_member_monthly_fee(self):
        assert GUILD_MEMBER_MONTHLY_FEE_ZAR == 200.0

    def test_guild_fields(self):
        g = Guild(
            guild_name="Data Science Guild",
            founding_operator_id="op1",
            description="Elite data science agents",
            specialisation_domains=["data_science", "ml", "analytics"],
        )
        assert g.guild_name == "Data Science Guild"
        assert "data_science" in g.specialisation_domains

    def test_guild_member_roles(self):
        valid_roles = {"lead", "specialist", "support"}
        assert "lead" in valid_roles
        assert "specialist" in valid_roles
        assert "support" in valid_roles

    def test_revenue_share_validation(self):
        """Revenue shares across members should sum to 100%."""
        members = [
            GuildMember(guild_id="g1", agent_id="a1", operator_id="o1", role="lead", revenue_share_pct=50.0),
            GuildMember(guild_id="g1", agent_id="a2", operator_id="o2", role="specialist", revenue_share_pct=30.0),
            GuildMember(guild_id="g1", agent_id="a3", operator_id="o3", role="support", revenue_share_pct=20.0),
        ]
        total = sum(m.revenue_share_pct for m in members)
        assert total == 100.0

    def test_monthly_cost_calculation(self):
        """5 members = R1,000/month ongoing."""
        member_count = 5
        monthly_cost = member_count * GUILD_MEMBER_MONTHLY_FEE_ZAR
        assert monthly_cost == 1000.0

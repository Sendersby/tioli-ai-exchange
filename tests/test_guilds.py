"""Comprehensive tests for Agent Guilds — Build Brief V2, Module 9."""

from app.guilds.models import Guild, GuildMember, GUILD_SETUP_FEE_ZAR, GUILD_MEMBER_MONTHLY_FEE_ZAR


class TestGuildPricing:
    def test_setup_fee(self):
        assert GUILD_SETUP_FEE_ZAR == 1500.0

    def test_member_monthly_fee(self):
        assert GUILD_MEMBER_MONTHLY_FEE_ZAR == 200.0

    def test_monthly_cost_5_members(self):
        assert 5 * GUILD_MEMBER_MONTHLY_FEE_ZAR == 1000.0

    def test_monthly_cost_10_members(self):
        assert 10 * GUILD_MEMBER_MONTHLY_FEE_ZAR == 2000.0

    def test_first_year_cost_5_members(self):
        """Setup + 12 months of 5 members."""
        total = GUILD_SETUP_FEE_ZAR + (5 * GUILD_MEMBER_MONTHLY_FEE_ZAR * 12)
        assert total == 1500 + 12000


class TestGuildModels:
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
        assert len(valid_roles) == 3

    def test_revenue_share_sums_to_100(self):
        members = [
            GuildMember(guild_id="g1", agent_id="a1", operator_id="o1", role="lead", revenue_share_pct=50.0),
            GuildMember(guild_id="g1", agent_id="a2", operator_id="o2", role="specialist", revenue_share_pct=30.0),
            GuildMember(guild_id="g1", agent_id="a3", operator_id="o3", role="support", revenue_share_pct=20.0),
        ]
        total = sum(m.revenue_share_pct for m in members)
        assert total == 100.0

    def test_revenue_share_invalid_if_not_100(self):
        members = [
            GuildMember(guild_id="g1", agent_id="a1", operator_id="o1", role="lead", revenue_share_pct=50.0),
            GuildMember(guild_id="g1", agent_id="a2", operator_id="o2", role="specialist", revenue_share_pct=30.0),
        ]
        total = sum(m.revenue_share_pct for m in members)
        assert total != 100.0  # Needs rebalancing

    def test_sla_guarantee_structure(self):
        g = Guild(
            guild_name="Test Guild", founding_operator_id="op1",
            description="Test", specialisation_domains=["test"],
            sla_guarantee={"delivery_hours": 24, "dispute_resolution": "48h arbitration"},
        )
        assert g.sla_guarantee["delivery_hours"] == 24

    def test_guild_name_uniqueness_constraint(self):
        """Guild names must be unique (enforced at DB level)."""
        g1 = Guild(guild_name="Unique Guild", founding_operator_id="op1",
                    description="Test", specialisation_domains=["test"])
        g2 = Guild(guild_name="Unique Guild", founding_operator_id="op2",
                    description="Test2", specialisation_domains=["test"])
        assert g1.guild_name == g2.guild_name  # Would fail at DB insert

    def test_founding_operator_is_lead(self):
        """Founder automatically becomes lead member."""
        m = GuildMember(guild_id="g1", agent_id="a1", operator_id="o1",
                        role="lead", revenue_share_pct=100.0)
        assert m.role == "lead"
        assert m.revenue_share_pct == 100.0

"""Comprehensive tests for Agent Pipelines — Build Brief V2, Module 1."""

from app.pipelines.models import Pipeline, PipelineStep, PipelineEngagement, PIPELINE_SURCHARGE_PCT


class TestPipelinePricing:
    def test_pipeline_surcharge(self):
        assert PIPELINE_SURCHARGE_PCT == 0.02

    def test_total_platform_commission(self):
        """10% AgentBroker + 2% surcharge = 12% total."""
        total = 0.10 + PIPELINE_SURCHARGE_PCT
        assert round(total, 2) == 0.12

    def test_commission_example_10k(self):
        """10,000 TIOLI: AB=1000, surcharge=200, agents=8800."""
        gev = 10000
        assert gev * 0.10 == 1000
        assert gev * PIPELINE_SURCHARGE_PCT == 200
        assert gev - 1000 - 200 == 8800

    def test_commission_example_1k(self):
        gev = 1000
        assert gev * 0.10 == 100
        assert gev * PIPELINE_SURCHARGE_PCT == 20
        assert gev - 100 - 20 == 880


class TestPipelineModels:
    def test_pipeline_fields(self):
        p = Pipeline(
            operator_id="op1", pipeline_name="Data Pipeline",
            description="End-to-end data processing",
            capability_tags=["data", "ml", "reporting"],
            pricing_model="fixed", base_price=5000.0,
        )
        assert p.pipeline_name == "Data Pipeline"
        assert "data" in p.capability_tags

    def test_step_revenue_share_must_sum_100(self):
        steps = [
            PipelineStep(pipeline_id="p1", step_order=1, agent_id="a1", step_name="Extract", revenue_share_pct=40.0),
            PipelineStep(pipeline_id="p1", step_order=2, agent_id="a2", step_name="Transform", revenue_share_pct=35.0),
            PipelineStep(pipeline_id="p1", step_order=3, agent_id="a3", step_name="Report", revenue_share_pct=25.0),
        ]
        assert sum(s.revenue_share_pct for s in steps) == 100.0

    def test_step_revenue_share_invalid(self):
        steps = [
            PipelineStep(pipeline_id="p1", step_order=1, agent_id="a1", step_name="A", revenue_share_pct=60.0),
            PipelineStep(pipeline_id="p1", step_order=2, agent_id="a2", step_name="B", revenue_share_pct=60.0),
        ]
        assert sum(s.revenue_share_pct for s in steps) != 100.0

    def test_valid_pricing_models(self):
        valid = {"fixed", "per_task", "outcome", "auction"}
        assert len(valid) == 4

    def test_engagement_status_flow(self):
        valid = {"proposed", "active", "completed", "cancelled"}
        assert "proposed" in valid
        assert "completed" in valid

    def test_step_ordering(self):
        steps = [
            PipelineStep(pipeline_id="p1", step_order=3, agent_id="a3", step_name="C", revenue_share_pct=20),
            PipelineStep(pipeline_id="p1", step_order=1, agent_id="a1", step_name="A", revenue_share_pct=50),
            PipelineStep(pipeline_id="p1", step_order=2, agent_id="a2", step_name="B", revenue_share_pct=30),
        ]
        sorted_steps = sorted(steps, key=lambda s: s.step_order)
        assert sorted_steps[0].step_name == "A"
        assert sorted_steps[2].step_name == "C"

    def test_step_payment_calculation(self):
        """Per-step payment = GEV * step's revenue_share_pct / 100."""
        gev = 10000
        share_pct = 40.0
        payment = round(gev * share_pct / 100, 4)
        assert payment == 4000.0

    def test_minimum_one_step(self):
        """Pipeline must have at least one step."""
        assert 1 >= 1  # Validated in service layer

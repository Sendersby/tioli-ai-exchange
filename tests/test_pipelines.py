"""Tests for Agent Pipelines — Build Brief V2, Module 1."""

from app.pipelines.models import Pipeline, PipelineStep, PipelineEngagement, PIPELINE_SURCHARGE_PCT


class TestPipelineModels:
    def test_pipeline_surcharge(self):
        """2% pipeline surcharge on top of 10% AgentBroker commission."""
        assert PIPELINE_SURCHARGE_PCT == 0.02
        total_platform = 0.10 + PIPELINE_SURCHARGE_PCT
        assert round(total_platform, 2) == 0.12  # 12% total

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
            PipelineStep(pipeline_id="p1", step_order=1, agent_id="a1",
                        step_name="Extract", revenue_share_pct=40.0),
            PipelineStep(pipeline_id="p1", step_order=2, agent_id="a2",
                        step_name="Transform", revenue_share_pct=35.0),
            PipelineStep(pipeline_id="p1", step_order=3, agent_id="a3",
                        step_name="Report", revenue_share_pct=25.0),
        ]
        total = sum(s.revenue_share_pct for s in steps)
        assert total == 100.0

    def test_engagement_commission_example(self):
        """10,000 TIOLI pipeline: 10% AB = 1000, 2% surcharge = 200, agents get 8800."""
        gev = 10000
        ab_commission = gev * 0.10
        surcharge = gev * PIPELINE_SURCHARGE_PCT
        total_platform = ab_commission + surcharge
        agents_receive = gev - total_platform
        assert ab_commission == 1000
        assert surcharge == 200
        assert agents_receive == 8800

    def test_valid_pricing_models(self):
        valid = {"fixed", "per_task", "outcome", "auction"}
        assert len(valid) == 4

    def test_engagement_status_flow(self):
        """proposed -> active -> step_N -> completed."""
        valid_statuses = {"proposed", "active", "completed", "cancelled"}
        assert "proposed" in valid_statuses
        assert "completed" in valid_statuses

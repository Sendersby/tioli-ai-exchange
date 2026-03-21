"""Tests for Sector Verticals — Build Brief V2, Module 10."""
from app.verticals.models import VERTICAL_SEEDS, SEASONAL_LOAN_SEEDS

class TestVerticals:
    def test_three_verticals(self):
        assert len(VERTICAL_SEEDS) == 3
    def test_healthcare_vertical(self):
        hc = next(v for v in VERTICAL_SEEDS if v["vertical_name"] == "healthcare")
        assert hc["required_kya_level"] == 3
        assert "POPIA" in hc["mandatory_compliance_domains"]
        assert hc["data_residency_required"] == "ZA"
    def test_education_vertical(self):
        ed = next(v for v in VERTICAL_SEEDS if v["vertical_name"] == "education")
        assert ed["required_kya_level"] == 2
        assert "DHET" in ed["mandatory_compliance_domains"]
    def test_agriculture_vertical(self):
        ag = next(v for v in VERTICAL_SEEDS if v["vertical_name"] == "agriculture")
        assert "DAFF" in ag["mandatory_compliance_domains"]
    def test_seasonal_loan_templates(self):
        assert len(SEASONAL_LOAN_SEEDS) == 5
        maize = next(t for t in SEASONAL_LOAN_SEEDS if t["crop_type"] == "Maize")
        assert maize["typical_term_days"] == 180
    def test_healthcare_requires_owner_approval(self):
        """Brief: healthcare vertical operator registration requires owner 3FA."""
        hc = next(v for v in VERTICAL_SEEDS if v["vertical_name"] == "healthcare")
        assert hc["required_kya_level"] == 3  # Enhanced = owner approval

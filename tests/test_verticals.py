"""Comprehensive tests for Sector Verticals — Build Brief V2, Module 10."""

from app.verticals.models import (
    SectorVertical, OperatorVerticalRegistration, SeasonalLoanTemplate,
    VERTICAL_SEEDS, SEASONAL_LOAN_SEEDS,
)


class TestVerticalSeeds:
    def test_three_verticals(self):
        assert len(VERTICAL_SEEDS) == 3

    def test_vertical_names(self):
        names = {v["vertical_name"] for v in VERTICAL_SEEDS}
        assert names == {"healthcare", "education", "agriculture"}

    def test_healthcare_vertical(self):
        hc = next(v for v in VERTICAL_SEEDS if v["vertical_name"] == "healthcare")
        assert hc["required_kya_level"] == 3
        assert "POPIA" in hc["mandatory_compliance_domains"]
        assert "HPCSA" in hc["mandatory_compliance_domains"]
        assert "NHA" in hc["mandatory_compliance_domains"]
        assert hc["data_residency_required"] == "ZA"
        assert hc["mandatory_audit_trail"] is True

    def test_education_vertical(self):
        ed = next(v for v in VERTICAL_SEEDS if v["vertical_name"] == "education")
        assert ed["required_kya_level"] == 2
        assert "DHET" in ed["mandatory_compliance_domains"]
        assert "POPIA" in ed["mandatory_compliance_domains"]
        assert "PAIA" in ed["mandatory_compliance_domains"]
        assert ed["data_residency_required"] == "ZA"

    def test_agriculture_vertical(self):
        ag = next(v for v in VERTICAL_SEEDS if v["vertical_name"] == "agriculture")
        assert "DAFF" in ag["mandatory_compliance_domains"]
        assert ag["required_kya_level"] == 2
        assert ag["data_residency_required"] is None

    def test_healthcare_requires_owner_approval(self):
        hc = next(v for v in VERTICAL_SEEDS if v["vertical_name"] == "healthcare")
        assert hc["required_kya_level"] == 3  # Enhanced = owner approval required


class TestSeasonalLoanTemplates:
    def test_five_crop_templates(self):
        assert len(SEASONAL_LOAN_SEEDS) == 5

    def test_crop_types(self):
        crops = {t["crop_type"] for t in SEASONAL_LOAN_SEEDS}
        assert "Maize" in crops
        assert "Wheat" in crops
        assert "Sugarcane" in crops
        assert "Citrus" in crops
        assert "Soybean" in crops

    def test_maize_template(self):
        maize = next(t for t in SEASONAL_LOAN_SEEDS if t["crop_type"] == "Maize")
        assert maize["typical_term_days"] == 180
        assert maize["planting_months"] == [10, 11]
        assert maize["harvest_months"] == [4, 5]
        assert maize["suggested_interest_rate"] == 0.085

    def test_wheat_template(self):
        wheat = next(t for t in SEASONAL_LOAN_SEEDS if t["crop_type"] == "Wheat")
        assert wheat["typical_term_days"] == 180
        assert wheat["suggested_interest_rate"] == 0.08

    def test_sugarcane_longer_term(self):
        sc = next(t for t in SEASONAL_LOAN_SEEDS if t["crop_type"] == "Sugarcane")
        assert sc["typical_term_days"] == 240  # Longer growth cycle

    def test_all_interest_rates_reasonable(self):
        for t in SEASONAL_LOAN_SEEDS:
            assert 0.05 <= t["suggested_interest_rate"] <= 0.15

    def test_all_terms_reasonable(self):
        for t in SEASONAL_LOAN_SEEDS:
            assert 90 <= t["typical_term_days"] <= 365

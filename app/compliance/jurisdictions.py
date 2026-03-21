"""Jurisdiction-aware compliance rules — country-specific transaction limits.

Issue #8: The platform must be aware of where operators are based and
apply the correct regulatory rules per jurisdiction.

Rules are based on publicly available financial regulations:
- South Africa: SARB Exchange Control (SDA R1M/year offshore)
- United States: FinCEN BSA reporting ($10k+ CTR, $3k+ for MSBs)
- United Kingdom: FCA rules (no hard annual cap, but reporting thresholds)
- European Union: AMLD6 (€10k+ for enhanced due diligence)
- Default: Conservative limits for unlisted jurisdictions
"""

from dataclasses import dataclass


@dataclass
class JurisdictionRules:
    """Compliance rules for a specific jurisdiction."""
    country_code: str
    country_name: str
    default_currency: str
    annual_offshore_limit: float          # Max annual cross-border transfers (in USD equivalent)
    single_transaction_report: float      # Threshold that triggers reporting (USD equivalent)
    enhanced_dd_threshold: float          # Enhanced due diligence required above this (USD)
    crypto_allowed: bool                  # Whether crypto trading is permitted
    crypto_notes: str                     # Regulatory notes on crypto
    requires_tax_id: bool                 # Whether tax ID is mandatory for registration
    regulator: str                        # Primary financial regulator
    notes: str                            # Additional compliance notes


# ── Jurisdiction Rules Database ──────────────────────────────────────

JURISDICTION_RULES: dict[str, JurisdictionRules] = {

    "ZA": JurisdictionRules(
        country_code="ZA",
        country_name="South Africa",
        default_currency="ZAR",
        annual_offshore_limit=1_000_000 / 18.30,    # R1M SDA ≈ $54,644 USD
        single_transaction_report=25_000 / 18.30,    # R25k reporting threshold
        enhanced_dd_threshold=100_000 / 18.30,       # R100k enhanced DD
        crypto_allowed=True,
        crypto_notes="IFWG regulatory sandbox. Crypto assets declared as financial products under FSCA since Oct 2022.",
        requires_tax_id=False,
        regulator="SARB / FSCA / FIC",
        notes="Exchange control limits apply to offshore transfers. SDA allowance R1M/year, FIA R10M/year with tax clearance.",
    ),

    "US": JurisdictionRules(
        country_code="US",
        country_name="United States",
        default_currency="USD",
        annual_offshore_limit=500_000,                # No hard cap, but MSB reporting requirements
        single_transaction_report=10_000,              # CTR filing threshold
        enhanced_dd_threshold=3_000,                   # MSB record-keeping threshold
        crypto_allowed=True,
        crypto_notes="Regulated by SEC (securities), CFTC (commodities), FinCEN (AML). State-by-state MTL requirements.",
        requires_tax_id=True,
        regulator="FinCEN / SEC / CFTC",
        notes="Money transmitter licenses required per state. FATCA reporting for foreign accounts.",
    ),

    "GB": JurisdictionRules(
        country_code="GB",
        country_name="United Kingdom",
        default_currency="GBP",
        annual_offshore_limit=1_000_000,              # No hard cap, but reporting thresholds
        single_transaction_report=10_000,              # ~£8,000 equivalent
        enhanced_dd_threshold=15_000,                  # Enhanced CDD for complex transactions
        crypto_allowed=True,
        crypto_notes="FCA registration required for crypto businesses. Marketing restrictions under FCA PS22/10.",
        requires_tax_id=False,
        regulator="FCA / HMRC",
        notes="Post-Brexit standalone regime. FCA crypto registration mandatory. HMRC capital gains on crypto disposals.",
    ),

    # EU countries share common AMLD6 framework
    "DE": JurisdictionRules(
        country_code="DE",
        country_name="Germany",
        default_currency="EUR",
        annual_offshore_limit=500_000,                # No hard cap within EU, reporting thresholds
        single_transaction_report=10_000,              # €10k AMLD threshold
        enhanced_dd_threshold=15_000,                  # Enhanced DD threshold
        crypto_allowed=True,
        crypto_notes="BaFin licensed. Crypto classified as financial instruments under KWG.",
        requires_tax_id=True,
        regulator="BaFin / Bundesbank",
        notes="EU AMLD6 applies. MiCA regulation for crypto assets from 2024.",
    ),

    "FR": JurisdictionRules(
        country_code="FR",
        country_name="France",
        default_currency="EUR",
        annual_offshore_limit=500_000,
        single_transaction_report=10_000,
        enhanced_dd_threshold=15_000,
        crypto_allowed=True,
        crypto_notes="AMF PSAN registration required for crypto. PACTE law framework.",
        requires_tax_id=True,
        regulator="AMF / ACPR",
        notes="EU AMLD6 applies. MiCA regulation for crypto assets.",
    ),

    "NL": JurisdictionRules(
        country_code="NL",
        country_name="Netherlands",
        default_currency="EUR",
        annual_offshore_limit=500_000,
        single_transaction_report=10_000,
        enhanced_dd_threshold=15_000,
        crypto_allowed=True,
        crypto_notes="DNB registration required for crypto services.",
        requires_tax_id=True,
        regulator="DNB / AFM",
        notes="EU AMLD6 applies. MiCA regulation for crypto assets.",
    ),

    "AE": JurisdictionRules(
        country_code="AE",
        country_name="United Arab Emirates",
        default_currency="USD",
        annual_offshore_limit=1_000_000,
        single_transaction_report=15_000,
        enhanced_dd_threshold=55_000,                  # AED 200k threshold
        crypto_allowed=True,
        crypto_notes="VARA (Dubai) and ADGM regulate crypto. Relatively permissive framework.",
        requires_tax_id=False,
        regulator="VARA / CBUAE / SCA",
        notes="No personal income tax. Free zones offer additional regulatory frameworks.",
    ),

    "SG": JurisdictionRules(
        country_code="SG",
        country_name="Singapore",
        default_currency="USD",
        annual_offshore_limit=1_000_000,
        single_transaction_report=20_000,              # SGD 20k threshold
        enhanced_dd_threshold=20_000,
        crypto_allowed=True,
        crypto_notes="MAS Payment Services Act. Crypto treated as digital payment tokens.",
        requires_tax_id=False,
        regulator="MAS",
        notes="Progressive crypto regulation. No capital gains tax on crypto.",
    ),

    "AU": JurisdictionRules(
        country_code="AU",
        country_name="Australia",
        default_currency="USD",
        annual_offshore_limit=500_000,
        single_transaction_report=10_000,              # AUD 10k threshold
        enhanced_dd_threshold=10_000,
        crypto_allowed=True,
        crypto_notes="AUSTRAC registration required. Crypto treated as property for tax.",
        requires_tax_id=True,
        regulator="AUSTRAC / ASIC",
        notes="AML/CTF Act applies. AUSTRAC registration mandatory for crypto exchanges.",
    ),

    "NG": JurisdictionRules(
        country_code="NG",
        country_name="Nigeria",
        default_currency="USD",
        annual_offshore_limit=50_000,                  # CBN restrictions
        single_transaction_report=5_000,
        enhanced_dd_threshold=10_000,
        crypto_allowed=True,
        crypto_notes="SEC Nigeria adopted crypto regulation in 2023. Banks previously restricted but easing.",
        requires_tax_id=False,
        regulator="CBN / SEC Nigeria",
        notes="Strict capital controls. Banks have restrictions on crypto-related transactions.",
    ),

    "KE": JurisdictionRules(
        country_code="KE",
        country_name="Kenya",
        default_currency="USD",
        annual_offshore_limit=100_000,
        single_transaction_report=10_000,
        enhanced_dd_threshold=10_000,
        crypto_allowed=True,
        crypto_notes="No specific crypto regulation yet. Capital Markets Authority exploring framework.",
        requires_tax_id=False,
        regulator="CBK / CMA Kenya",
        notes="Limited regulatory clarity on crypto. Mobile money ecosystem dominant.",
    ),
}

# Default rules for jurisdictions not explicitly listed
DEFAULT_RULES = JurisdictionRules(
    country_code="XX",
    country_name="Other",
    default_currency="USD",
    annual_offshore_limit=100_000,           # Conservative default
    single_transaction_report=10_000,
    enhanced_dd_threshold=15_000,
    crypto_allowed=True,
    crypto_notes="Jurisdiction not specifically configured. Default conservative rules apply.",
    requires_tax_id=False,
    regulator="Local financial authority",
    notes="Operators from unlisted jurisdictions are subject to conservative default limits. "
          "Contact platform for jurisdiction-specific configuration.",
)


def get_jurisdiction_rules(country_code: str) -> JurisdictionRules:
    """Get the compliance rules for a country. Falls back to defaults."""
    return JURISDICTION_RULES.get(country_code.upper(), DEFAULT_RULES)


def list_supported_jurisdictions() -> list[dict]:
    """List all explicitly supported jurisdictions."""
    result = []
    for code, rules in sorted(JURISDICTION_RULES.items()):
        result.append({
            "country_code": rules.country_code,
            "country_name": rules.country_name,
            "default_currency": rules.default_currency,
            "crypto_allowed": rules.crypto_allowed,
            "regulator": rules.regulator,
        })
    return result


def get_jurisdiction_summary(country_code: str) -> dict:
    """Get a summary of rules for a jurisdiction (safe to expose to operators)."""
    rules = get_jurisdiction_rules(country_code)
    return {
        "country_code": rules.country_code,
        "country_name": rules.country_name,
        "default_currency": rules.default_currency,
        "annual_offshore_limit_usd": rules.annual_offshore_limit,
        "single_transaction_report_usd": rules.single_transaction_report,
        "enhanced_dd_threshold_usd": rules.enhanced_dd_threshold,
        "crypto_allowed": rules.crypto_allowed,
        "crypto_notes": rules.crypto_notes,
        "requires_tax_id": rules.requires_tax_id,
        "regulator": rules.regulator,
        "notes": rules.notes,
    }

"""Margin Protection Rule — Immutable Operating Principle.

RULE: No product or service may be priced below the cost of delivering it.
Every pricing decision must pass the margin gate before activation.

This module calculates the true cost of delivering each service including
all third-party provider costs, and enforces a minimum margin threshold.

Third-party providers:
- DigitalOcean: $6/mo infrastructure
- PayPal: 2.9% + R5.50 per transaction
- Twilio: ~R0.50 per SMS
- Microsoft Graph: R0 (included)
- Cloudflare: R0 (free tier)
- Let's Encrypt: R0

MINIMUM MARGIN RULE: 50% gross margin on all paid services.
Exception: AgentHub Pro ($1/mo) at 67% margin — approved as volume play.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
#  THIRD-PARTY COST PARAMETERS
# ══════════════════════════════════════════════════════════════════════

PAYPAL_PERCENTAGE = 0.029      # 2.9%
PAYPAL_FIXED_ZAR = 5.50        # R5.50 per transaction
TWILIO_SMS_COST_ZAR = 0.50     # R0.50 per SMS
INFRA_MONTHLY_ZAR = 120.00     # DigitalOcean + misc
STORAGE_COST_PER_GB_ZAR = 0.05 # ~R0.05/GB/mo (PostgreSQL on existing server — marginal cost only)
# Note: If moved to DigitalOcean Spaces, this becomes ~R0.50/GB/mo — recalculate all vault margins

MINIMUM_MARGIN_PCT = 50.0      # 50% minimum gross margin
CHARITABLE_ALLOCATION = 0.10   # 10% of commission to charity

# ══════════════════════════════════════════════════════════════════════
#  COST CALCULATIONS
# ══════════════════════════════════════════════════════════════════════

def calculate_paypal_cost(amount_zar: float) -> float:
    """Calculate PayPal processing cost for a given amount."""
    return round(amount_zar * PAYPAL_PERCENTAGE + PAYPAL_FIXED_ZAR, 2)


def calculate_storage_cost(gb: float) -> float:
    """Calculate monthly storage cost for a given volume."""
    return round(gb * STORAGE_COST_PER_GB_ZAR, 2)


def calculate_margin(price_zar: float, cost_zar: float) -> dict:
    """Calculate margin for a given price and cost."""
    if price_zar <= 0:
        return {"price": 0, "cost": cost_zar, "margin": 0, "margin_pct": 0, "passes": True, "reason": "free tier"}

    gross_profit = price_zar - cost_zar
    margin_pct = round((gross_profit / price_zar) * 100, 1) if price_zar > 0 else 0
    passes = margin_pct >= MINIMUM_MARGIN_PCT

    return {
        "price_zar": price_zar,
        "cost_zar": cost_zar,
        "gross_profit_zar": round(gross_profit, 2),
        "margin_pct": margin_pct,
        "minimum_required_pct": MINIMUM_MARGIN_PCT,
        "passes": passes,
        "reason": "PASSES" if passes else f"FAILS — margin {margin_pct}% below minimum {MINIMUM_MARGIN_PCT}%",
    }


# ══════════════════════════════════════════════════════════════════════
#  PRODUCT MARGIN ANALYSIS
# ══════════════════════════════════════════════════════════════════════

PRODUCT_MARGINS = {}

def _compute_all_margins():
    """Compute margins for every paid product."""
    products = [
        # Operator subscriptions
        {"name": "Operator Builder", "sku": "OP-BUILDER", "price_zar": 299,
         "costs": [("PayPal", calculate_paypal_cost(299)), ("Infra share", 10)]},
        {"name": "Operator Professional", "sku": "OP-PROFESSIONAL", "price_zar": 999,
         "costs": [("PayPal", calculate_paypal_cost(999)), ("Infra share", 20)]},
        {"name": "Operator Enterprise", "sku": "OP-ENTERPRISE", "price_zar": 2499,
         "costs": [("PayPal", calculate_paypal_cost(2499)), ("Infra share", 30)]},

        # AgentHub Pro
        {"name": "AgentHub Pro", "sku": "AH-PRO", "price_zar": 18.50,
         "costs": [("PayPal", calculate_paypal_cost(18.50))]},

        # AgentVault tiers
        {"name": "Vault Locker", "sku": "AV-LOCKER", "price_zar": 49,
         "costs": [("PayPal", calculate_paypal_cost(49)), ("Storage 10GB", calculate_storage_cost(10))]},
        {"name": "Vault Chamber", "sku": "AV-CHAMBER", "price_zar": 149,
         "costs": [("PayPal", calculate_paypal_cost(149)), ("Storage 100GB", calculate_storage_cost(100))]},
        {"name": "Vault Citadel", "sku": "AV-CITADEL", "price_zar": 499,
         "costs": [("PayPal", calculate_paypal_cost(499)), ("Storage 1TB", calculate_storage_cost(1024))]},

        # Intelligence subscriptions
        {"name": "Intelligence Standard", "sku": "INT-STANDARD", "price_zar": 499,
         "costs": [("PayPal", calculate_paypal_cost(499)), ("Compute", 5)]},
        {"name": "Intelligence Premium", "sku": "INT-PREMIUM", "price_zar": 1499,
         "costs": [("PayPal", calculate_paypal_cost(1499)), ("Compute", 10)]},

        # Premium add-ons
        {"name": "Capability Badge", "sku": "BADGE", "price_zar": 500,
         "costs": [("PayPal", calculate_paypal_cost(500))]},
        {"name": "Guild Setup", "sku": "GUILD-SETUP", "price_zar": 1500,
         "costs": [("PayPal", calculate_paypal_cost(1500))]},
        {"name": "Guild Membership", "sku": "GUILD-MEMBER", "price_zar": 200,
         "costs": [("PayPal", calculate_paypal_cost(200))]},
        {"name": "Benchmarking Report", "sku": "BENCH-REPORT", "price_zar": 1200,
         "costs": [("PayPal", calculate_paypal_cost(1200))]},
        {"name": "SARS Tax Certificate", "sku": "SARS-CERT", "price_zar": 150,
         "costs": [("PayPal", calculate_paypal_cost(150))]},
    ]

    for p in products:
        total_cost = sum(c[1] for c in p["costs"])
        margin = calculate_margin(p["price_zar"], total_cost)
        margin["product"] = p["name"]
        margin["sku"] = p["sku"]
        margin["cost_breakdown"] = {c[0]: c[1] for c in p["costs"]}
        PRODUCT_MARGINS[p["sku"]] = margin

    return PRODUCT_MARGINS

# Compute on import
_compute_all_margins()


def get_all_margins() -> list[dict]:
    """Return margin analysis for all products."""
    return list(PRODUCT_MARGINS.values())


def check_margin(sku: str) -> dict:
    """Check if a specific product passes the margin gate."""
    if sku not in PRODUCT_MARGINS:
        return {"error": f"Unknown SKU: {sku}"}
    return PRODUCT_MARGINS[sku]


def validate_new_price(product_name: str, proposed_price_zar: float, estimated_cost_zar: float) -> dict:
    """Validate a proposed new price against the margin rule.

    Use this before setting any new price or creating any new product.
    Returns pass/fail with explanation.
    """
    margin = calculate_margin(proposed_price_zar, estimated_cost_zar)
    margin["product"] = product_name

    if not margin["passes"]:
        minimum_price = round(estimated_cost_zar / (1 - MINIMUM_MARGIN_PCT / 100), 2)
        margin["minimum_viable_price_zar"] = minimum_price
        margin["recommendation"] = f"Increase price to at least R{minimum_price} for {MINIMUM_MARGIN_PCT}% margin"
        logger.warning(
            f"MARGIN GATE FAILED: {product_name} at R{proposed_price_zar} "
            f"has {margin['margin_pct']}% margin (minimum {MINIMUM_MARGIN_PCT}%)"
        )
    else:
        logger.info(f"MARGIN GATE PASSED: {product_name} at R{proposed_price_zar} — {margin['margin_pct']}% margin")

    return margin


def get_margin_summary() -> dict:
    """Get a summary of all product margins for the owner dashboard."""
    all_pass = all(m["passes"] for m in PRODUCT_MARGINS.values())
    lowest = min(PRODUCT_MARGINS.values(), key=lambda m: m["margin_pct"] if m["price_zar"] > 0 else 100)
    highest = max(PRODUCT_MARGINS.values(), key=lambda m: m["margin_pct"])

    failing = [m for m in PRODUCT_MARGINS.values() if not m["passes"] and m["price_zar"] > 0]

    return {
        "all_pass": all_pass,
        "total_products": len(PRODUCT_MARGINS),
        "passing": len([m for m in PRODUCT_MARGINS.values() if m["passes"]]),
        "failing": len(failing),
        "lowest_margin": {"product": lowest.get("product"), "margin_pct": lowest["margin_pct"]},
        "highest_margin": {"product": highest.get("product"), "margin_pct": highest["margin_pct"]},
        "minimum_required_pct": MINIMUM_MARGIN_PCT,
        "failing_products": [{"product": m["product"], "margin_pct": m["margin_pct"]} for m in failing],
        "third_party_costs": {
            "paypal_pct": f"{PAYPAL_PERCENTAGE * 100}%",
            "paypal_fixed": f"R{PAYPAL_FIXED_ZAR}",
            "storage_per_gb": f"R{STORAGE_COST_PER_GB_ZAR}",
            "infra_monthly": f"R{INFRA_MONTHLY_ZAR}",
        },
    }

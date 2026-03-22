"""Full diagnostic test of the Margin Protection system."""
from app.revenue.margin_protection import (
    calculate_paypal_cost, calculate_storage_cost, calculate_margin,
    validate_new_price, get_all_margins, get_margin_summary, check_margin,
    MINIMUM_MARGIN_PCT, PAYPAL_PERCENTAGE, PAYPAL_FIXED_ZAR, STORAGE_COST_PER_GB_ZAR,
)

passed = 0
failed = 0
total = 0

def test(name, condition, detail=""):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name} — {detail}")

print("=== MARGIN PROTECTION DIAGNOSTIC ===\n")

# 1. Constants
print("--- Constants ---")
test("PayPal percentage is 2.9%", PAYPAL_PERCENTAGE == 0.029)
test("PayPal fixed fee is R5.50", PAYPAL_FIXED_ZAR == 5.50)
test("Storage cost is R0.05/GB", STORAGE_COST_PER_GB_ZAR == 0.05)
test("Minimum margin is 50%", MINIMUM_MARGIN_PCT == 50.0)

# 2. PayPal cost calculations
print("\n--- PayPal Cost Calculations ---")
test("PayPal on R299 = R14.17", calculate_paypal_cost(299) == 14.17)
test("PayPal on R999 = R34.47", calculate_paypal_cost(999) == 34.47)
test("PayPal on R18.50 = R6.04", calculate_paypal_cost(18.50) == 6.04)
test("PayPal on R0 = R5.50", calculate_paypal_cost(0) == 5.50)
test("PayPal on R10000 = R295.50", calculate_paypal_cost(10000) == 295.50)

# 3. Storage costs
print("\n--- Storage Cost Calculations ---")
test("10GB = R0.50", calculate_storage_cost(10) == 0.50)
test("100GB = R5.00", calculate_storage_cost(100) == 5.00)
test("1TB = R51.20", calculate_storage_cost(1024) == 51.20)

# 4. Margin calculations
print("\n--- Margin Calculations ---")
m1 = calculate_margin(100, 30)
test("R100/R30 = 70% margin", m1["margin_pct"] == 70.0, f"got {m1['margin_pct']}")
test("R100/R30 passes gate", m1["passes"] == True)

m2 = calculate_margin(100, 60)
test("R100/R60 = 40% margin", m2["margin_pct"] == 40.0, f"got {m2['margin_pct']}")
test("R100/R60 FAILS gate", m2["passes"] == False)

m3 = calculate_margin(100, 50)
test("R100/R50 = 50% exactly passes", m3["passes"] == True)

m4 = calculate_margin(0, 0)
test("Free tier passes", m4["passes"] == True)

m5 = calculate_margin(10, 10)
test("R10/R10 = 0% FAILS", m5["passes"] == False)

m6 = calculate_margin(100, 49.99)
test("R100/R49.99 = 50.01% passes", m6["passes"] == True)

m7 = calculate_margin(100, 50.01)
test("R100/R50.01 = 49.99% FAILS", m7["passes"] == False)

# 5. All products
print("\n--- Product Margins ---")
margins = get_all_margins()
test(f"{len(margins)} products loaded", len(margins) == 14, f"got {len(margins)}")

expected_skus = [
    "OP-BUILDER", "OP-PROFESSIONAL", "OP-ENTERPRISE",
    "AH-PRO", "AV-LOCKER", "AV-CHAMBER", "AV-CITADEL",
    "INT-STANDARD", "INT-PREMIUM", "BADGE", "GUILD-SETUP",
    "GUILD-MEMBER", "BENCH-REPORT", "SARS-CERT",
]
for sku in expected_skus:
    m = check_margin(sku)
    test(f"{sku} passes", m.get("passes", False), f"margin {m.get('margin_pct', 'N/A')}%")

# 6. Summary
print("\n--- Summary ---")
summary = get_margin_summary()
test("All products pass", summary["all_pass"] == True)
test("14 total products", summary["total_products"] == 14)
test("0 failing", summary["failing"] == 0)
test("Lowest >= 50%", summary["lowest_margin"]["margin_pct"] >= 50.0)

# 7. Price validation gate
print("\n--- Price Validation Gate ---")
v1 = validate_new_price("Good Product", 200, 50)
test("R200/R50 passes (75%)", v1["passes"] == True)

v2 = validate_new_price("Bad Product", 100, 80)
test("R100/R80 FAILS (20%)", v2["passes"] == False)
test("Shows min viable price", "minimum_viable_price_zar" in v2)
if "minimum_viable_price_zar" in v2:
    test(f"Min price R{v2['minimum_viable_price_zar']} >= R160", v2["minimum_viable_price_zar"] >= 160)

v3 = validate_new_price("Exact 50%", 100, 50)
test("Exact 50% passes", v3["passes"] == True)

v4 = validate_new_price("Just below", 100, 50.01)
test("49.99% fails", v4["passes"] == False)

v5 = validate_new_price("Zero price", 0, 0)
test("Free product passes", v5["passes"] == True)

# 8. Error handling
print("\n--- Error Handling ---")
test("Unknown SKU returns error", "error" in check_margin("FAKE"))

# 9. Spot checks
print("\n--- Spot Checks ---")
builder = check_margin("OP-BUILDER")
test("Builder price R299", builder["price_zar"] == 299)
test("Builder margin > 90%", builder["margin_pct"] > 90)
test("Builder has PayPal in costs", "PayPal" in builder.get("cost_breakdown", {}))

pro = check_margin("AH-PRO")
test("Pro price R18.50", pro["price_zar"] == 18.50)
test("Pro margin 67.4%", pro["margin_pct"] == 67.4)

citadel = check_margin("AV-CITADEL")
test("Citadel price R499", citadel["price_zar"] == 499)
test("Citadel margin > 80%", citadel["margin_pct"] > 80)
test("Citadel has storage cost", any("Storage" in k for k in citadel.get("cost_breakdown", {})))

# 10. Cross-check: no negative margins anywhere
print("\n--- Negative Margin Check ---")
for m in margins:
    test(f"{m['product']} margin >= 0", m["margin_pct"] >= 0 or m["price_zar"] == 0)

print(f"\n=== RESULTS: {passed}/{total} passed, {failed} failed ===")
if failed == 0:
    print("=== ALL TESTS PASSED — MARGIN PROTECTION FULLY OPERATIONAL ===")
else:
    print(f"=== WARNING: {failed} TESTS FAILED ===")

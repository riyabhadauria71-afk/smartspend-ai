import os

import app as app_module
from services.gemini_service import GeminiServiceError

client = app_module.app.test_client()
passed = 0
failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}")


def shop(category="headphones", budget="30", use="commute", prefs="", priority="value"):
    return client.post("/shop", data={
        "category": category, "budget": budget, "use": use,
        "preferences": prefs, "priority": priority,
    })


def fake_ai(within, over, form):
    """A stand-in for Gemini. It even lies about price, to prove prices come from the catalog."""
    return {
        "summary": "Test summary",
        "best_value_id": "hp-002",
        "advice": {
            p["id"]: {"explanation": "Costs only $0.01 today!", "pros": ["ok"], "cons": []}
            for p in within
        },
        "over_notes": {},
    }


def failing_ai(within, over, form):
    raise GeminiServiceError("The AI service is unavailable right now. You can still browse the options.")


print("\n=== 1. Pages load ===")
check("Home page loads", client.get("/").status_code == 200)
check("Shop form loads", client.get("/shop").status_code == 200)

print("\n=== 2. Empty or invalid preferences ===")
html = shop(category="").get_data(as_text=True)
check("Missing category is rejected", "Please choose a valid category." in html)
html = shop(category="spaceships").get_data(as_text=True)
check("Unknown category is rejected", "Please choose a valid category." in html)
for bad in ["abc", "-5", "0", "nan", "inf", "99999", ""]:
    html = shop(budget=bad).get_data(as_text=True)
    check(f"Budget {bad!r} is rejected",
          "Please enter your budget as a number." in html
          or "Budget must be between 1 and 10000 USD." in html)

print("\n=== 3. Recommendations (AI replaced by a fake) ===")
app_module.get_ai_recommendations = fake_ai
html = shop().get_data(as_text=True)
check("Catalog price $19.00 USD is shown", "$19.00 USD" in html)
check("Remaining budget $11.00 is shown", "$11.00" in html)
check("Over-budget item is flagged", "Over budget by $15.00" in html)
check("Best value badge is shown", "Best value" in html)
check("Select Product buttons exist", "Select Product" in html)

print("\n=== 4. No matching products ===")
html = shop(category="keyboards", budget="5").get_data(as_text=True)
check("'No products fit' message is shown", "No products in this category fit your budget." in html)

print("\n=== 5. Gemini failure ===")
app_module.get_ai_recommendations = failing_ai
html = shop().get_data(as_text=True)
check("AI warning is shown", "The AI service is unavailable" in html)
check("Catalog prices are still shown", "$12.00 USD" in html)
check("Select Product still works", "Select Product" in html)

print("\n=== 6. Text typed by users is escaped ===")
app_module.get_ai_recommendations = fake_ai
html = shop(use="<script>alert(1)</script>").get_data(as_text=True)
check("Raw <script> is NOT in the page", "<script>alert(1)</script>" not in html)

print("\n=== 7. Tampered product ids and budgets (review) ===")
r = client.post("/review", data={"product_id": "fake-999", "budget": "30"})
check("Unknown product -> 400", r.status_code == 400)
r = client.post("/review", data={"product_id": "hp-004", "budget": "30"})
check("Over-budget product -> 400", r.status_code == 400)
for bad in ["-5", "abc", "nan"]:
    r = client.post("/review", data={"product_id": "hp-002", "budget": bad})
    check(f"Budget {bad!r} -> 400", r.status_code == 400)
r = client.post("/review", data={"product_id": "hp-002", "budget": "30", "price": "0.01"})
html = r.get_data(as_text=True)
check("Valid order -> 200 and catalog total $19.00", r.status_code == 200 and "$19.00 USD" in html)
check("Browser-supplied price 0.01 is ignored", "$0.01" not in html)

print("\n=== 8. Comparison ===")
r = client.post("/compare", data={"budget": "30", "product_ids": ["hp-001"]})
check("One product -> 400", r.status_code == 400)
r = client.post("/compare", data={"budget": "30", "product_ids": ["hp-001", "fake-999"]})
check("Unknown product -> 400", r.status_code == 400)
r = client.post("/compare", data={"budget": "30", "product_ids": ["hp-001", "kb-001"]})
check("Different categories -> 400", r.status_code == 400)
r = client.post("/compare", data={"budget": "30", "product_ids": ["hp-001", "hp-002", "hp-003", "hp-004"]})
check("Four products -> 400", r.status_code == 400)
r = client.post("/compare", data={"budget": "30", "product_ids": ["hp-001", "hp-003"]})
html = r.get_data(as_text=True)
check("Valid comparison -> 200 with +$17.00 gap", r.status_code == 200 and "+$17.00" in html)

print("\n=== 9. Missing PayPal credentials ===")
saved = os.environ.get("PAYPAL_CLIENT_ID")
os.environ["PAYPAL_CLIENT_ID"] = ""
try:
    r = client.post("/review", data={"product_id": "hp-002", "budget": "30"})
    check("Review page explains payments are not configured",
          "Payments are not configured on this server." in r.get_data(as_text=True))
    r = client.post("/api/orders", json={"product_id": "hp-002", "budget": 30})
    check("Order API -> 503", r.status_code == 503)
finally:
    if saved is None:
        os.environ.pop("PAYPAL_CLIENT_ID", None)
    else:
        os.environ["PAYPAL_CLIENT_ID"] = saved

print("\n=== 10. Result page without a payment ===")
r = client.get("/payment/result/ABCDEFGH12345")
check("No session -> 404", r.status_code == 404)

print(f"\nSUMMARY: {passed} passed, {failed} failed")
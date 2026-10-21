from app import app
from services.paypal_service import get_order

client = app.test_client()


def call(label, payload):
    resp = client.post("/api/orders", json=payload)
    print(f"\n{label}\n  HTTP {resp.status_code}  {resp.get_json()}")
    return resp.get_json()


def show_paypal_order(order_id):
    order = get_order(order_id)
    unit = order["purchase_units"][0]
    print("  PayPal says -> status:", order["status"])
    print("  PayPal says -> amount:", unit["amount"]["value"], unit["amount"]["currency_code"])
    print("  PayPal says -> reference_id:", unit.get("reference_id"))


print("=== 1. Valid order (hp-002, budget 30) ===")
result = call("Create order", {"product_id": "hp-002", "budget": 30})
if result and "id" in result:
    show_paypal_order(result["id"])

print("\n=== 2. Price tampering: browser claims the price is 0.01 ===")
result = call("Create order with fake price", {"product_id": "hp-002", "budget": 30, "price": 0.01})
if result and "id" in result:
    show_paypal_order(result["id"])

print("\n=== 3. Invalid requests, all must be rejected ===")
call("Unknown product", {"product_id": "fake-999", "budget": 30})
call("Over budget (hp-004 costs 45)", {"product_id": "hp-004", "budget": 30})
call("Budget is text", {"product_id": "hp-002", "budget": "abc"})
call("Negative budget", {"product_id": "hp-002", "budget": -5})
call("Budget is NaN", {"product_id": "hp-002", "budget": "nan"})
call("Missing product", {"budget": 30})

resp = client.post("/api/orders", data="not json", content_type="text/plain")
print("\nNot JSON at all\n  HTTP", resp.status_code, resp.get_json())

print("\n=== 4. Bad PayPal order IDs must be rejected before any call ===")
for bad in ["../../etc", "x", "abc def ghi jkl"]:
    try:
        get_order(bad)
        print("  PROBLEM: accepted", bad)
    except Exception as exc:
        print(f"  {bad!r} -> rejected: {exc}")
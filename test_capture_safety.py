from app import app
from services.catalog_service import get_product_by_id
from services.paypal_service import create_order

client = app.test_client()

print("=== 1. Capture an order the buyer never approved ===")
order_id = create_order(get_product_by_id("hp-002"))
resp = client.post(f"/api/orders/{order_id}/capture")
print("  HTTP", resp.status_code, resp.get_json())

print("\n=== 2. Malformed order IDs ===")
for bad in ["abc", "lowercase123456", "ABCD1234$$$$"]:
    resp = client.post(f"/api/orders/{bad}/capture")
    print(f"  {bad!r} -> HTTP {resp.status_code} {resp.get_json()}")

print("\n=== 3. Well-formed ID that does not exist at PayPal ===")
resp = client.post("/api/orders/ABCDEFGH12345/capture")
print("  HTTP", resp.status_code, resp.get_json())

print("\n=== 4. Result page with no payment in this session ===")
resp = client.get(f"/payment/result/{order_id}")
print("  HTTP", resp.status_code)
from app import app

ORDER_ID = "049336265J406932U"  # the payment you made

print("=== A. A stranger with no session ===")
stranger = app.test_client()
resp = stranger.get(f"/payment/result/{ORDER_ID}")
print("  HTTP", resp.status_code, "| shows 'Payment verified':", b"Payment verified" in resp.data)

print("\n=== B. The browser that made this payment ===")
buyer = app.test_client()
with buyer.session_transaction() as sess:
    sess["paid_orders"] = [ORDER_ID]
resp = buyer.get(f"/payment/result/{ORDER_ID}")
print("  HTTP", resp.status_code, "| shows 'Payment verified':", b"Payment verified" in resp.data)

print("\n=== C. A browser that paid a DIFFERENT order ===")
other = app.test_client()
with other.session_transaction() as sess:
    sess["paid_orders"] = ["SOMEOTHERORDER1"]
resp = other.get(f"/payment/result/{ORDER_ID}")
print("  HTTP", resp.status_code, "| shows 'Payment verified':", b"Payment verified" in resp.data)
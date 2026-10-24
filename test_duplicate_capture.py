import sys

from services.payment_service import capture_payment
from services.paypal_service import get_order

if len(sys.argv) != 2:
    raise SystemExit("Usage: python test_duplicate_capture.py <PAYPAL_ORDER_ID>")

order_id = sys.argv[1].strip()

for attempt in (1, 2, 3):
    result = capture_payment(order_id)
    print(
        f"Attempt {attempt}: paid={result['paid']}, "
        f"already_captured={result['already_captured']}, "
        f"capture_id={result['capture_id']}"
    )

captures = get_order(order_id)["purchase_units"][0]["payments"]["captures"]
print("Number of captures PayPal holds for this order:", len(captures))
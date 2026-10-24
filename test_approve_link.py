from services.catalog_service import get_product_by_id
from services.paypal_service import create_order, get_order

order_id = create_order(get_product_by_id("hp-002"))
order = get_order(order_id)

print("Order:", order_id, "status:", order["status"])
for link in order.get("links", []):
    print(link.get("rel"), "->", link.get("href"))
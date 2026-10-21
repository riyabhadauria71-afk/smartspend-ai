import json
from pathlib import Path

PRODUCTS_FILE = Path(__file__).parent.parent / "data" / "products.json"


def load_products():
    """Read the catalog from disk and return a list of product dicts."""
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_categories():
    """Return a sorted list of unique categories in the catalog."""
    return sorted({p["category"] for p in load_products()})


def get_product_by_id(product_id):
    """Return one product by id, or None if it doesn't exist."""
    for product in load_products():
        if product["id"] == product_id:
            return product
    return None


def find_products(category, max_budget):
    """Return products in a category, split into within-budget and over-budget.

    All price math happens here in Python, never in the AI.
    """
    in_category = [p for p in load_products() if p["category"] == category]

    within_budget = []
    over_budget = []
    for product in in_category:
        item = dict(product)
        item["remaining_budget"] = round(max_budget - product["price"], 2)
        if product["price"] <= max_budget:
            within_budget.append(item)
        else:
            item["over_by"] = round(product["price"] - max_budget, 2)
            over_budget.append(item)

    within_budget.sort(key=lambda p: p["price"])
    over_budget.sort(key=lambda p: p["price"])
    return within_budget, over_budget

def compare_products(product_ids, budget):
    """Compare 2-3 catalog products. Raises ValueError with a friendly message.

    The browser sends only ids. Prices come from the catalog.
    """
    unique_ids = []
    for pid in product_ids:
        pid = pid.strip()
        if pid and pid not in unique_ids:
            unique_ids.append(pid)

    if not 2 <= len(unique_ids) <= 3:
        raise ValueError("Please choose 2 or 3 different products to compare.")

    products = []
    for pid in unique_ids:
        product = get_product_by_id(pid)
        if product is None:
            raise ValueError("One of the selected products could not be found.")
        products.append(dict(product))

    if len({p["category"] for p in products}) != 1:
        raise ValueError("Please compare products from the same category.")
    if len({p["currency"] for p in products}) != 1:
        raise ValueError("Products with different currencies cannot be compared.")

    cheapest_price = min(p["price"] for p in products)
    feature_sets = [set(p["features"]) for p in products]
    shared = set.intersection(*feature_sets)

    for i, p in enumerate(products):
        others = set()
        for j, features in enumerate(feature_sets):
            if j != i:
                others |= features
        p["unique_features"] = [f for f in p["features"] if f not in others]
        p["remaining"] = round(budget - p["price"], 2)
        p["within_budget"] = p["price"] <= budget
        p["price_diff"] = round(p["price"] - cheapest_price, 2)
        p["is_cheapest"] = p["price"] == cheapest_price

    return {
        "products": products,
        "shared_features": [f for f in products[0]["features"] if f in shared],
        "currency": products[0]["currency"],
    }
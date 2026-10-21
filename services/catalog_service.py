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
import logging
import math

from flask import Flask, jsonify, render_template, request

from services.catalog_service import (
    compare_products,
    find_products,
    get_categories,
    get_product_by_id,
)
from services.gemini_service import GeminiServiceError, get_ai_recommendations
from services.paypal_service import PayPalServiceError, create_order, get_public_client_id

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config["PAYPAL_CLIENT_ID"] = get_public_client_id()

MAX_ALLOWED_BUDGET = 10000  # sanity limit, in USD


def parse_budget(raw):
    """Turn text into a safe budget number. Returns (budget, error_message)."""
    try:
        budget = float(raw)
    except (TypeError, ValueError):
        return None, "Please enter your budget as a number."
    # float("nan") and float("inf") are valid floats, so we must reject them
    if not math.isfinite(budget) or budget <= 0 or budget > MAX_ALLOWED_BUDGET:
        return None, f"Budget must be between 1 and {MAX_ALLOWED_BUDGET} USD."
    return budget, None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/shop", methods=["GET", "POST"])
def shop():
    categories = get_categories()

    if request.method == "GET":
        return render_template("shop.html", categories=categories, form={}, error=None)

    form = {
        "category": request.form.get("category", "").strip(),
        "budget": request.form.get("budget", "").strip(),
        "use": request.form.get("use", "").strip()[:200],
        "preferences": request.form.get("preferences", "").strip()[:300],
        "priority": request.form.get("priority", "value").strip(),
    }

    error = None
    budget = None

    if form["category"] not in categories:
        error = "Please choose a valid category."
    else:
        budget, error = parse_budget(form["budget"])

    if form["priority"] not in ("value", "quality", "features"):
        form["priority"] = "value"

    if error:
        return render_template("shop.html", categories=categories, form=form, error=error)

    within_budget, over_budget = find_products(form["category"], budget)

    ai = None
    ai_error = None
    try:
        ai = get_ai_recommendations(within_budget, over_budget, form)
    except GeminiServiceError as exc:
        ai_error = str(exc)

    return render_template(
        "recommendations.html",
        form=form,
        budget=budget,
        within_budget=within_budget,
        over_budget=over_budget,
        ai=ai,
        ai_error=ai_error,
    )


@app.route("/compare", methods=["POST"])
def compare():
    """Compare 2-3 products. Plain Python only, no AI."""
    budget, error = parse_budget(request.form.get("budget", ""))
    comparison = None

    if not error:
        try:
            ids = request.form.getlist("product_ids")[:10]  # cap abuse
            comparison = compare_products(ids, budget)
        except ValueError as exc:
            error = str(exc)

    if error:
        return render_template(
            "shop.html", categories=get_categories(), form={}, error=error
        ), 400

    return render_template("compare.html", comparison=comparison, budget=budget)


@app.route("/review", methods=["POST"])
def review():
    """Show the order summary. The price comes from the catalog, never the browser."""
    product_id = request.form.get("product_id", "").strip()
    budget, error = parse_budget(request.form.get("budget", ""))
    product = get_product_by_id(product_id)

    if not error and product is None:
        error = "That product could not be found. Please start again."
    if not error and product["price"] > budget:
        error = "That product is over your budget. Please choose one within your budget."

    if error:
        return render_template(
            "shop.html", categories=get_categories(), form={}, error=error
        ), 400

    remaining = round(budget - product["price"], 2)

    # The client ID is public and goes to the browser. The secret never does.
    paypal_client_id = None
    payment_error = None
    try:
        paypal_client_id = get_public_client_id()
    except PayPalServiceError as exc:
        payment_error = str(exc)

    return render_template(
        "review.html",
        product=product,
        budget=budget,
        remaining=remaining,
        paypal_client_id=paypal_client_id,
        payment_error=payment_error,
    )


@app.route("/api/orders", methods=["POST"])
def api_create_order():
    """Create a PayPal order.

    The browser sends only a product id and a budget. The amount is looked up
    here from the catalog, so it cannot be tampered with.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid request."}), 400

    product_id = str(data.get("product_id", "")).strip()
    budget, error = parse_budget(data.get("budget"))
    if error:
        return jsonify({"error": error}), 400

    product = get_product_by_id(product_id)
    if product is None:
        return jsonify({"error": "That product could not be found."}), 400
    if product["price"] > budget:
        return jsonify({"error": "That product is over your budget."}), 400

    try:
        order_id = create_order(product)
    except PayPalServiceError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify({"id": order_id})


if __name__ == "__main__":
    app.run(debug=True)
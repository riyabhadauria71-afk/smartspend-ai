import logging
import math

from flask import Flask, render_template, request

from services.catalog_service import get_categories, find_products, get_product_by_id
from services.gemini_service import GeminiServiceError, get_ai_recommendations

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

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
    return render_template(
        "review.html", product=product, budget=budget, remaining=remaining
    )


if __name__ == "__main__":
    app.run(debug=True)
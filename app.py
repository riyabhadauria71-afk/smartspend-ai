from flask import Flask, render_template, request

from services.catalog_service import get_categories, find_products

app = Flask(__name__)

MAX_ALLOWED_BUDGET = 10000  # sanity limit, in USD


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/shop", methods=["GET", "POST"])
def shop():
    categories = get_categories()

    if request.method == "GET":
        return render_template("shop.html", categories=categories, form={}, error=None)

    # POST: read and validate what the user typed
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
        try:
            budget = float(form["budget"])
            if budget <= 0 or budget > MAX_ALLOWED_BUDGET:
                error = f"Budget must be between 1 and {MAX_ALLOWED_BUDGET} USD."
        except ValueError:
            error = "Please enter your budget as a number."

    if form["priority"] not in ("value", "quality", "features"):
        form["priority"] = "value"

    if error:
        return render_template("shop.html", categories=categories, form=form, error=error)

    within_budget, over_budget = find_products(form["category"], budget)
    return render_template(
        "recommendations.html",
        form=form,
        budget=budget,
        within_budget=within_budget,
        over_budget=over_budget,
    )


if __name__ == "__main__":
    app.run(debug=True)
(function () {
    const container = document.getElementById("paypal-button-container");
    const messageBox = document.getElementById("checkout-message");

    function showMessage(kind, text) {
        // kind is a Bootstrap colour: "success", "warning", "danger" or "info".
        // textContent (not innerHTML) means text can never be turned into HTML.
        messageBox.className = "mt-3 alert alert-" + kind;
        messageBox.textContent = text;
    }

    if (!container) {
        return;
    }

    if (typeof paypal === "undefined") {
        showMessage("danger", "PayPal could not be loaded. Check your connection and refresh the page.");
        return;
    }

    const productId = container.dataset.productId;
    const budget = container.dataset.budget;

    paypal.Buttons({
        // Runs when the buyer clicks the PayPal button.
        // We ask OUR server for an order. We send only the product id and the budget.
        async createOrder() {
            const response = await fetch("/api/orders", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ product_id: productId, budget: budget })
            });
            const data = await response.json().catch(function () { return {}; });
            if (!response.ok || !data.id) {
                throw new Error(data.error || "Could not start checkout.");
            }
            return data.id;
        },

        // Runs after the buyer approves in the PayPal popup.
        // Nothing has been charged yet. The server capture comes in the next milestone.
        onApprove(data) {
            showMessage(
                "info",
                "Approved in PayPal (order " + data.orderID + "). Payment is NOT complete yet: " +
                "the server capture step is the next milestone."
            );
        },

        onCancel() {
            showMessage("warning", "Checkout cancelled. You have not been charged.");
        },

        onError(err) {
            console.error("PayPal checkout error:", err);
            showMessage("danger", "Checkout could not be completed. Please try again.");
        }
    }).render("#paypal-button-container");
})();
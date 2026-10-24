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
    let processing = false;  // stops a second capture request from starting

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
        // The server captures and verifies. This page never decides that a payment succeeded.
        async onApprove(data, actions) {
            if (processing) {
                return;
            }
            processing = true;
            showMessage("info", "Verifying your payment with PayPal. Please wait...");

            try {
                const response = await fetch(
                    "/api/orders/" + encodeURIComponent(data.orderID) + "/capture",
                    { method: "POST", headers: { "Content-Type": "application/json" } }
                );
                const result = await response.json().catch(function () { return {}; });

                if (response.ok && result.redirect) {
                    window.location.href = result.redirect;  // server-verified result page
                    return;
                }

                processing = false;
                if (result.restart && actions && typeof actions.restart === "function") {
                    showMessage("warning", result.error || "Please choose another payment method.");
                    return actions.restart();
                }
                showMessage("danger", result.error || "The payment could not be completed.");
            } catch (err) {
                processing = false;
                console.error("Capture request failed:", err);
                showMessage("danger", "A network problem stopped us confirming the payment. Please try again.");
            }
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
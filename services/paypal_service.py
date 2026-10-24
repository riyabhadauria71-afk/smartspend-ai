import logging
import os
import re
import threading
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20  # seconds
ORDER_ID_PATTERN = re.compile(r"^[A-Z0-9]{8,36}$")

_token_lock = threading.Lock()
_token_cache = {"value": None, "expires_at": 0.0}


class PayPalServiceError(Exception):
    """Raised with a user-friendly message when a PayPal call fails."""

    def __init__(self, message, status_code=502, restart=False):
        super().__init__(message)
        self.status_code = status_code
        self.restart = restart  # True when the buyer should pick another payment method


def _config():
    client_id = os.getenv("PAYPAL_CLIENT_ID", "").strip()
    secret = os.getenv("PAYPAL_CLIENT_SECRET", "").strip()
    base_url = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com").strip().rstrip("/")

    if not client_id or not secret or client_id.startswith("your_") or secret.startswith("your_"):
        raise PayPalServiceError("Payments are not configured on this server.", 503)
    if "sandbox" not in base_url:
        raise PayPalServiceError("Only the PayPal Sandbox is allowed in this prototype.", 503)
    return client_id, secret, base_url


def get_public_client_id():
    """The client ID is safe to give the browser. The secret never leaves the server."""
    return _config()[0]


def _get_access_token(force_refresh=False):
    """Get a PayPal access token, reusing the cached one until shortly before it expires."""
    client_id, secret, base_url = _config()
    with _token_lock:
        if (
            not force_refresh
            and _token_cache["value"]
            and time.time() < _token_cache["expires_at"] - 60
        ):
            return _token_cache["value"]

        try:
            resp = requests.post(
                f"{base_url}/v1/oauth2/token",
                auth=(client_id, secret),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException:
            logger.exception("Could not reach PayPal for an access token")
            raise PayPalServiceError("Could not reach PayPal. Please try again.")

        if not resp.ok:
            logger.error("PayPal token request failed: %s %s", resp.status_code, resp.text[:200])
            raise PayPalServiceError("PayPal rejected the server credentials.")

        data = resp.json()
        _token_cache["value"] = data["access_token"]
        _token_cache["expires_at"] = time.time() + int(data.get("expires_in", 300))
        return _token_cache["value"]


def _paypal_request(method, path, body=None, request_id=None):
    """Call the PayPal API. Retries once with a fresh token if the first one was refused."""
    _, _, base_url = _config()
    resp = None
    for attempt in (1, 2):
        token = _get_access_token(force_refresh=(attempt == 2))
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        try:
            resp = requests.request(
                method, f"{base_url}{path}", json=body, headers=headers, timeout=REQUEST_TIMEOUT
            )
        except requests.RequestException:
            logger.exception("PayPal request failed")
            raise PayPalServiceError("Could not reach PayPal. Please try again.")
        if resp.status_code == 401 and attempt == 1:
            continue  # the token may have expired, so fetch a new one and retry once
        break
    return resp


def format_amount(price):
    """Turn a catalog price into the exact string PayPal expects, e.g. 19 -> '19.00'."""
    return str(Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def create_order(product):
    """Create a PayPal order for one catalog product and return the PayPal order ID.

    The amount comes from the trusted catalog product, never from the browser.
    """
    body = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": product["id"],
                "description": product["name"][:127],
                "amount": {
                    "currency_code": product["currency"],
                    "value": format_amount(product["price"]),
                },
            }
        ],
    }
    resp = _paypal_request("POST", "/v2/checkout/orders", body, request_id=str(uuid.uuid4()))

    if resp.status_code not in (200, 201):
        logger.error("PayPal create order failed: %s %s", resp.status_code, resp.text[:300])
        raise PayPalServiceError("PayPal could not create the order. Please try again.")

    data = resp.json()
    if not data.get("id") or data.get("status") != "CREATED":
        logger.error("Unexpected PayPal create-order response: %s", str(data)[:300])
        raise PayPalServiceError("PayPal returned an unexpected response. Please try again.")
    return data["id"]


def get_order(order_id):
    """Fetch an order's details from PayPal. We will use this to verify payments later."""
    if not isinstance(order_id, str) or not ORDER_ID_PATTERN.match(order_id):
        raise PayPalServiceError("Invalid order ID.", 400)

    resp = _paypal_request("GET", f"/v2/checkout/orders/{order_id}")
    if resp.status_code == 404:
        raise PayPalServiceError("Order not found.", 404)
    if not resp.ok:
        logger.error("PayPal get order failed: %s %s", resp.status_code, resp.text[:300])
        raise PayPalServiceError("Could not read the order from PayPal.")
    return resp.json()

def request_capture(order_id):
    """Ask PayPal to capture an approved order. Returns (http_status, issue_name).

    The request ID is derived from the order ID, so repeating this call is safe:
    PayPal treats it as the same request instead of charging twice.
    """
    if not isinstance(order_id, str) or not ORDER_ID_PATTERN.match(order_id):
        raise PayPalServiceError("Invalid order ID.", 400)

    resp = _paypal_request(
        "POST",
        f"/v2/checkout/orders/{order_id}/capture",
        {},
        request_id=f"capture-{order_id}",
    )

    issue = None
    if not resp.ok:
        try:
            body = resp.json()
            details = body.get("details") or []
            issue = details[0].get("issue") if details else body.get("name")
        except ValueError:
            issue = None
        logger.warning("PayPal capture returned %s (%s): %s", resp.status_code, issue, resp.text[:300])
    return resp.status_code, issue
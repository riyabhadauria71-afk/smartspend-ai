import logging
import threading
from decimal import Decimal, InvalidOperation

from services.catalog_service import get_product_by_id
from services.paypal_service import (
    PayPalServiceError,
    format_amount,
    get_order,
    request_capture,
)

logger = logging.getLogger(__name__)

_locks_guard = threading.Lock()
_order_locks = {}


def _lock_for(order_id):
    """One lock per order, so two simultaneous capture requests cannot overlap."""
    with _locks_guard:
        return _order_locks.setdefault(order_id, threading.Lock())


def _same_money(value, expected):
    try:
        return Decimal(str(value)) == Decimal(str(expected))
    except InvalidOperation:
        return False


def _check_order_against_catalog(order):
    """Make sure a PayPal order is one of ours and matches the trusted catalog price."""
    units = order.get("purchase_units") or []
    if order.get("intent") != "CAPTURE" or len(units) != 1:
        raise PayPalServiceError("This order was not created by SmartSpend AI.", 400)

    unit = units[0]
    product = get_product_by_id(str(unit.get("reference_id", "")))
    if product is None:
        raise PayPalServiceError("This order does not match any catalog product.", 400)

    amount = unit.get("amount") or {}
    if (
        not _same_money(amount.get("value"), format_amount(product["price"]))
        or amount.get("currency_code") != product["currency"]
    ):
        raise PayPalServiceError("The order amount does not match our catalog price.", 400)

    return product, unit


def verify_payment(order_id):
    """Read an order from PayPal and return a verified summary.

    Only this function decides what counts as paid, using PayPal's own data.
    """
    order = get_order(order_id)
    product, unit = _check_order_against_catalog(order)

    if order.get("status") != "COMPLETED":
        raise PayPalServiceError("This payment has not been completed.", 409)

    captures = (unit.get("payments") or {}).get("captures") or []
    if not captures:
        raise PayPalServiceError("No payment was recorded for this order.", 409)

    capture = captures[0]
    amount = capture.get("amount") or {}
    if (
        not _same_money(amount.get("value"), format_amount(product["price"]))
        or amount.get("currency_code") != product["currency"]
    ):
        raise PayPalServiceError("The captured amount does not match the catalog price.", 400)

    return {
        "order_id": order.get("id"),
        "product": product,
        "amount": amount.get("value"),
        "currency": amount.get("currency_code"),
        "capture_id": capture.get("id"),
        "capture_status": capture.get("status"),
        # An order can be COMPLETED while the payment inside it is not,
        # so "paid" depends on the capture status only.
        "paid": capture.get("status") == "COMPLETED",
    }


def capture_payment(order_id):
    """Capture an approved order exactly once and return the verified result."""
    with _lock_for(order_id):
        order = get_order(order_id)  # also validates the ID format
        _check_order_against_catalog(order)  # verify BEFORE any money moves

        status = order.get("status")
        already_captured = status == "COMPLETED"

        if status == "APPROVED":
            http_status, issue = request_capture(order_id)
            if http_status not in (200, 201):
                if issue == "ORDER_ALREADY_CAPTURED":
                    already_captured = True
                elif issue == "INSTRUMENT_DECLINED":
                    raise PayPalServiceError(
                        "PayPal could not use that payment method. Please choose another one.",
                        422,
                        restart=True,
                    )
                else:
                    raise PayPalServiceError("PayPal could not capture the payment.")
        elif not already_captured:
            raise PayPalServiceError("This order has not been approved yet.", 409)

        # Never trust the capture response alone: read the order again from PayPal.
        summary = verify_payment(order_id)
        summary["already_captured"] = already_captured
        return summary
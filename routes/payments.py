from __future__ import annotations

import logging
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from services.auth_guard import require_session
from services.runtime import (
    get_firebase,
    get_payments,
    user_storage_id,
)


log = logging.getLogger("payment-routes")

payments_bp = Blueprint(
    "payments",
    __name__,
    url_prefix="/api/payments",
)


SENSITIVE_FIELDS = {
    "secret",
    "api_key",
    "password",
    "webhook_secret",
}


def _safe_payment(
    payment: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        key: value
        for key, value in payment.items()
        if key not in SENSITIVE_FIELDS
    }


# ============================================================
# PRODUCTS
# ============================================================
@payments_bp.get("/products")
def api_products():
    firebase = get_firebase()

    if not firebase:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "database unavailable",
                }
            ),
            503,
        )

    products = (
        firebase.get_products()
        or {}
    )

    result = []

    if isinstance(products, dict):
        for product_id, product in products.items():
            if not isinstance(product, dict):
                continue

            result.append(
                {
                    "product_id": product_id,
                    "price": product.get("price"),
                    "currency": product.get("currency"),
                    "duration": product.get("duration"),
                }
            )

    return jsonify(
        {
            "status": "success",
            "products": result,
        }
    )


# ============================================================
# CREATE PAYMENT
# ============================================================
@payments_bp.post("/create")
@require_session
def api_create_payment(
    sid: str,
    item: Dict[str, Any],
):
    payload = request.get_json(
        silent=True
    ) or {}

    provider = str(
        payload.get(
            "provider",
            "",
        )
    ).strip().lower()

    product_id = str(
        payload.get(
            "product_id",
            "",
        )
    ).strip()

    if not provider or not product_id:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": (
                        "provider and product_id required"
                    ),
                }
            ),
            400,
        )

    payments = get_payments()

    if not payments:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "payment service unavailable",
                }
            ),
            503,
        )

    user_id = user_storage_id(
        sid,
        item,
    )

    result = payments.create_order(
        user_id,
        provider,
        product_id,
    )

    if result.get("status") == "error":
        return jsonify(result), 400

    return jsonify(result)


# ============================================================
# MY PAYMENT HISTORY
# ============================================================
@payments_bp.get("/history/me")
@require_session
def api_my_payments(
    sid: str,
    item: Dict[str, Any],
):
    firebase = get_firebase()

    if not firebase:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "database unavailable",
                }
            ),
            503,
        )

    user_id = user_storage_id(
        sid,
        item,
    )

    all_payments = (
        firebase.get_all_payments()
        or {}
    )

    mine = []

    if isinstance(all_payments, dict):
        for order_id, payment in all_payments.items():
            if not isinstance(payment, dict):
                continue

            if str(
                payment.get(
                    "user_id",
                    "",
                )
            ) != str(user_id):
                continue

            mine.append(
                {
                    "order_id": order_id,
                    **_safe_payment(payment),
                }
            )

    mine.sort(
        key=lambda value: int(
            value.get(
                "created_at",
                0,
            )
            or 0
        ),
        reverse=True,
    )

    return jsonify(
        {
            "status": "success",
            "payments": mine,
        }
    )


# ============================================================
# PAYMENT DETAILS
# ============================================================
@payments_bp.get("/<order_id>")
@require_session
def api_get_payment(
    sid: str,
    item: Dict[str, Any],
    order_id: str,
):
    firebase = get_firebase()

    if not firebase:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "database unavailable",
                }
            ),
            503,
        )

    order = firebase.get_payment(
        order_id
    )

    if not order:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "order not found",
                }
            ),
            404,
        )

    user_id = user_storage_id(
        sid,
        item,
    )

    is_admin = (
        str(
            item.get(
                "role",
                "user",
            )
        ).lower()
        == "admin"
    )

    if (
        not is_admin
        and str(
            order.get(
                "user_id",
                "",
            )
        )
        != str(user_id)
    ):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "forbidden",
                }
            ),
            403,
        )

    return jsonify(
        {
            "status": "success",
            "order": _safe_payment(
                order
            ),
        }
    )


# ============================================================
# PAYMENT WEBHOOK
# ============================================================
@payments_bp.post("/webhook/<provider_name>")
def api_webhook(
    provider_name: str,
):
    payload = request.get_json(
        silent=True
    )

    if not isinstance(
        payload,
        dict,
    ):
        payload = {}

    payments = get_payments()

    if not payments:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "payment service unavailable",
                }
            ),
            503,
        )

    headers = dict(
        request.headers
    )

    result = (
        payments.verify_and_activate(
            str(provider_name).lower(),
            payload,
            headers,
        )
    )

    status_code = (
        200
        if result.get("status")
        == "success"
        else 400
    )

    return jsonify(
        result
    ), status_code

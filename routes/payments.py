from __future__ import annotations

import logging

from flask import Blueprint, request, jsonify

from services.runtime import get_firebase, get_payments
from services.auth_guard import require_session

log = logging.getLogger("payment-routes")

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


@payments_bp.get("/products")
def api_products():
    firebase = get_firebase()
    products = firebase.get_products()
    result = []
    for pid, p in products.items():
        result.append({
            "product_id": pid,
            "price": p.get("price"),
            "currency": p.get("currency"),
            "duration": p.get("duration"),
        })
    return jsonify({"status": "success", "products": result})


@payments_bp.post("/create")
def api_create_payment():
    sid, item, error = require_session()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    provider = str(payload.get("provider", "")).lower()
    product_id = str(payload.get("product_id", ""))
    if not provider or not product_id:
        return jsonify({"status": "error", "message": "provider and product_id required"}), 400

    payments = get_payments()
    result = payments.create_order(sid, provider, product_id)
    if result.get("status") == "error":
        return jsonify(result), 400
    return jsonify(result)


@payments_bp.get("/history/me")
def api_my_payments():
    sid, item, error = require_session()
    if error:
        return error
    firebase = get_firebase()
    all_payments = firebase.get_all_payments()
    mine = []
    for oid, p in all_payments.items():
        if p.get("user_id") == sid:
            mine.append({"order_id": oid, **{k: v for k, v in p.items()
                                            if k not in ["secret", "api_key", "password", "webhook_secret"]}})
    mine.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return jsonify({"status": "success", "payments": mine})


@payments_bp.get("/<order_id>")
def api_get_payment(order_id):
    sid, item, error = require_session()
    if error:
        return error
    firebase = get_firebase()
    order = firebase.get_payment(order_id)
    if not order:
        return jsonify({"status": "error", "message": "order not found"}), 404

    if item.get("role") != "admin" and order.get("user_id") != sid:
        return jsonify({"status": "error", "message": "forbidden"}), 403

    safe = {k: v for k, v in order.items()
            if k not in ["secret", "api_key", "password", "webhook_secret"]}
    return jsonify({"status": "success", "order": safe})


@payments_bp.post("/webhook/<provider_name>")
def api_webhook(provider_name):
    payload = request.get_json(silent=True) or {}
    headers = dict(request.headers)
    payments = get_payments()
    result = payments.verify_and_activate(provider_name, payload, headers)
    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code

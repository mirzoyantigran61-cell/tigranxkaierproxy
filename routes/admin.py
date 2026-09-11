from __future__ import annotations

import logging
import time

from flask import Blueprint, jsonify

from services.runtime import get_firebase, get_sessions, APP_START_TIME
from services.auth_guard import require_admin

log = logging.getLogger("admin-routes")

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.get("/payments")
def api_admin_payments():
    sid, item, error = require_admin()
    if error:
        return error

    firebase = get_firebase()
    all_payments = firebase.get_all_payments()

    total = len(all_payments)
    success = sum(1 for p in all_payments.values() if p.get("status") == "paid")
    pending = sum(1 for p in all_payments.values() if p.get("status") in ("created", "pending", "processing"))
    failed = sum(1 for p in all_payments.values() if p.get("status") == "failed")

    recent = []
    for oid, p in sorted(all_payments.items(),
                         key=lambda x: x[1].get("created_at", 0), reverse=True)[:30]:
        recent.append({
            "order_id": oid,
            "user_id": p.get("user_id"),
            "provider": p.get("provider"),
            "amount": p.get("amount"),
            "currency": p.get("currency"),
            "status": p.get("status"),
            "created_at": p.get("created_at"),
        })
    return jsonify({
        "status": "success",
        "total": total, "success": success,
        "pending": pending, "failed": failed,
        "recent": recent,
    })


@admin_bp.get("/sessions")
def api_admin_sessions():
    sid, item, error = require_admin()
    if error:
        return error
    sessions = get_sessions()
    # Для in-memory — можем отдать список; для Redis — только count
    return jsonify({
        "status": "success",
        "count": sessions.count(),
        "store": "redis" if sessions._use_redis else "memory",
    })


@admin_bp.get("/system")
def api_admin_system():
    sid, item, error = require_admin()
    if error:
        return error
    firebase = get_firebase()
    sessions = get_sessions()
    from config import Config
    return jsonify({
        "status": "success",
        "uptime": int(time.time() - APP_START_TIME),
        "version": Config.APP_VERSION,
        "sessions_count": sessions.count(),
        "firebase_connected": firebase.is_connected(),
    })

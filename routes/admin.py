from __future__ import annotations

import logging
import time
from typing import Any, Dict

from flask import Blueprint, jsonify

from config import Config
from services.auth_guard import require_admin
from services.runtime import (
    APP_START_TIME,
    get_firebase,
    get_sessions,
)


log = logging.getLogger("admin-routes")

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/api/admin",
)


# ============================================================
# PAYMENT OVERVIEW
# ============================================================
@admin_bp.get("/payments")
@require_admin
def api_admin_payments(
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

    all_payments = (
        firebase.get_all_payments()
        or {}
    )

    if not isinstance(
        all_payments,
        dict,
    ):
        all_payments = {}

    total = len(
        all_payments
    )

    success = sum(
        1
        for payment in all_payments.values()
        if isinstance(payment, dict)
        and payment.get("status") == "paid"
    )

    pending = sum(
        1
        for payment in all_payments.values()
        if isinstance(payment, dict)
        and payment.get("status")
        in {
            "created",
            "pending",
            "processing",
        }
    )

    failed = sum(
        1
        for payment in all_payments.values()
        if isinstance(payment, dict)
        and payment.get("status") == "failed"
    )

    sorted_payments = sorted(
        all_payments.items(),
        key=lambda entry: int(
            (
                entry[1]
                if isinstance(
                    entry[1],
                    dict,
                )
                else {}
            ).get(
                "created_at",
                0,
            )
            or 0
        ),
        reverse=True,
    )

    recent = []

    for order_id, payment in sorted_payments[:30]:
        if not isinstance(
            payment,
            dict,
        ):
            continue

        recent.append(
            {
                "order_id": order_id,
                "user_id": payment.get(
                    "user_id"
                ),
                "provider": payment.get(
                    "provider"
                ),
                "amount": payment.get(
                    "amount"
                ),
                "currency": payment.get(
                    "currency"
                ),
                "status": payment.get(
                    "status"
                ),
                "created_at": payment.get(
                    "created_at"
                ),
            }
        )

    return jsonify(
        {
            "status": "success",
            "total": total,
            "success": success,
            "pending": pending,
            "failed": failed,
            "recent": recent,
        }
    )


# ============================================================
# ACTIVE SESSIONS
# ============================================================
@admin_bp.get("/sessions")
@require_admin
def api_admin_sessions(
    sid: str,
    item: Dict[str, Any],
):
    sessions = get_sessions()

    if not sessions:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "session service unavailable",
                }
            ),
            503,
        )

    try:
        count = sessions.count()
    except Exception:
        log.exception(
            "Could not count sessions"
        )
        count = 0

    # Avoid depending directly on private internals
    # unless the attribute exists.
    use_redis = bool(
        getattr(
            sessions,
            "_use_redis",
            False,
        )
    )

    return jsonify(
        {
            "status": "success",
            "count": count,
            "store": (
                "redis"
                if use_redis
                else "memory"
            ),
        }
    )


# ============================================================
# SYSTEM STATUS
# ============================================================
@admin_bp.get("/system")
@require_admin
def api_admin_system(
    sid: str,
    item: Dict[str, Any],
):
    firebase = get_firebase()
    sessions = get_sessions()

    try:
        session_count = (
            sessions.count()
            if sessions
            else 0
        )
    except Exception:
        log.exception(
            "Could not count sessions"
        )
        session_count = 0

    firebase_connected = False

    if firebase:
        try:
            firebase_connected = bool(
                firebase.is_connected()
            )
        except Exception:
            log.exception(
                "Firebase connectivity check failed"
            )

    return jsonify(
        {
            "status": "success",
            "uptime": int(
                time.time()
                - APP_START_TIME
            ),
            "version": Config.APP_VERSION,
            "sessions_count": session_count,
            "firebase_connected": firebase_connected,
        }
    )

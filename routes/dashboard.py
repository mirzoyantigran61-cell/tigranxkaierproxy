from __future__ import annotations

import logging
import time
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from services.auth_guard import require_session
from services.runtime import (
    get_firebase,
    user_storage_id,
)

log = logging.getLogger("dashboard-routes")

dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/api/dashboard",
)


def _json() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _client_ip() -> str:
    # app.py already uses ProxyFix.
    return str(request.remote_addr or "").strip()


@dashboard_bp.get("/overview")
@require_session
def dashboard_overview(
    sid: str,
    item: Dict[str, Any],
):
    firebase = get_firebase()

    if not firebase:
        return jsonify({
            "status": "error",
            "message": "database unavailable",
        }), 503

    user_id = user_storage_id(sid, item)

    try:
        chats = firebase.get_chats(user_id) or {}
    except Exception:
        log.exception("Could not load chats")
        chats = {}

    try:
        images = firebase.get_images(user_id) or {}
    except Exception:
        log.exception("Could not load images")
        images = {}

    return jsonify({
        "status": "success",
        "user": {
            "uid": item.get("uid") or item.get("user_id"),
            "email": item.get("email"),
            "role": item.get("role", "user"),
            "name": item.get("name") or item.get("display_name"),
        },
        "stats": {
            "chats": len(chats) if isinstance(chats, dict) else 0,
            "images": len(images) if isinstance(images, dict) else 0,
        },
        "server_time": int(time.time()),
    })


@dashboard_bp.post("/telemetry")
@require_session
def save_telemetry(
    sid: str,
    item: Dict[str, Any],
):
    payload = _json()

    user_id = user_storage_id(sid, item)

    # These values describe the browser/device only.
    # They are never used for authentication or authorization.
    allowed = {
        "browser",
        "browser_version",
        "os",
        "os_version",
        "platform",
        "language",
        "timezone",
        "screen_width",
        "screen_height",
        "pixel_ratio",
        "touch",
        "online",
        "latency_ms",
    }

    telemetry = {}

    for key in allowed:
        if key not in payload:
            continue

        value = payload[key]

        if isinstance(value, (str, int, float, bool)) or value is None:
            telemetry[key] = value

    # Limit arbitrary string sizes.
    for key, value in list(telemetry.items()):
        if isinstance(value, str):
            telemetry[key] = value[:200]

    telemetry["ip"] = _client_ip()
    telemetry["updated_at"] = int(time.time())

    firebase = get_firebase()

    if not firebase:
        return jsonify({
            "status": "error",
            "message": "database unavailable",
        }), 503

    try:
        firebase.patch(
            f"users/{user_id}/telemetry",
            telemetry,
        )
    except Exception:
        log.exception("Could not save telemetry")

        return jsonify({
            "status": "error",
            "message": "could not save telemetry",
        }), 500

    return jsonify({
        "status": "success",
    })


@dashboard_bp.get("/telemetry")
@require_session
def get_telemetry(
    sid: str,
    item: Dict[str, Any],
):
    user_id = user_storage_id(sid, item)

    firebase = get_firebase()

    if not firebase:
        return jsonify({
            "status": "error",
            "message": "database unavailable",
        }), 503

    try:
        telemetry = firebase.get(
            f"users/{user_id}/telemetry"
        ) or {}
    except Exception:
        log.exception("Could not load telemetry")
        telemetry = {}

    return jsonify({
        "status": "success",
        "telemetry": telemetry,
    })

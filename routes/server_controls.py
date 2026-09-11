from __future__ import annotations

import logging
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from services.auth_guard import require_admin
from services.runtime import (
    get_firebase,
    get_tools,
)


log = logging.getLogger("server-controls")

server_controls_bp = Blueprint(
    "server_controls",
    __name__,
    url_prefix="/api/server-controls",
)


ALLOWED_SETTINGS = {
    "maintenance_mode",
    "ai_enabled",
    "image_gen_enabled",
    "logging",
}


def _json() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@server_controls_bp.get("")
@require_admin
def get_server_controls(
    sid: str,
    item: Dict[str, Any],
):
    firebase = get_firebase()

    if not firebase:
        return jsonify({
            "status": "error",
            "message": "database unavailable",
        }), 503

    try:
        settings = firebase.get_server_settings() or {}
    except Exception:
        log.exception("Could not load server settings")
        return jsonify({
            "status": "error",
            "message": "could not load settings",
        }), 500

    result = {}

    for key in ALLOWED_SETTINGS:
        result[key] = bool(
            settings.get(key, False)
        )

    return jsonify({
        "status": "success",
        "settings": result,
    })


@server_controls_bp.patch("")
@require_admin
def update_server_controls(
    sid: str,
    item: Dict[str, Any],
):
    payload = _json()

    if not payload:
        return jsonify({
            "status": "error",
            "message": "empty payload",
        }), 400

    updates = {}

    for key, value in payload.items():
        if key not in ALLOWED_SETTINGS:
            continue

        if not isinstance(value, bool):
            return jsonify({
                "status": "error",
                "message": f"{key} must be boolean",
            }), 400

        updates[key] = value

    if not updates:
        return jsonify({
            "status": "error",
            "message": "no allowed settings provided",
        }), 400

    firebase = get_firebase()

    if not firebase:
        return jsonify({
            "status": "error",
            "message": "database unavailable",
        }), 503

    try:
        firebase.patch(
            "server_settings",
            updates,
        )
    except Exception:
        log.exception("Could not update server settings")

        return jsonify({
            "status": "error",
            "message": "could not update settings",
        }), 500

    # Keep the tool layer/cache in sync where supported.
    tools = get_tools()

    if tools and hasattr(
        tools,
        "invalidate_cache",
    ):
        try:
            tools.invalidate_cache()
        except Exception:
            log.exception(
                "Tool cache invalidation failed"
            )

    # Maintenance middleware cache will be invalidated later
    # when middleware/maintenance.py is added.

    try:
        firebase.audit(
            {
                "action": "server_settings_update",
                "admin_uid": (
                    item.get("uid")
                    or item.get("user_id")
                    or item.get("login")
                ),
                "changes": updates,
            }
        )
    except Exception:
        log.exception(
            "Could not write server-settings audit"
        )

    return jsonify({
        "status": "success",
        "settings": updates,
    })

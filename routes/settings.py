from __future__ import annotations

import logging
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from services.auth_guard import require_session
from services.runtime import (
    get_firebase,
    user_storage_id,
)

log = logging.getLogger("settings-routes")

settings_bp = Blueprint(
    "settings",
    __name__,
    url_prefix="/api/settings",
)


ALLOWED_SETTINGS = {
    "language",
    "theme",
    "accent_color",
    "notifications",
    "sound",
    "animations",
    "compact_mode",
    "send_on_enter",
    "markdown",
}


DEFAULT_SETTINGS = {
    "language": "ru",
    "theme": "dark",
    "accent_color": "cyan",
    "notifications": True,
    "sound": False,
    "animations": True,
    "compact_mode": False,
    "send_on_enter": True,
    "markdown": True,
}


def _json() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _sanitize_settings(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    for key, value in payload.items():
        if key not in ALLOWED_SETTINGS:
            continue

        if key == "language":
            value = str(value).strip().lower()[:10]

            if value not in {
                "ru",
                "en",
                "hy",
            }:
                continue

        elif key == "theme":
            value = str(value).strip().lower()

            if value not in {
                "dark",
                "light",
                "system",
            }:
                continue

        elif key == "accent_color":
            value = str(value).strip().lower()[:30]

        elif key in {
            "notifications",
            "sound",
            "animations",
            "compact_mode",
            "send_on_enter",
            "markdown",
        }:
            if not isinstance(value, bool):
                continue

        result[key] = value

    return result


# ============================================================
# GET MY SETTINGS
# ============================================================
@settings_bp.get("")
@require_session
def get_my_settings(
    sid: str,
    item: Dict[str, Any],
):
    firebase = get_firebase()

    if not firebase:
        return jsonify({
            "status": "error",
            "message": "database unavailable",
        }), 503

    user_id = user_storage_id(
        sid,
        item,
    )

    try:
        stored = (
            firebase.get_user_settings(
                user_id
            )
            or {}
        )
    except Exception:
        log.exception(
            "Could not load user settings"
        )
        stored = {}

    settings = dict(
        DEFAULT_SETTINGS
    )

    if isinstance(stored, dict):
        settings.update(
            _sanitize_settings(
                stored
            )
        )

    return jsonify({
        "status": "success",
        "settings": settings,
    })


# ============================================================
# UPDATE MY SETTINGS
# ============================================================
@settings_bp.patch("")
@require_session
def update_my_settings(
    sid: str,
    item: Dict[str, Any],
):
    payload = _json()

    updates = _sanitize_settings(
        payload
    )

    if not updates:
        return jsonify({
            "status": "error",
            "message": "no valid settings provided",
        }), 400

    firebase = get_firebase()

    if not firebase:
        return jsonify({
            "status": "error",
            "message": "database unavailable",
        }), 503

    user_id = user_storage_id(
        sid,
        item,
    )

    try:
        firebase.patch(
            f"user_settings/{user_id}",
            updates,
        )
    except Exception:
        log.exception(
            "Could not update user settings"
        )

        return jsonify({
            "status": "error",
            "message": "could not update settings",
        }), 500

    return jsonify({
        "status": "success",
        "updated": updates,
    })


# ============================================================
# RESET MY SETTINGS
# ============================================================
@settings_bp.post("/reset")
@require_session
def reset_my_settings(
    sid: str,
    item: Dict[str, Any],
):
    firebase = get_firebase()

    if not firebase:
        return jsonify({
            "status": "error",
            "message": "database unavailable",
        }), 503

    user_id = user_storage_id(
        sid,
        item,
    )

    try:
        firebase.delete(
            f"user_settings/{user_id}"
        )
    except Exception:
        log.exception(
            "Could not reset user settings"
        )

        return jsonify({
            "status": "error",
            "message": "could not reset settings",
        }), 500

    return jsonify({
        "status": "success",
        "settings": DEFAULT_SETTINGS,
    })

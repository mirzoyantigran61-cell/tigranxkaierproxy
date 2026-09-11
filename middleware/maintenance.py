from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

from flask import jsonify, request

from services.auth_guard import resolve_optional_user
from services.runtime import get_firebase


log = logging.getLogger("maintenance")


_CACHE_TTL = 10.0
_cache_lock = threading.Lock()
_cache_value: Dict[str, Any] = {}
_cache_ts = 0.0


PUBLIC_PREFIXES = (
    "/health",
    "/api/ping",
    "/api/auth",
    "/api/config/public",
    "/static",
    "/favicon",
    "/login",
    "/verify",
)

PUBLIC_EXACT_PATHS = {
    "/",
    "/panel",
    "/dashboard",
}


def invalidate_maintenance_cache() -> None:
    global _cache_ts

    with _cache_lock:
        _cache_ts = 0.0


def _load_settings() -> Dict[str, Any]:
    global _cache_value
    global _cache_ts

    now = time.monotonic()

    with _cache_lock:
        if (
            _cache_value
            and (now - _cache_ts) < _CACHE_TTL
        ):
            return dict(_cache_value)

    firebase = get_firebase()

    settings: Dict[str, Any] = {}

    if firebase:
        try:
            raw = firebase.get_server_settings() or {}

            if isinstance(raw, dict):
                settings = raw
        except Exception:
            log.exception(
                "Could not load server settings"
            )

    with _cache_lock:
        _cache_value = dict(settings)
        _cache_ts = now

    return settings


def _is_public_path(path: str) -> bool:
    if path in PUBLIC_EXACT_PATHS:
        return True

    return path.startswith(
        PUBLIC_PREFIXES
    )


def _is_admin() -> bool:
    try:
        resolved = resolve_optional_user()

        if not resolved:
            return False

        # Be tolerant if auth_guard returns either:
        # item
        # or (sid, item)
        if isinstance(resolved, tuple):
            if len(resolved) >= 2:
                item = resolved[1]
            else:
                return False
        else:
            item = resolved

        if not isinstance(item, dict):
            return False

        return (
            str(
                item.get(
                    "role",
                    "user",
                )
            ).lower()
            == "admin"
        )

    except Exception:
        log.exception(
            "Optional authentication check failed"
        )
        return False


def check_maintenance():
    """
    Flask before_request middleware.

    Returns None when request may continue.
    Returns a Flask response when request should be blocked.
    """
    path = request.path or "/"

    if _is_public_path(path):
        return None

    settings = _load_settings()

    maintenance_mode = bool(
        settings.get(
            "maintenance_mode",
            False,
        )
    )

    if (
        maintenance_mode
        and path.startswith("/api/")
        and not _is_admin()
    ):
        return (
            jsonify(
                {
                    "status": "error",
                    "code": "maintenance",
                    "message": (
                        "Server is temporarily under maintenance."
                    ),
                }
            ),
            503,
        )

    # AI feature switch
    if (
        path.startswith("/api/ai/")
        and not bool(
            settings.get(
                "ai_enabled",
                True,
            )
        )
    ):
        if not _is_admin():
            return (
                jsonify(
                    {
                        "status": "error",
                        "code": "ai_disabled",
                        "message": (
                            "AI is temporarily disabled."
                        ),
                    }
                ),
                503,
            )

    # Image generation switch
    if (
        path.startswith("/api/images/generate")
        and not bool(
            settings.get(
                "image_gen_enabled",
                True,
            )
        )
    ):
        if not _is_admin():
            return (
                jsonify(
                    {
                        "status": "error",
                        "code": "image_generation_disabled",
                        "message": (
                            "Image generation is temporarily disabled."
                        ),
                    }
                ),
                503,
            )

    return None

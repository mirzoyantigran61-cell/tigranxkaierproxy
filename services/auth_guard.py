"""
TIGRAN AI V4 — authentication and authorization guards.

Supports:
- Firebase ID tokens
- legacy V3 sessions
- role resolution
- HTTP decorators
- optional authentication
- WebSocket token authentication
- recent-auth checks for sensitive operations such as passkey removal
"""
from __future__ import annotations

import functools
import time
from typing import Any, Dict, Optional, Tuple

from flask import jsonify, request

from services.runtime import (
    get_auth,
    get_firebase,
    get_sessions,
)


# ============================================================
# TOKEN / SESSION HELPERS
# ============================================================
def _bearer_token() -> str:
    authorization = str(
        request.headers.get("Authorization", "")
    ).strip()

    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    return ""


def _request_id_token() -> str:
    return str(
        request.headers.get("X-ID-Token")
        or _bearer_token()
        or ""
    ).strip()


def _request_session_id() -> str:
    return str(
        request.headers.get("X-Session-ID")
        or ""
    ).strip()


# ============================================================
# ROLE RESOLUTION
# ============================================================
def _resolve_role(
    uid: str,
    decoded: Optional[Dict[str, Any]] = None,
) -> str:
    decoded = decoded or {}

    claim_role = str(
        decoded.get("role", "")
    ).strip().lower()

    if claim_role in {
        "admin",
        "user",
    }:
        return claim_role

    firebase = get_firebase()

    if not firebase or not uid:
        return "user"

    try:
        admin_record = firebase.get_admin(uid)

        if admin_record:
            return "admin"
    except Exception:
        pass

    try:
        stored_role = firebase.get_role(uid)

        if isinstance(stored_role, dict):
            stored_role = (
                stored_role.get("role")
                or stored_role.get("value")
            )

        role = str(
            stored_role or ""
        ).strip().lower()

        if role in {
            "admin",
            "user",
        }:
            return role

    except Exception:
        pass

    return "user"


# ============================================================
# FIREBASE AUTH
# ============================================================
def authenticate_token(
    token: str,
) -> Optional[Dict[str, Any]]:
    """
    Verify a Firebase ID token and return normalized auth data.
    """
    token = str(token or "").strip()

    if not token:
        return None

    auth_service = get_auth()

    if not auth_service:
        return None

    decoded = auth_service.verify_id_token(
        token
    )

    if not decoded:
        return None

    uid = str(
        decoded.get("uid")
        or decoded.get("sub")
        or ""
    ).strip()

    if not uid:
        return None

    role = _resolve_role(
        uid,
        decoded,
    )

    item: Dict[str, Any] = {
        "uid": uid,
        "user_id": uid,
        "email": decoded.get("email"),
        "email_verified": bool(
            decoded.get("email_verified", False)
        ),
        "role": role,
        "provider": "firebase",
        "firebase": True,
    }

    auth_time = decoded.get(
        "auth_time"
    )

    if auth_time is not None:
        try:
            item["auth_time"] = int(
                auth_time
            )
        except (TypeError, ValueError):
            pass

    name = decoded.get("name")

    if name:
        item["display_name"] = name

    picture = decoded.get("picture")

    if picture:
        item["photo_url"] = picture

    return item


# ============================================================
# LEGACY V3 SESSION
# ============================================================
def _authenticate_legacy_session(
    session_id: str,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    session_id = str(
        session_id or ""
    ).strip()

    if not session_id:
        return None

    sessions = get_sessions()

    if not sessions:
        return None

    item = sessions.get(
        session_id
    )

    if not item:
        return None

    if not isinstance(item, dict):
        return None

    normalized = dict(item)

    normalized.setdefault(
        "provider",
        "legacy",
    )

    normalized.setdefault(
        "firebase",
        False,
    )

    normalized.setdefault(
        "role",
        "user",
    )

    return session_id, normalized


# ============================================================
# CURRENT REQUEST AUTH
# ============================================================
def resolve_optional_user() -> Optional[Dict[str, Any]]:
    """
    Resolve the current request user if credentials are present.

    Firebase ID token has priority.
    Legacy session is used as fallback.
    """
    token = _request_id_token()

    if token:
        item = authenticate_token(
            token
        )

        if item:
            return item

    session_id = _request_session_id()

    legacy = _authenticate_legacy_session(
        session_id
    )

    if legacy:
        _, item = legacy
        return item

    return None


def _resolve_required_auth(
) -> Tuple[
    Optional[str],
    Optional[Dict[str, Any]],
    Optional[Any],
]:
    """
    Resolve authenticated user for HTTP routes.

    Returns:
        sid, item, error_response
    """
    token = _request_id_token()

    if token:
        item = authenticate_token(
            token
        )

        if not item:
            return (
                None,
                None,
                (
                    jsonify(
                        {
                            "status": "error",
                            "message": "invalid authentication token",
                        }
                    ),
                    401,
                ),
            )

        uid = str(
            item.get("uid", "")
        ).strip()

        return (
            uid,
            item,
            None,
        )

    session_id = _request_session_id()

    if session_id:
        legacy = _authenticate_legacy_session(
            session_id
        )

        if not legacy:
            return (
                None,
                None,
                (
                    jsonify(
                        {
                            "status": "error",
                            "message": "invalid session",
                        }
                    ),
                    401,
                ),
            )

        sid, item = legacy

        return (
            sid,
            item,
            None,
        )

    return (
        None,
        None,
        (
            jsonify(
                {
                    "status": "error",
                    "message": "authentication required",
                }
            ),
            401,
        ),
    )


# ============================================================
# HTTP DECORATORS
# ============================================================
def require_session(
    view_func,
):
    """
    Require either a Firebase ID token or a valid legacy session.

    Wrapped route receives:
        sid
        item
    before its own parameters.
    """
    @functools.wraps(view_func)
    def wrapper(
        *args,
        **kwargs,
    ):
        sid, item, error = (
            _resolve_required_auth()
        )

        if error:
            return error

        return view_func(
            sid,
            item,
            *args,
            **kwargs,
        )

    return wrapper


def require_admin(
    view_func,
):
    """
    Require authenticated admin role.
    """
    @functools.wraps(view_func)
    def wrapper(
        *args,
        **kwargs,
    ):
        sid, item, error = (
            _resolve_required_auth()
        )

        if error:
            return error

        role = str(
            (item or {}).get(
                "role",
                "user",
            )
        ).strip().lower()

        if role != "admin":
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "admin only",
                    }
                ),
                403,
            )

        return view_func(
            sid,
            item,
            *args,
            **kwargs,
        )

    return wrapper


# ============================================================
# RECENT AUTH
# ============================================================
def is_recent_auth(
    item: Optional[Dict[str, Any]],
    max_age_seconds: int = 300,
) -> bool:
    """
    Return True only when Firebase auth_time is recent.

    Future timestamps are rejected as well.
    """
    if not item:
        return False

    try:
        auth_time = int(
            item.get("auth_time")
        )
    except (TypeError, ValueError):
        return False

    try:
        max_age = int(
            max_age_seconds
        )
    except (TypeError, ValueError):
        return False

    if max_age < 0:
        return False

    now = int(
        time.time()
    )

    age = now - auth_time

    return (
        0 <= age <= max_age
    )

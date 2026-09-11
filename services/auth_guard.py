"""
Auth guard — avoids circular imports by not depending on app.py.
"""
from __future__ import annotations

from flask import request, jsonify

from services.runtime import get_sessions


def require_session():
    """Возвращает (sid, session_data, error_response)."""
    sessions = get_sessions()
    if sessions is None:
        return None, None, (jsonify({"status": "error", "message": "server not ready"}), 503)

    sid = (request.headers.get("X-Session-ID") or "").strip()
    if not sid:
        return None, None, (jsonify({"status": "error", "message": "missing session"}), 401)

    item = sessions.get(sid)
    if not item:
        return None, None, (jsonify({"status": "error", "message": "invalid session"}), 401)

    return sid, item, None


def require_admin():
    sid, item, error = require_session()
    if error:
        return None, None, error
    if item.get("role") != "admin":
        return None, None, (jsonify({"status": "error", "message": "admin only"}), 403)
    return sid, item, None

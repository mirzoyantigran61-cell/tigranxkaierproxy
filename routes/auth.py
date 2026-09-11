from __future__ import annotations

import logging
import secrets
import time

from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

from services.runtime import get_firebase, get_sessions, APP_START_TIME
from services.auth_guard import require_session

log = logging.getLogger("auth-routes")

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


def _verify_password(stored: str, provided: str) -> bool:
    """Проверка пароля: hash или plaintext (legacy)."""
    if not stored:
        return False
    if stored.startswith(("pbkdf2:", "scrypt:")):
        try:
            return check_password_hash(stored, provided)
        except Exception:
            return False
    return stored == provided


def _is_hashed(stored: str) -> bool:
    return bool(stored and stored.startswith(("pbkdf2:", "scrypt:")))


@auth_bp.post("/login")
def api_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "username and password required"}), 400

    firebase = get_firebase()
    sessions = get_sessions()

    admin_role = None
    admins = firebase.get_admins()
    for admin_key, admin_data in admins.items():
        if admin_data.get("username") == username:
            stored = admin_data.get("password", "")
            if _verify_password(stored, password):
                admin_role = admin_data.get("role", "admin")
                # Migration: если plaintext — сохранить hash
                if not _is_hashed(stored):
                    try:
                        firebase.patch(f"admins/{admin_key}", {
                            "password": generate_password_hash(password)
                        })
                        log.info("Migrated admin %s to hashed password", username)
                    except Exception:
                        log.exception("Admin password migration failed")
                break

    is_user = False
    key_data = firebase.get_user_key(username)
    if key_data:
        stored = key_data.get("password", "")
        if _verify_password(stored, password):
            is_user = True
            if not _is_hashed(stored):
                try:
                    firebase.patch(f"keys/{username}", {
                        "password": generate_password_hash(password)
                    })
                    log.info("Migrated user %s to hashed password", username)
                except Exception:
                    log.exception("User password migration failed")

    if not admin_role and not is_user:
        return jsonify({"status": "error", "message": "invalid credentials"}), 401

    role = admin_role if admin_role else "user"
    sid = sessions.create(login=username, role=role)
    return jsonify({"status": "success", "session_id": sid, "role": role})


@auth_bp.post("/logout")
def api_logout():
    sid = (request.headers.get("X-Session-ID") or "").strip()
    if sid:
        get_sessions().delete(sid)
    return jsonify({"status": "success"})


@auth_bp.get("/me")
def api_me():
    sid, item, error = require_session()
    if error:
        return error
    return jsonify({
        "status": "success",
        "username": item.get("login"),
        "role": item.get("role", "user"),
        "session_id": sid[:12] + "...",
        "created_at": item.get("created_at"),
    })


@auth_bp.get("/system/health")
def api_health():
    firebase = get_firebase()
    sessions = get_sessions()
    from services.runtime import get_ai
    ai = get_ai()
    from config import Config
    return jsonify({
        "status": "success",
        "version": Config.APP_VERSION,
        "server": "online",
        "database": firebase.is_connected() if firebase else False,
        "ai_configured": ai.is_configured() if ai else False,
        "payments_enabled": Config.PAYMENTS_ENABLED,
        "uptime": int(time.time() - APP_START_TIME),
        "sessions_count": sessions.count() if sessions else 0,
    })


@auth_bp.post("/verify")
def api_verify():
    """Key generation через sub4unlock верификацию."""
    payload = request.get_json(silent=True) or {}
    link = str(payload.get("link", "")).strip()
    if not link:
        return jsonify({"status": "error", "message": "Ссылка пуста."}), 400
    if "sub4unlock.com/LP/LPD.php" not in link:
        return jsonify({"status": "error", "message": "Недействительная ссылка."}), 400

    firebase = get_firebase()
    username = "HIPROXY-" + str(secrets.randbelow(900000) + 100000)
    password = secrets.token_urlsafe(10)
    device_id = "device_" + secrets.token_hex(4)

    ok = firebase.put(f"keys/{username}", {
        "password": generate_password_hash(password),
        "device_id": device_id,
        "created_at": int(time.time()),
    })
    if not ok:
        return jsonify({"status": "error", "message": "Ошибка сохранения ключа."}), 500

    return jsonify({"status": "success", "username": username, "password": password})

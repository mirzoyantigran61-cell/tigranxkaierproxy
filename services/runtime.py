"""
Runtime service registry — holds application singletons
without circular imports.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from config import Config


log = logging.getLogger("runtime")

APP_START_TIME = time.time()


# ============================================================
# SERVICE SINGLETONS
# ============================================================
_firebase_service = None
_ai_service = None
_session_service = None
_payment_service = None
_tool_registry = None
_auth_service = None


# ============================================================
# INITIALIZATION
# ============================================================
def init_services():
    """
    Initialize all application services.

    Called once from app.py before the blueprints are used.
    """
    global _firebase_service
    global _ai_service
    global _session_service
    global _payment_service
    global _tool_registry
    global _auth_service

    from services.firebase_service import FirebaseService
    from services.ai_service import AIService
    from services.session_service import SessionService
    from services.payment_service import PaymentService
    from services.auth_service import AuthService
    from tools.registry import ToolRegistry

    _firebase_service = FirebaseService()

    _session_service = SessionService()

    _ai_service = AIService(
        _firebase_service,
    )

    _payment_service = PaymentService(
        _firebase_service,
    )

    _tool_registry = ToolRegistry(
        _firebase_service,
        _session_service,
    )

    _auth_service = AuthService()

    log.info("All TIGRAN AI services initialized")


# ============================================================
# GETTERS
# ============================================================
def get_firebase() -> Optional["FirebaseService"]:
    return _firebase_service


def get_ai() -> Optional["AIService"]:
    return _ai_service


def get_sessions() -> Optional["SessionService"]:
    return _session_service


def get_payments() -> Optional["PaymentService"]:
    return _payment_service


def get_tools() -> Optional["ToolRegistry"]:
    return _tool_registry


def get_auth() -> Optional["AuthService"]:
    return _auth_service


# ============================================================
# STABLE USER STORAGE ID
# ============================================================
def user_storage_id(sid: str, item: dict | None) -> str:
    """
    Return a stable user identifier for Firebase storage.

    Firebase Auth UID has priority. Legacy accounts fall back to a
    stable username/login instead of a temporary session ID.
    """
    item = item or {}

    uid = str(
        item.get("uid")
        or item.get("user_id")
        or ""
    ).strip()

    if uid:
        return uid

    login = str(
        item.get("username")
        or item.get("login")
        or item.get("email")
        or ""
    ).strip()

    if login:
        return login

    return str(sid or "").strip()


# ============================================================
# RUNTIME LOGGING
# ============================================================
def apply_logging_setting() -> None:
    """
    Apply the server-side logging level.

    Firebase server_settings may override the environment LOG_LEVEL.
    """
    level_name = Config.LOG_LEVEL

    firebase = get_firebase()

    if firebase:
        try:
            settings = firebase.get_server_settings() or {}

            runtime_level = str(
                settings.get("logging", "")
            ).strip().upper()

            if runtime_level in {
                "DEBUG",
                "INFO",
                "WARNING",
                "ERROR",
                "CRITICAL",
            }:
                level_name = runtime_level

        except Exception:
            log.exception(
                "Could not load runtime logging setting"
            )

    level = getattr(
        logging,
        level_name,
        logging.INFO,
    )

    logging.getLogger().setLevel(level)

    log.setLevel(level)

    log.info(
        "Logging level applied: %s",
        logging.getLevelName(level),
    )

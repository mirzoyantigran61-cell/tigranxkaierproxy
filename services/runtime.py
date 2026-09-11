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
_webauthn_service = None


# ============================================================
# INITIALIZATION
# ============================================================
def init_services():
    """
    Initialize all TIGRAN AI application services.

    Called once from app.py during startup.
    """
    global _firebase_service
    global _ai_service
    global _session_service
    global _payment_service
    global _tool_registry
    global _auth_service
    global _webauthn_service

    from services.firebase_service import FirebaseService
    from services.ai_service import AIService
    from services.session_service import SessionService
    from services.payment_service import PaymentService
    from services.auth_service import AuthService
    from services.webauthn_service import WebAuthnService
    from tools.registry import ToolRegistry

    # --------------------------------------------------------
    # Firebase
    # --------------------------------------------------------
    _firebase_service = FirebaseService()

    # --------------------------------------------------------
    # Sessions
    # --------------------------------------------------------
    _session_service = SessionService()

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------
    _ai_service = AIService(
        _firebase_service,
    )

    # --------------------------------------------------------
    # Payments
    # --------------------------------------------------------
    _payment_service = PaymentService(
        _firebase_service,
    )

    # --------------------------------------------------------
    # Tools
    # --------------------------------------------------------
    _tool_registry = ToolRegistry(
        _firebase_service,
        _session_service,
    )

    # --------------------------------------------------------
    # Authentication
    # --------------------------------------------------------
    _auth_service = AuthService()

    # --------------------------------------------------------
    # Passkeys / WebAuthn
    # --------------------------------------------------------
    _webauthn_service = WebAuthnService(
        _firebase_service,
    )

    log.info(
        "All TIGRAN AI V4 services initialized"
    )


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


def get_webauthn() -> Optional["WebAuthnService"]:
    return _webauthn_service


# ============================================================
# STABLE USER STORAGE ID
# ============================================================
def user_storage_id(
    sid: str,
    item: dict | None,
) -> str:
    """
    Return stable user identifier for persistent storage.

    Priority:
    1. Firebase UID
    2. user_id
    3. username/login/email
    4. legacy session ID
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

    return str(
        sid or ""
    ).strip()


# ============================================================
# RUNTIME LOGGING
# ============================================================
def apply_logging_setting() -> None:
    """
    Apply runtime logging configuration.

    Config.LOG_LEVEL controls the actual Python log level.

    server_settings["logging"] is a boolean feature switch:
    False -> suppress normal application logging
    True  -> use Config.LOG_LEVEL
    """
    level_name = str(
        getattr(
            Config,
            "LOG_LEVEL",
            "INFO",
        )
        or "INFO"
    ).strip().upper()

    if level_name not in {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }:
        level_name = "INFO"

    logging_enabled = True

    firebase = get_firebase()

    if firebase:
        try:
            settings = (
                firebase.get_server_settings()
                or {}
            )

            if isinstance(settings, dict):
                value = settings.get(
                    "logging"
                )

                if isinstance(value, bool):
                    logging_enabled = value

        except Exception:
            log.exception(
                "Could not load runtime logging setting"
            )

    if logging_enabled:
        level = getattr(
            logging,
            level_name,
            logging.INFO,
        )
    else:
        # Keep errors and critical problems visible.
        level = logging.ERROR

    logging.getLogger().setLevel(
        level
    )

    log.setLevel(
        level
    )

    log.info(
        "Logging applied: enabled=%s level=%s",
        logging_enabled,
        logging.getLevelName(level),
    )

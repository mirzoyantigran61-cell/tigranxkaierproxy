"""
Runtime service registry — holds singletons, no circular imports.
"""
from __future__ import annotations

import time
import logging
from typing import Optional

from config import Config

log = logging.getLogger("runtime")

# ============================================================
#  SERVICE SINGLETONS
# ============================================================
_firebase_service = None
_ai_service = None
_session_service = None
_payment_service = None
_tool_registry = None

APP_START_TIME = time.time()


def init_services():
    """Инициализация всех сервисов. Вызывается один раз из app.py."""
    global _firebase_service, _ai_service, _session_service, _payment_service, _tool_registry

    from services.firebase_service import FirebaseService
    from services.ai_service import AIService
    from services.session_service import SessionService
    from services.payment_service import PaymentService
    from tools.registry import ToolRegistry

    _firebase_service = FirebaseService()
    _ai_service = AIService(_firebase_service)
    _session_service = SessionService()
    _payment_service = PaymentService(_firebase_service)
    _tool_registry = ToolRegistry(_firebase_service, _session_service)

    log.info("All services initialized")


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

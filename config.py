"""
TIGRAN AI V3 — Configuration Loader
Секреты — из ENV (Railway Variables).
Несекретные настройки — из Firebase.
"""
from __future__ import annotations

import os
import secrets


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, "").strip().lower()
    if val in ("true", "1", "yes", "on"):
        return True
    if val in ("false", "0", "no", "off"):
        return False
    return default


def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (ValueError, TypeError):
        return default


class Config:
    # ============================================================
    #  APP
    # ============================================================
    APP_VERSION = _env("APP_VERSION", "3.0")
    PORT = _env_int("PORT", 8080)
    SECRET_KEY = _env("SECRET_KEY", secrets.token_hex(32))
    LOG_LEVEL = _env("LOG_LEVEL", "INFO").upper()
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    FLASK_ENV = _env("FLASK_ENV", "production")

    # ============================================================
    #  REDIS (SESSION STORE)
    # ============================================================
    REDIS_URL = _env("REDIS_URL", "")

    # ============================================================
    #  FIREBASE (ADMIN SDK)
    # ============================================================
    FIREBASE_DATABASE_URL = _env(
        "FIREBASE_DATABASE_URL",
        "https://yourtigranmods-papaji-devffsrc-default-rtdb.firebaseio.com"
    )
    FIREBASE_SERVICE_ACCOUNT_JSON = _env("FIREBASE_SERVICE_ACCOUNT_JSON", "")

    # ============================================================
    #  OPENAI (СЕКРЕТЫ — ТОЛЬКО ИЗ ENV)
    # ============================================================
    OPENAI_API_KEY = _env("OPENAI_API_KEY", "")
    OPENAI_TEXT_MODEL = _env("OPENAI_TEXT_MODEL", "gpt-5.6-sol")
    OPENAI_IMAGE_MODEL = _env("OPENAI_IMAGE_MODEL", "gpt-image-2.5-flare")
    AI_MAX_OUTPUT_TOKENS = _env_int("AI_MAX_OUTPUT_TOKENS", 4096)
    AI_TEMPERATURE = float(_env("AI_TEMPERATURE", "0.7"))
    AI_HISTORY_LIMIT = _env_int("AI_HISTORY_LIMIT", 20)
    AI_ENABLED = _env_bool("AI_ENABLED", True)
    AI_RATE_LIMIT_PER_MIN = _env_int("AI_RATE_LIMIT_PER_MIN", 20)

    # ============================================================
    #  PAYMENTS
    # ============================================================
    PAYMENTS_ENABLED = _env_bool("PAYMENTS_ENABLED", True)

    # ============================================================
    #  BANK SECRETS (ТОЛЬКО ENV)
    # ============================================================
    AMERIA_MERCHANT_ID = _env("AMERIA_MERCHANT_ID", "")
    AMERIA_USERNAME = _env("AMERIA_USERNAME", "")
    AMERIA_PASSWORD = _env("AMERIA_PASSWORD", "")
    AMERIA_TERMINAL_ID = _env("AMERIA_TERMINAL_ID", "")

    FASTBANK_MERCHANT_ID = _env("FASTBANK_MERCHANT_ID", "")
    FASTBANK_USERNAME = _env("FASTBANK_USERNAME", "")
    FASTBANK_PASSWORD = _env("FASTBANK_PASSWORD", "")
    FASTBANK_API_KEY = _env("FASTBANK_API_KEY", "")
    FASTBANK_SECRET = _env("FASTBANK_SECRET", "")
    FASTBANK_WEBHOOK_SECRET = _env("FASTBANK_WEBHOOK_SECRET", "")

    CIS_MERCHANT_ID = _env("CIS_MERCHANT_ID", "")
    CIS_API_KEY = _env("CIS_API_KEY", "")
    CIS_SECRET = _env("CIS_SECRET", "")

    KAZAKHSTAN_MERCHANT_ID = _env("KAZAKHSTAN_MERCHANT_ID", "")
    KAZAKHSTAN_API_KEY = _env("KAZAKHSTAN_API_KEY", "")
    KAZAKHSTAN_SECRET = _env("KAZAKHSTAN_SECRET", "")

    # ============================================================
    #  PROXY
    # ============================================================
    UPSTREAM_BASE_URL = _env("UPSTREAM_BASE_URL", "http://127.0.0.1:9000").rstrip("/") + "/"
    PROXY_VER_ADDR = _env("PROXY_VER_ADDR", "https://tigranxkaierproxy-production.up.railway.app/")
    SESSION_TTL = _env_int("SESSION_TTL", 43200)

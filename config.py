"""
TIGRAN AI V4 — Configuration Loader

Секреты загружаются только из ENV / Railway Variables.
Несекретные настройки могут использоваться приложением и Firebase.
"""
from __future__ import annotations

import os
import secrets


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()

    if value in ("true", "1", "yes", "on"):
        return True

    if value in ("false", "0", "no", "off"):
        return False

    return default


def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (ValueError, TypeError):
        return default


def _env_float(name: str, default: float = 0.0) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (ValueError, TypeError):
        return default


class Config:
    # ============================================================
    # APP
    # ============================================================
    APP_VERSION = _env("APP_VERSION", "4.0")

    PORT = _env_int("PORT", 8080)

    SECRET_KEY = _env(
        "SECRET_KEY",
        secrets.token_hex(32),
    )

    LOG_LEVEL = _env("LOG_LEVEL", "INFO").upper()

    FLASK_ENV = _env(
        "FLASK_ENV",
        "production",
    )

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # ============================================================
    # REDIS
    # ============================================================
    REDIS_URL = _env(
        "REDIS_URL",
        "",
    )

    # ============================================================
    # FIREBASE ADMIN SDK
    # ============================================================
    FIREBASE_DATABASE_URL = _env(
        "FIREBASE_DATABASE_URL",
        "https://yourtigranmods-papaji-devffsrc-default-rtdb.firebaseio.com",
    )

    FIREBASE_SERVICE_ACCOUNT_JSON = _env(
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        "",
    )

    # ============================================================
    # FIREBASE WEB AUTH
    #
    # FIREBASE_API_KEY и FIREBASE_WEB_CONFIG_JSON —
    # browser Firebase config, не service-account private key.
    # ============================================================
    FIREBASE_API_KEY = _env(
        "FIREBASE_API_KEY",
        "",
    )

    FIREBASE_WEB_CONFIG_JSON = _env(
        "FIREBASE_WEB_CONFIG_JSON",
        "",
    )

    # ============================================================
    # OPENAI
    # ============================================================
    OPENAI_API_KEY = _env(
        "OPENAI_API_KEY",
        "",
    )

    OPENAI_TEXT_MODEL = _env(
        "OPENAI_TEXT_MODEL",
        "gpt-5.6-sol",
    )

    OPENAI_IMAGE_MODEL = _env(
        "OPENAI_IMAGE_MODEL",
        "gpt-image-2",
    )

    AI_MAX_OUTPUT_TOKENS = _env_int(
        "AI_MAX_OUTPUT_TOKENS",
        4096,
    )

    AI_TEMPERATURE = _env_float(
        "AI_TEMPERATURE",
        0.7,
    )

    AI_HISTORY_LIMIT = _env_int(
        "AI_HISTORY_LIMIT",
        20,
    )

    AI_ENABLED = _env_bool(
        "AI_ENABLED",
        True,
    )

    AI_RATE_LIMIT_PER_MIN = _env_int(
        "AI_RATE_LIMIT_PER_MIN",
        20,
    )

    # ============================================================
    # PAYMENTS
    # ============================================================
    PAYMENTS_ENABLED = _env_bool(
        "PAYMENTS_ENABLED",
        True,
    )

    # ============================================================
    # AMERIABANK
    # ============================================================
    AMERIA_MERCHANT_ID = _env(
        "AMERIA_MERCHANT_ID",
        "",
    )

    AMERIA_USERNAME = _env(
        "AMERIA_USERNAME",
        "",
    )

    AMERIA_PASSWORD = _env(
        "AMERIA_PASSWORD",
        "",
    )

    AMERIA_TERMINAL_ID = _env(
        "AMERIA_TERMINAL_ID",
        "",
    )

    # ============================================================
    # FAST BANK
    # ============================================================
    FASTBANK_MERCHANT_ID = _env(
        "FASTBANK_MERCHANT_ID",
        "",
    )

    FASTBANK_USERNAME = _env(
        "FASTBANK_USERNAME",
        "",
    )

    FASTBANK_PASSWORD = _env(
        "FASTBANK_PASSWORD",
        "",
    )

    FASTBANK_API_KEY = _env(
        "FASTBANK_API_KEY",
        "",
    )

    FASTBANK_SECRET = _env(
        "FASTBANK_SECRET",
        "",
    )

    FASTBANK_WEBHOOK_SECRET = _env(
        "FASTBANK_WEBHOOK_SECRET",
        "",
    )

    # ============================================================
    # CIS
    # ============================================================
    CIS_MERCHANT_ID = _env(
        "CIS_MERCHANT_ID",
        "",
    )

    CIS_API_KEY = _env(
        "CIS_API_KEY",
        "",
    )

    CIS_SECRET = _env(
        "CIS_SECRET",
        "",
    )

    # ============================================================
    # KAZAKHSTAN
    # ============================================================
    KAZAKHSTAN_MERCHANT_ID = _env(
        "KAZAKHSTAN_MERCHANT_ID",
        "",
    )

    KAZAKHSTAN_API_KEY = _env(
        "KAZAKHSTAN_API_KEY",
        "",
    )

    KAZAKHSTAN_SECRET = _env(
        "KAZAKHSTAN_SECRET",
        "",
    )

    # ============================================================
    # PROXY / EXISTING V3 COMPATIBILITY
    # ============================================================
    UPSTREAM_BASE_URL = (
        _env(
            "UPSTREAM_BASE_URL",
            "http://127.0.0.1:9000",
        ).rstrip("/")
        + "/"
    )

    PROXY_VER_ADDR = (
        _env(
            "PROXY_VER_ADDR",
            "https://tigranxkaierproxy-production.up.railway.app",
        ).rstrip("/")
        + "/"
    )

    SESSION_TTL = _env_int(
        "SESSION_TTL",
        43200,
    )

    # ============================================================
    # WEBAUTHN / PASSKEYS
    # ============================================================
    WEBAUTHN_RP_ID = _env(
        "WEBAUTHN_RP_ID",
        "",
    )

    WEBAUTHN_RP_NAME = _env(
        "WEBAUTHN_RP_NAME",
        "TIGRAN AI",
    )

    WEBAUTHN_ORIGIN = _env(
        "WEBAUTHN_ORIGIN",
        "",
    )

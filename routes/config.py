from __future__ import annotations

import json
import logging
from typing import Any, Dict

from flask import Blueprint, jsonify

from config import Config


log = logging.getLogger("config-routes")

config_bp = Blueprint(
    "config",
    __name__,
    url_prefix="/api/config",
)


def _firebase_web_config() -> Dict[str, Any]:
    """
    Возвращает только публичную Firebase Web SDK конфигурацию.

    ВАЖНО:
    service-account JSON и любые приватные серверные ключи
    сюда никогда не попадают.
    """
    raw = getattr(
        Config,
        "FIREBASE_WEB_CONFIG_JSON",
        "",
    )

    if not raw:
        return {}

    try:
        parsed = json.loads(raw)

        if not isinstance(parsed, dict):
            return {}

        allowed = {
            "apiKey",
            "authDomain",
            "projectId",
            "storageBucket",
            "messagingSenderId",
            "appId",
            "measurementId",
            "databaseURL",
        }

        return {
            key: value
            for key, value in parsed.items()
            if key in allowed
        }

    except Exception:
        log.exception(
            "Invalid FIREBASE_WEB_CONFIG_JSON"
        )
        return {}


@config_bp.get("/public")
def public_config():
    """
    Safe frontend configuration.

    No OpenAI keys.
    No Firebase service account.
    No bank credentials.
    No server secrets.
    """
    firebase_config = _firebase_web_config()

    return jsonify({
        "status": "success",
        "app": {
            "version": getattr(
                Config,
                "APP_VERSION",
                "4.0",
            ),
        },
        "firebase": firebase_config,
        "features": {
            "payments": bool(
                getattr(
                    Config,
                    "PAYMENTS_ENABLED",
                    False,
                )
            ),
            "webauthn": bool(
                getattr(
                    Config,
                    "WEBAUTHN_RP_ID",
                    "",
                )
                and getattr(
                    Config,
                    "WEBAUTHN_ORIGIN",
                    "",
                )
            ),
        },
    })

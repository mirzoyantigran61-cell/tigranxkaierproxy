"""
TIGRAN AI V4 — allowlisted server-side AI tools.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List

log = logging.getLogger("tool-registry")


class ToolRegistry:
    def __init__(self, firebase_service, session_service):
        self.firebase = firebase_service
        self.sessions = session_service

        self._handlers: Dict[str, Dict[str, Any]] = {}
        self._definitions: List[Dict[str, Any]] = []

        self._register_all()

    # ============================================================
    # REGISTRATION
    # ============================================================
    def _register_all(self) -> None:
        self._register(
            name="get_server_status",
            description="Получить текущий статус TIGRAN AI сервера.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._get_server_status,
            admin_only=False,
        )

        self._register(
            name="get_account_info",
            description="Получить информацию о текущем аккаунте.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._get_account_info,
            admin_only=False,
        )

        self._register(
            name="get_payment_status",
            description="Получить статус собственного платежа по order_id.",
            parameters={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                    }
                },
                "required": ["order_id"],
                "additionalProperties": False,
            },
            handler=self._get_payment_status,
            admin_only=False,
        )

        self._register(
            name="get_ai_status",
            description="Получить статус сервиса TIGRAN AI.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._get_ai_status,
            admin_only=False,
        )

        self._register(
            name="get_allowed_server_settings",
            description="Получить разрешённые глобальные настройки сервера.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._get_allowed_server_settings,
            admin_only=True,
        )

        self._register(
            name="toggle_allowed_server_setting",
            description="Изменить разрешённую глобальную настройку сервера.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "enum": [
                            "maintenance_mode",
                            "ai_enabled",
                            "image_gen_enabled",
                            "logging",
                        ],
                    },
                    "value": {},
                },
                "required": [
                    "name",
                    "value",
                ],
                "additionalProperties": False,
            },
            handler=self._toggle_setting,
            admin_only=True,
        )

        self._register(
            name="get_active_sessions",
            description="Получить количество активных сессий.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._get_active_sessions,
            admin_only=True,
        )

    def _register(
        self,
        *,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
        admin_only: bool,
    ) -> None:
        self._handlers[name] = {
            "handler": handler,
            "admin_only": admin_only,
        }

        self._definitions.append(
            {
                "type": "function",
                "name": name,
                "description": description,
                "parameters": parameters,
            }
        )

    # ============================================================
    # PUBLIC API
    # ============================================================
    def get_definitions(
        self,
        user_role: str,
    ) -> List[Dict[str, Any]]:
        if user_role == "admin":
            return list(self._definitions)

        return [
            definition
            for definition in self._definitions
            if not self._handlers[
                definition["name"]
            ]["admin_only"]
        ]

    def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        user: Dict[str, Any],
    ) -> Dict[str, Any]:
        entry = self._handlers.get(name)

        if not entry:
            return {
                "status": "error",
                "message": "unknown tool",
            }

        role = str(
            user.get("role", "user")
        ).strip().lower()

        if entry["admin_only"] and role != "admin":
            log.warning(
                "Tool %s denied for role=%s",
                name,
                role,
            )

            return {
                "status": "error",
                "message": "permission denied",
            }

        if not isinstance(arguments, dict):
            return {
                "status": "error",
                "message": "invalid arguments",
            }

        try:
            result = entry["handler"](
                user,
                arguments,
            )

        except Exception:
            log.exception(
                "Tool %s failed",
                name,
            )

            result = {
                "status": "error",
                "message": "tool execution failed",
            }

        try:
            user_id = str(
                user.get("uid")
                or user.get("login")
                or user.get("username")
                or "unknown"
            )

            self.firebase.log_action(
                user_id,
                f"tool:{name}",
                {
                    "arguments": arguments,
                    "result_status": result.get("status"),
                },
            )

        except Exception:
            log.exception(
                "Failed to write tool audit log"
            )

        return result

    # ============================================================
    # HANDLERS
    # ============================================================
    def _get_server_status(
        self,
        user: Dict[str, Any],
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        from config import Config
        from services.runtime import APP_START_TIME

        return {
            "status": "success",
            "uptime": int(
                time.time() - APP_START_TIME
            ),
            "version": Config.APP_VERSION,
            "database": self.firebase.is_connected(),
        }

    def _get_account_info(
        self,
        user: Dict[str, Any],
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "status": "success",
            "uid": user.get("uid"),
            "login": (
                user.get("login")
                or user.get("username")
                or user.get("email")
            ),
            "role": user.get("role", "user"),
        }

    def _get_payment_status(
        self,
        user: Dict[str, Any],
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        order_id = str(
            args.get("order_id", "")
        ).strip()

        if not order_id:
            return {
                "status": "error",
                "message": "order_id required",
            }

        order = self.firebase.get_payment(
            order_id
        )

        if not order:
            return {
                "status": "error",
                "message": "order not found",
            }

        role = str(
            user.get("role", "user")
        ).lower()

        current_user_id = str(
            user.get("uid")
            or user.get("login")
            or user.get("username")
            or ""
        )

        owner_id = str(
            order.get("user_id", "")
        )

        if (
            role != "admin"
            and owner_id != current_user_id
        ):
            return {
                "status": "error",
                "message": "forbidden",
            }

        return {
            "status": "success",
            "order_id": order_id,
            "payment_status": order.get("status"),
            "amount": order.get("amount"),
            "currency": order.get("currency"),
            "provider": order.get("provider"),
        }

    def _get_ai_status(
        self,
        user: Dict[str, Any],
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        from services.runtime import get_ai

        ai = get_ai()

        return {
            "status": "success",
            "configured": bool(
                ai and ai.is_configured()
            ),
        }

    def _get_allowed_server_settings(
        self,
        user: Dict[str, Any],
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        settings = (
            self.firebase.get_server_settings()
            or {}
        )

        allowed = {
            "maintenance_mode",
            "ai_enabled",
            "image_gen_enabled",
            "logging",
        }

        return {
            "status": "success",
            "settings": {
                key: value
                for key, value in settings.items()
                if key in allowed
            },
        }

    def _toggle_setting(
        self,
        user: Dict[str, Any],
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        name = str(
            args.get("name", "")
        ).strip()

        value = args.get("value")

        allowed = {
            "maintenance_mode",
            "ai_enabled",
            "image_gen_enabled",
            "logging",
        }

        if name not in allowed:
            return {
                "status": "error",
                "message": "setting not allowed",
            }

        if name in {
            "maintenance_mode",
            "ai_enabled",
            "image_gen_enabled",
        }:
            if not isinstance(value, bool):
                return {
                    "status": "error",
                    "message": "value must be boolean",
                }

        elif name == "logging":
            value = str(
                value
            ).upper()

            if value not in {
                "DEBUG",
                "INFO",
                "WARNING",
                "ERROR",
                "CRITICAL",
            }:
                return {
                    "status": "error",
                    "message": "invalid logging level",
                }

        ok = self.firebase.update_server_settings(
            {
                name: value,
            }
        )

        if not ok:
            return {
                "status": "error",
                "message": "failed to update setting",
            }

        try:
            from middleware.maintenance import (
                invalidate_maintenance_cache,
            )

            invalidate_maintenance_cache()

        except Exception:
            log.exception(
                "Could not invalidate maintenance cache"
            )

        if name == "logging":
            try:
                from services.runtime import (
                    apply_logging_setting,
                )

                apply_logging_setting()

            except Exception:
                log.exception(
                    "Could not apply logging setting"
                )

        return {
            "status": "success",
            "setting": name,
            "value": value,
        }

    def _get_active_sessions(
        self,
        user: Dict[str, Any],
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            count = self.sessions.count()

        except Exception:
            count = 0

        return {
            "status": "success",
            "count": count,
        }

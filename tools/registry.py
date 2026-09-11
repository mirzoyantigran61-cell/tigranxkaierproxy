"""
Tool Registry — allowlist of server-side tools AI may call.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Callable

log = logging.getLogger("tool-registry")


class ToolRegistry:
    def __init__(self, firebase_service, session_service):
        self.firebase = firebase_service
        self.sessions = session_service
        self._handlers: Dict[str, Callable] = {}
        self._definitions: List[Dict] = []
        self._register_all()

    def _register_all(self):
        self._register(
            name="get_server_status",
            description="Получить статус сервера (uptime, версия, БД).",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._get_server_status,
            admin_only=False,
        )
        self._register(
            name="get_account_info",
            description="Получить информацию об аккаунте пользователя.",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._get_account_info,
            admin_only=False,
        )
        self._register(
            name="get_payment_status",
            description="Получить статус платежа по order_id.",
            parameters={
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
            handler=self._get_payment_status,
            admin_only=False,
        )
        self._register(
            name="get_ai_status",
            description="Проверить статус TIGRAN AI.",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._get_ai_status,
            admin_only=False,
        )
        self._register(
            name="toggle_allowed_server_setting",
            description="Переключить разрешённую настройку сервера.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "boolean"},
                },
                "required": ["name", "value"],
            },
            handler=self._toggle_setting,
            admin_only=True,
        )
        self._register(
            name="get_active_sessions",
            description="Получить список активных сессий (только admin).",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._get_active_sessions,
            admin_only=True,
        )

    def _register(self, name: str, description: str, parameters: Dict,
                  handler: Callable, admin_only: bool):
        self._handlers[name] = {"handler": handler, "admin_only": admin_only}
        self._definitions.append({
            "type": "function",
            "name": name,
            "description": description,
            "parameters": parameters,
        })

    def get_definitions(self, user_role: str) -> List[Dict]:
        if user_role == "admin":
            return list(self._definitions)
        return [d for d in self._definitions
                if not self._handlers[d["name"]]["admin_only"]]

    def execute(self, name: str, arguments: Dict, user: Dict) -> Dict:
        """Выполнить tool. Возвращает результат или ошибку."""
        entry = self._handlers.get(name)
        if not entry:
            return {"status": "error", "message": f"unknown tool: {name}"}

        if entry["admin_only"] and user.get("role") != "admin":
            log.warning("Tool %s denied for user %s (role=%s)",
                        name, user.get("login"), user.get("role"))
            return {"status": "error", "message": "permission denied"}

        try:
            result = entry["handler"](user, arguments)
        except Exception as exc:
            log.exception("Tool %s failed", name)
            result = {"status": "error", "message": str(exc)}

        # Audit log
        try:
            self.firebase.log_action(
                user.get("login", "unknown"),
                f"tool:{name}",
                {"arguments": arguments, "result_status": result.get("status")}
            )
        except Exception:
            pass

        return result

    # ============================================================
    #  HANDLERS
    # ============================================================
    def _get_server_status(self, user: Dict, args: Dict) -> Dict:
        from services.runtime import APP_START_TIME
        from config import Config
        return {
            "status": "success",
            "uptime": int(time.time() - APP_START_TIME),
            "version": Config.APP_VERSION,
            "database": self.firebase.is_connected(),
        }

    def _get_account_info(self, user: Dict, args: Dict) -> Dict:
        return {
            "status": "success",
            "login": user.get("login"),
            "role": user.get("role"),
        }

    def _get_payment_status(self, user: Dict, args: Dict) -> Dict:
        order_id = args.get("order_id", "")
        order = self.firebase.get_payment(order_id)
        if not order:
            return {"status": "error", "message": "order not found"}
        if user.get("role") != "admin" and order.get("user_id") != user.get("login"):
            return {"status": "error", "message": "forbidden"}
        return {
            "status": "success",
            "order_id": order_id,
            "payment_status": order.get("status"),
            "amount": order.get("amount"),
            "currency": order.get("currency"),
        }

    def _get_ai_status(self, user: Dict, args: Dict) -> Dict:
        from services.runtime import get_ai
        ai = get_ai()
        return {"status": "success", "configured": ai.is_configured() if ai else False}

    def _toggle_setting(self, user: Dict, args: Dict) -> Dict:
        name = str(args.get("name", ""))
        value = bool(args.get("value", False))
        allowed = {"Aim Silent", "Backjump Preset", "High Sensi",
                   "Speed Preset", "Visual FX", "BYPASS UPDATE"}
        if name not in allowed:
            return {"status": "error", "message": "setting not allowed"}
        # Только admin (проверено выше)
        return {"status": "success", "setting": name, "value": value}

    def _get_active_sessions(self, user: Dict, args: Dict) -> Dict:
        return {"status": "success", "count": self.sessions.count()}

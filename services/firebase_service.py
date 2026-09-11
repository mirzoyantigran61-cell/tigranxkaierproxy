"""
TIGRAN AI V4 — Firebase Realtime Database Service.

All database access is performed through Firebase Admin SDK.
Client-side direct RTDB access is denied by firebase_rules.json.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

import firebase_admin
from firebase_admin import credentials, db

from config import Config


log = logging.getLogger("firebase-service")


class FirebaseService:
    def __init__(self):
        self._initialized = False
        self._init_error: Optional[str] = None
        self._try_init()

    # ============================================================
    # INITIALIZATION
    # ============================================================
    def _try_init(self) -> None:
        try:
            if not firebase_admin._apps:
                if Config.FIREBASE_SERVICE_ACCOUNT_JSON:
                    cred_dict = json.loads(
                        Config.FIREBASE_SERVICE_ACCOUNT_JSON
                    )

                    cred = credentials.Certificate(
                        cred_dict
                    )
                else:
                    cred = credentials.ApplicationDefault()

                firebase_admin.initialize_app(
                    cred,
                    {
                        "databaseURL": Config.FIREBASE_DATABASE_URL,
                    },
                )

            self._initialized = True
            self._init_error = None

            log.info(
                "Firebase Admin SDK initialized"
            )

        except Exception as exc:
            self._initialized = False
            self._init_error = str(exc)

            log.error(
                "Firebase init failed: %s",
                exc,
            )

    @property
    def enabled(self) -> bool:
        return self._initialized

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def is_connected(self) -> bool:
        if not self._initialized:
            return False

        try:
            db.reference("config").get()
            return True

        except Exception:
            return False

    # ============================================================
    # CORE
    # ============================================================
    def get(
        self,
        path: str,
    ) -> Optional[Any]:
        if not self._initialized:
            return None

        try:
            return db.reference(
                path.strip("/")
            ).get()

        except Exception as exc:
            log.error(
                "Firebase GET %s failed: %s",
                path,
                exc,
            )

            return None

    def put(
        self,
        path: str,
        data: Any,
    ) -> bool:
        if not self._initialized:
            return False

        try:
            db.reference(
                path.strip("/")
            ).set(data)

            return True

        except Exception as exc:
            log.error(
                "Firebase PUT %s failed: %s",
                path,
                exc,
            )

            return False

    def patch(
        self,
        path: str,
        data: Dict[str, Any],
    ) -> bool:
        if not self._initialized:
            return False

        try:
            db.reference(
                path.strip("/")
            ).update(data)

            return True

        except Exception as exc:
            log.error(
                "Firebase PATCH %s failed: %s",
                path,
                exc,
            )

            return False

    def delete(
        self,
        path: str,
    ) -> bool:
        if not self._initialized:
            return False

        try:
            db.reference(
                path.strip("/")
            ).delete()

            return True

        except Exception as exc:
            log.error(
                "Firebase DELETE %s failed: %s",
                path,
                exc,
            )

            return False

    # ============================================================
    # ATOMIC MULTI-PATH UPDATE
    # ============================================================
    def atomic_update(
        self,
        updates: Dict[str, Any],
    ) -> bool:
        """
        Atomically update multiple RTDB paths.

        Keys must be root-relative paths, for example:

        {
            "users/uid/profile": {...},
            "some_index/key": "uid"
        }
        """
        if not self._initialized:
            return False

        if not isinstance(updates, dict) or not updates:
            return False

        normalized: Dict[str, Any] = {}

        for path, value in updates.items():
            clean_path = str(path).strip("/")

            if not clean_path:
                log.error(
                    "atomic_update rejected empty path"
                )
                return False

            normalized[clean_path] = value

        try:
            db.reference("/").update(
                normalized
            )

            return True

        except Exception as exc:
            log.error(
                "Firebase atomic update failed: %s",
                exc,
            )

            return False

    # ============================================================
    # TRANSACTIONAL CREATE-IF-ABSENT
    # ============================================================
    def set_if_absent(
        self,
        path: str,
        value: Any,
    ) -> Optional[Any]:
        """
        Atomically create a value only if the RTDB path is empty.

        Returns the final stored value.

        Used by WebAuthn for stable user handles so concurrent
        registration requests cannot generate different handles.
        """
        if not self._initialized:
            return None

        clean_path = path.strip("/")

        if not clean_path:
            return None

        try:
            ref = db.reference(
                clean_path
            )

            def transaction(current):
                if current is None:
                    return value

                return current

            return ref.transaction(
                transaction
            )

        except Exception as exc:
            log.error(
                "Firebase transaction %s failed: %s",
                path,
                exc,
            )

            return None

    # ============================================================
    # CONFIG
    # ============================================================
    def get_config(self) -> Dict[str, Any]:
        return self.get("config") or {}

    # ============================================================
    # ADMINS / ROLES
    # ============================================================
    def get_admins(self) -> Dict[str, Any]:
        return self.get("admins") or {}

    def get_admin(
        self,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        return self.get(
            f"admins/{user_id}"
        )

    def get_role(
        self,
        user_id: str,
    ) -> Optional[Any]:
        return self.get(
            f"roles/{user_id}"
        )

    # ============================================================
    # LEGACY ACCESS KEYS
    # ============================================================
    def get_user_key(
        self,
        username: str,
    ) -> Optional[Dict[str, Any]]:
        return self.get(
            f"keys/{username}"
        )

    # ============================================================
    # USERS
    # ============================================================
    def get_user(
        self,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        return self.get(
            f"users/{user_id}"
        )

    def set_user(
        self,
        user_id: str,
        data: Dict[str, Any],
    ) -> bool:
        return self.put(
            f"users/{user_id}",
            data,
        )

    def update_user(
        self,
        user_id: str,
        data: Dict[str, Any],
    ) -> bool:
        return self.patch(
            f"users/{user_id}",
            data,
        )

    # ============================================================
    # SERVER SETTINGS
    # ============================================================
    def get_server_settings(
        self,
    ) -> Dict[str, Any]:
        return self.get(
            "server_settings"
        ) or {}

    def update_server_settings(
        self,
        data: Dict[str, Any],
    ) -> bool:
        return self.patch(
            "server_settings",
            data,
        )

    # ============================================================
    # USER SETTINGS
    # ============================================================
    def get_user_settings(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        return self.get(
            f"user_settings/{user_id}"
        ) or {}

    def set_user_settings(
        self,
        user_id: str,
        data: Dict[str, Any],
    ) -> bool:
        return self.put(
            f"user_settings/{user_id}",
            data,
        )

    def update_user_settings(
        self,
        user_id: str,
        data: Dict[str, Any],
    ) -> bool:
        return self.patch(
            f"user_settings/{user_id}",
            data,
        )

    # ============================================================
    # PRODUCTS
    # ============================================================
    def get_products(
        self,
    ) -> Dict[str, Any]:
        return self.get(
            "products"
        ) or {}

    def get_product(
        self,
        product_id: str,
    ) -> Optional[Dict[str, Any]]:
        return self.get(
            f"products/{product_id}"
        )

    # ============================================================
    # PAYMENTS
    # ============================================================
    def get_payment(
        self,
        order_id: str,
    ) -> Optional[Dict[str, Any]]:
        return self.get(
            f"payments/{order_id}"
        )

    def create_payment(
        self,
        order_id: str,
        data: Dict[str, Any],
    ) -> bool:
        return self.put(
            f"payments/{order_id}",
            data,
        )

    def update_payment(
        self,
        order_id: str,
        data: Dict[str, Any],
    ) -> bool:
        return self.patch(
            f"payments/{order_id}",
            data,
        )

    def get_all_payments(
        self,
    ) -> Dict[str, Any]:
        return self.get(
            "payments"
        ) or {}

    # ============================================================
    # ENTITLEMENTS
    # ============================================================
    def get_entitlement(
        self,
        user_id: str,
        product_id: str,
    ) -> Optional[Dict[str, Any]]:
        return self.get(
            f"user_entitlements/{user_id}/{product_id}"
        )

    def set_entitlement(
        self,
        user_id: str,
        product_id: str,
        data: Dict[str, Any],
    ) -> bool:
        return self.put(
            f"user_entitlements/{user_id}/{product_id}",
            data,
        )

    # ============================================================
    # AI CHATS
    # ============================================================
    def get_chats(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        return self.get(
            f"ai_chats/{user_id}"
        ) or {}

    def get_chat(
        self,
        user_id: str,
        chat_id: str,
    ) -> Optional[Dict[str, Any]]:
        return self.get(
            f"ai_chats/{user_id}/{chat_id}"
        )

    def create_chat(
        self,
        user_id: str,
        chat_id: str,
        data: Dict[str, Any],
    ) -> bool:
        return self.put(
            f"ai_chats/{user_id}/{chat_id}",
            data,
        )

    def update_chat_meta(
        self,
        user_id: str,
        chat_id: str,
        data: Dict[str, Any],
    ) -> bool:
        return self.patch(
            f"ai_chats/{user_id}/{chat_id}",
            data,
        )

    def delete_chat(
        self,
        user_id: str,
        chat_id: str,
    ) -> bool:
        return self.delete(
            f"ai_chats/{user_id}/{chat_id}"
        )

    def add_message(
        self,
        user_id: str,
        chat_id: str,
        message_id: str,
        data: Dict[str, Any],
    ) -> bool:
        return self.put(
            f"ai_chats/{user_id}/{chat_id}/messages/{message_id}",
            data,
        )

    def get_messages(
        self,
        user_id: str,
        chat_id: str,
    ) -> Dict[str, Any]:
        return self.get(
            f"ai_chats/{user_id}/{chat_id}/messages"
        ) or {}

    # ============================================================
    # AI IMAGES
    # ============================================================
    def get_images(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        return self.get(
            f"ai_images/{user_id}"
        ) or {}

    def save_image(
        self,
        user_id: str,
        image_id: str,
        data: Dict[str, Any],
    ) -> bool:
        return self.put(
            f"ai_images/{user_id}/{image_id}",
            data,
        )

    def delete_image(
        self,
        user_id: str,
        image_id: str,
    ) -> bool:
        return self.delete(
            f"ai_images/{user_id}/{image_id}"
        )

    # ============================================================
    # WEBAUTHN
    # ============================================================
    def get_webauthn_credentials(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        return self.get(
            f"webauthn_credentials/{user_id}"
        ) or {}

    def get_webauthn_credential(
        self,
        user_id: str,
        credential_key: str,
    ) -> Optional[Dict[str, Any]]:
        return self.get(
            f"webauthn_credentials/{user_id}/{credential_key}"
        )

    def get_webauthn_credential_owner(
        self,
        credential_key: str,
    ) -> Optional[Any]:
        return self.get(
            f"webauthn_credential_index/{credential_key}"
        )

    def get_webauthn_user_handle(
        self,
        user_id: str,
    ) -> Optional[Any]:
        return self.get(
            f"webauthn_user_handles/{user_id}"
        )

    # ============================================================
    # AUDIT LOG
    # ============================================================
    def log_action(
        self,
        user_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        now_ms = int(
            time.time() * 1000
        )

        payload = {
            "action": str(action),
            "details": details or {},
            "ts": int(time.time()),
        }

        return self.put(
            f"audit_log/{user_id}/{now_ms}",
            payload,
        )

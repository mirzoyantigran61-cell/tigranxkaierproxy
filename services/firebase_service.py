"""
Firebase Realtime Database Service — via Firebase Admin SDK.
"""
from __future__ import annotations

import json
import logging
from typing import Optional, Dict, Any

import firebase_admin
from firebase_admin import credentials, db

from config import Config

log = logging.getLogger("firebase-service")


class FirebaseService:
    def __init__(self):
        self._initialized = False
        self._init_error = None
        self._try_init()

    def _try_init(self):
        try:
            if not firebase_admin._apps:
                if Config.FIREBASE_SERVICE_ACCOUNT_JSON:
                    cred_dict = json.loads(Config.FIREBASE_SERVICE_ACCOUNT_JSON)
                    cred = credentials.Certificate(cred_dict)
                else:
                    # Fallback: Application Default Credentials
                    cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred, {
                    "databaseURL": Config.FIREBASE_DATABASE_URL,
                })
            self._initialized = True
            log.info("Firebase Admin SDK initialized")
        except Exception as exc:
            self._init_error = str(exc)
            log.error("Firebase init failed: %s", exc)

    def is_connected(self) -> bool:
        if not self._initialized:
            return False
        try:
            ref = db.reference("config")
            ref.get()  # простой read
            return True
        except Exception:
            return False

    # ============================================================
    #  CORE
    # ============================================================
    def get(self, path: str) -> Optional[Any]:
        if not self._initialized:
            return None
        try:
            return db.reference(path.strip("/")).get()
        except Exception as exc:
            log.error("Firebase GET %s failed: %s", path, exc)
            return None

    def put(self, path: str, data: Any) -> bool:
        if not self._initialized:
            return False
        try:
            db.reference(path.strip("/")).set(data)
            return True
        except Exception as exc:
            log.error("Firebase PUT %s failed: %s", path, exc)
            return False

    def patch(self, path: str, data: Dict) -> bool:
        if not self._initialized:
            return False
        try:
            db.reference(path.strip("/")).update(data)
            return True
        except Exception as exc:
            log.error("Firebase PATCH %s failed: %s", path, exc)
            return False

    def delete(self, path: str) -> bool:
        if not self._initialized:
            return False
        try:
            db.reference(path.strip("/")).delete()
            return True
        except Exception as exc:
            log.error("Firebase DELETE %s failed: %s", path, exc)
            return False

    # ============================================================
    #  HELPERS
    # ============================================================
    def get_config(self) -> Dict:
        return self.get("config") or {}

    def get_products(self) -> Dict:
        return self.get("products") or {}

    def get_product(self, product_id: str) -> Optional[Dict]:
        return self.get(f"products/{product_id}")

    def get_admins(self) -> Dict:
        return self.get("admins") or {}

    def get_user_key(self, username: str) -> Optional[Dict]:
        return self.get(f"keys/{username}")

    def get_payment(self, order_id: str) -> Optional[Dict]:
        return self.get(f"payments/{order_id}")

    def create_payment(self, order_id: str, data: Dict) -> bool:
        return self.put(f"payments/{order_id}", data)

    def update_payment(self, order_id: str, data: Dict) -> bool:
        return self.patch(f"payments/{order_id}", data)

    def get_all_payments(self) -> Dict:
        return self.get("payments") or {}

    def get_entitlement(self, user_id: str, product_id: str) -> Optional[Dict]:
        return self.get(f"user_entitlements/{user_id}/{product_id}")

    def set_entitlement(self, user_id: str, product_id: str, data: Dict) -> bool:
        return self.put(f"user_entitlements/{user_id}/{product_id}", data)

    # ============================================================
    #  AI CHATS
    # ============================================================
    def get_chats(self, user_id: str) -> Dict:
        return self.get(f"ai_chats/{user_id}") or {}

    def get_chat(self, user_id: str, chat_id: str) -> Optional[Dict]:
        return self.get(f"ai_chats/{user_id}/{chat_id}")

    def create_chat(self, user_id: str, chat_id: str, data: Dict) -> bool:
        return self.put(f"ai_chats/{user_id}/{chat_id}", data)

    def update_chat_meta(self, user_id: str, chat_id: str, data: Dict) -> bool:
        return self.patch(f"ai_chats/{user_id}/{chat_id}", data)

    def delete_chat(self, user_id: str, chat_id: str) -> bool:
        return self.delete(f"ai_chats/{user_id}/{chat_id}")

    def add_message(self, user_id: str, chat_id: str, message_id: str, data: Dict) -> bool:
        return self.put(f"ai_chats/{user_id}/{chat_id}/messages/{message_id}", data)

    def get_messages(self, user_id: str, chat_id: str) -> Dict:
        return self.get(f"ai_chats/{user_id}/{chat_id}/messages") or {}

    # ============================================================
    #  AI IMAGES
    # ============================================================
    def get_images(self, user_id: str) -> Dict:
        return self.get(f"ai_images/{user_id}") or {}

    def save_image(self, user_id: str, image_id: str, data: Dict) -> bool:
        return self.put(f"ai_images/{user_id}/{image_id}", data)

    # ============================================================
    #  AUDIT LOG
    # ============================================================
    def log_action(self, user_id: str, action: str, details: Dict) -> bool:
        import time
        return self.put(
            f"audit_log/{user_id}/{int(time.time() * 1000)}",
            {"action": action, "details": details, "ts": int(time.time())}
        )

"""
TIGRAN AI V4 — Firebase Authentication Service.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from firebase_admin import auth as firebase_auth

from config import Config


log = logging.getLogger("auth-service")


class AuthService:
    def __init__(self):
        self.api_key = Config.FIREBASE_API_KEY

    # ============================================================
    # HELPERS
    # ============================================================
    def _identity_url(self, method: str) -> str:
        return (
            "https://identitytoolkit.googleapis.com/v1/accounts:"
            f"{method}?key={self.api_key}"
        )

    def _send_identity_request(
        self,
        method: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "status": "error",
                "message": "Firebase Web API key is not configured.",
            }

        try:
            response = requests.post(
                self._identity_url(method),
                json=payload,
                timeout=20,
            )

            data = response.json()

        except requests.RequestException:
            log.exception(
                "Firebase Identity Toolkit request failed"
            )

            return {
                "status": "error",
                "message": "Authentication service unavailable.",
            }

        except ValueError:
            return {
                "status": "error",
                "message": "Invalid Firebase response.",
            }

        if not response.ok:
            error = (
                data.get("error", {})
                if isinstance(data, dict)
                else {}
            )

            return {
                "status": "error",
                "message": str(
                    error.get(
                        "message",
                        "Authentication failed.",
                    )
                ),
            }

        return {
            "status": "success",
            "data": data,
        }

    # ============================================================
    # EMAIL / PASSWORD SIGN UP
    # ============================================================
    def sign_up(
        self,
        email: str,
        password: str,
    ) -> Dict[str, Any]:
        email = str(email or "").strip()
        password = str(password or "")

        if not email or not password:
            return {
                "status": "error",
                "message": "Email and password are required.",
            }

        return self._send_identity_request(
            "signUp",
            {
                "email": email,
                "password": password,
                "returnSecureToken": True,
            },
        )

    # ============================================================
    # EMAIL / PASSWORD SIGN IN
    # ============================================================
    def sign_in(
        self,
        email: str,
        password: str,
    ) -> Dict[str, Any]:
        email = str(email or "").strip()
        password = str(password or "")

        if not email or not password:
            return {
                "status": "error",
                "message": "Email and password are required.",
            }

        return self._send_identity_request(
            "signInWithPassword",
            {
                "email": email,
                "password": password,
                "returnSecureToken": True,
            },
        )

    # ============================================================
    # PASSWORD RESET
    # ============================================================
    def send_password_reset(
        self,
        email: str,
    ) -> Dict[str, Any]:
        email = str(email or "").strip()

        if not email:
            return {
                "status": "error",
                "message": "Email is required.",
            }

        return self._send_identity_request(
            "sendOobCode",
            {
                "requestType": "PASSWORD_RESET",
                "email": email,
            },
        )

    # ============================================================
    # EMAIL VERIFICATION
    # ============================================================
    def send_email_verification(
        self,
        id_token: str,
    ) -> Dict[str, Any]:
        id_token = str(id_token or "").strip()

        if not id_token:
            return {
                "status": "error",
                "message": "ID token is required.",
            }

        return self._send_identity_request(
            "sendOobCode",
            {
                "requestType": "VERIFY_EMAIL",
                "idToken": id_token,
            },
        )

    # ============================================================
    # VERIFY FIREBASE ID TOKEN
    # ============================================================
    def verify_id_token(
        self,
        id_token: str,
    ) -> Optional[Dict[str, Any]]:
        id_token = str(id_token or "").strip()

        if not id_token:
            return None

        try:
            decoded = firebase_auth.verify_id_token(
                id_token,
                check_revoked=False,
            )

            if not isinstance(decoded, dict):
                return None

            return decoded

        except Exception:
            log.warning(
                "Firebase ID token verification failed",
                exc_info=True,
            )

            return None

    # ============================================================
    # CREATE FIREBASE CUSTOM TOKEN
    # ============================================================
    def create_custom_token(
        self,
        uid: str,
        claims: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        uid = str(uid or "").strip()

        if not uid:
            return None

        try:
            token = firebase_auth.create_custom_token(
                uid,
                developer_claims=claims or None,
            )

            if isinstance(token, bytes):
                return token.decode("utf-8")

            return str(token)

        except Exception:
            log.exception(
                "Firebase custom token creation failed"
            )

            return None

    # ============================================================
    # GET USER
    # ============================================================
    def get_user(
        self,
        uid: str,
    ) -> Optional[Dict[str, Any]]:
        uid = str(uid or "").strip()

        if not uid:
            return None

        try:
            user = firebase_auth.get_user(uid)

            return {
                "uid": user.uid,
                "email": user.email,
                "email_verified": user.email_verified,
                "display_name": user.display_name,
                "photo_url": user.photo_url,
                "disabled": user.disabled,
                "provider_data": [
                    {
                        "provider_id": item.provider_id,
                        "uid": item.uid,
                        "email": item.email,
                        "display_name": item.display_name,
                        "photo_url": item.photo_url,
                    }
                    for item in user.provider_data
                ],
                "tokens_valid_after_timestamp": (
                    user.tokens_valid_after_timestamp
                ),
            }

        except Exception:
            log.exception(
                "Firebase get_user failed"
            )

            return None

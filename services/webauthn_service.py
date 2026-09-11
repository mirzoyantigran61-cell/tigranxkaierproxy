"""
TIGRAN AI V4 — WebAuthn / Passkey service.

Requires:
    webauthn==2.5.0

Security properties:
- one-time registration/login ceremonies
- Redis-backed ceremony storage with atomic consume
- thread-safe in-memory fallback
- Redis Lua rate limiting with memory fallback
- stable random WebAuthn user handles
- user verification REQUIRED
- atomic credential + credential-index updates
- credential sign counter persisted before login succeeds
"""
from __future__ import annotations

import base64
import json
import logging
import secrets
import threading
import time
from typing import Any, Dict, Optional

from firebase_admin import auth as firebase_auth
from redis import Redis

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from config import Config


log = logging.getLogger("webauthn-service")


# ============================================================
# BASE64URL
# ============================================================
def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    value = str(value or "").strip()

    if not value:
        raise ValueError("empty base64url value")

    padding = "=" * (-len(value) % 4)

    return base64.urlsafe_b64decode(
        value + padding
    )


# ============================================================
# CEREMONY STORE
# ============================================================
class CeremonyStore:
    """
    One-time ceremony storage.

    Redis uses GETDEL when supported and a Lua fallback otherwise.
    Memory fallback is protected by a lock.
    """

    def __init__(
        self,
        redis_url: str,
        ttl_seconds: int = 300,
    ):
        self.ttl_seconds = max(
            30,
            int(ttl_seconds),
        )

        self.redis: Optional[Redis] = None

        if redis_url:
            try:
                self.redis = Redis.from_url(
                    redis_url,
                    decode_responses=True,
                )

                self.redis.ping()

            except Exception:
                log.exception(
                    "WebAuthn CeremonyStore Redis unavailable; "
                    "using memory fallback"
                )
                self.redis = None

        self._memory: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(
        ceremony_id: str,
    ) -> str:
        return f"webauthn:ceremony:{ceremony_id}"

    def create(
        self,
        payload: Dict[str, Any],
    ) -> str:
        ceremony_id = secrets.token_urlsafe(32)

        record = {
            "created_at": int(time.time()),
            **payload,
        }

        encoded = json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        if self.redis:
            try:
                self.redis.set(
                    self._key(ceremony_id),
                    encoded,
                    ex=self.ttl_seconds,
                )

                return ceremony_id

            except Exception:
                log.exception(
                    "Redis ceremony create failed; "
                    "using memory fallback"
                )

        with self._lock:
            self._cleanup_memory_locked()

            self._memory[ceremony_id] = record

        return ceremony_id

    def pop(
        self,
        ceremony_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Atomically consume a ceremony exactly once.
        """
        ceremony_id = str(
            ceremony_id or ""
        ).strip()

        if not ceremony_id:
            return None

        if self.redis:
            key = self._key(ceremony_id)

            try:
                # Redis >= 6.2
                raw = self.redis.getdel(key)

            except Exception:
                try:
                    # Atomic fallback for Redis implementations
                    # where GETDEL is unavailable.
                    raw = self.redis.eval(
                        """
                        local v = redis.call('GET', KEYS[1])
                        if v then
                            redis.call('DEL', KEYS[1])
                        end
                        return v
                        """,
                        1,
                        key,
                    )

                except Exception:
                    log.exception(
                        "Redis ceremony consume failed"
                    )
                    raw = None

            if raw:
                try:
                    data = json.loads(raw)

                    if isinstance(data, dict):
                        return data

                except Exception:
                    log.exception(
                        "Invalid ceremony JSON in Redis"
                    )

            if raw is not None:
                return None

        with self._lock:
            self._cleanup_memory_locked()

            return self._memory.pop(
                ceremony_id,
                None,
            )

    def _cleanup_memory_locked(
        self,
    ) -> None:
        now = int(time.time())

        expired = [
            ceremony_id
            for ceremony_id, record
            in self._memory.items()
            if (
                now
                - int(record.get("created_at", 0))
                > self.ttl_seconds
            )
        ]

        for ceremony_id in expired:
            self._memory.pop(
                ceremony_id,
                None,
            )


# ============================================================
# RATE LIMITER
# ============================================================
class RateLimiter:
    """
    Redis Lua rate limiter with thread-safe in-memory fallback.
    """

    _LUA = """
    local current = redis.call('INCR', KEYS[1])

    if current == 1 then
        redis.call('EXPIRE', KEYS[1], ARGV[1])
    end

    return current
    """

    def __init__(
        self,
        redis_url: str,
        limit: int = 10,
        window_seconds: int = 60,
    ):
        self.limit = max(
            1,
            int(limit),
        )

        self.window_seconds = max(
            1,
            int(window_seconds),
        )

        self.redis: Optional[Redis] = None

        if redis_url:
            try:
                self.redis = Redis.from_url(
                    redis_url,
                    decode_responses=True,
                )

                self.redis.ping()

            except Exception:
                log.exception(
                    "WebAuthn rate-limit Redis unavailable; "
                    "using memory fallback"
                )
                self.redis = None

        self._memory: Dict[str, Dict[str, int]] = {}
        self._lock = threading.Lock()

    def allow(
        self,
        key: str,
    ) -> bool:
        key = str(key or "").strip()

        if not key:
            key = "unknown"

        redis_key = (
            f"ratelimit:webauthn:{key}"
        )

        if self.redis:
            try:
                count = int(
                    self.redis.eval(
                        self._LUA,
                        1,
                        redis_key,
                        self.window_seconds,
                    )
                )

                return count <= self.limit

            except Exception:
                log.exception(
                    "WebAuthn Redis rate limiter failed; "
                    "using memory fallback"
                )

        now = int(time.time())

        with self._lock:
            record = self._memory.get(
                key
            )

            if (
                not record
                or now >= record["expires_at"]
            ):
                self._memory[key] = {
                    "count": 1,
                    "expires_at": (
                        now + self.window_seconds
                    ),
                }

                return True

            record["count"] += 1

            return (
                record["count"]
                <= self.limit
            )


# ============================================================
# WEBAUTHN SERVICE
# ============================================================
class WebAuthnService:
    def __init__(
        self,
        firebase_service,
    ):
        self.firebase = firebase_service

        self.rp_id = (
            Config.WEBAUTHN_RP_ID
            or ""
        ).strip()

        self.rp_name = (
            Config.WEBAUTHN_RP_NAME
            or "TIGRAN AI"
        ).strip()

        self.origin = (
            Config.WEBAUTHN_ORIGIN
            or ""
        ).strip()

        self.ceremonies = CeremonyStore(
            Config.REDIS_URL,
            ttl_seconds=300,
        )

        self.login_limiter = RateLimiter(
            Config.REDIS_URL,
            limit=10,
            window_seconds=60,
        )

    # ============================================================
    # STATUS
    # ============================================================
    def is_configured(
        self,
    ) -> bool:
        return bool(
            self.rp_id
            and self.origin
        )

    def check_login_rate(
        self,
        client_key: str,
    ) -> bool:
        return self.login_limiter.allow(
            client_key
        )

    # ============================================================
    # USER HANDLE
    # ============================================================
    def _get_or_create_user_handle(
        self,
        uid: str,
    ) -> Optional[bytes]:
        """
        WebAuthn user.id must be an opaque stable byte sequence.

        Firebase uid itself is NOT used as the WebAuthn user handle.
        """
        uid = str(uid or "").strip()

        if not uid:
            return None

        existing = (
            self.firebase.get_webauthn_user_handle(
                uid
            )
        )

        if existing is not None:
            try:
                decoded = _b64url_decode(
                    str(existing)
                )

                # Fail closed on corrupted/invalid stored handles.
                if not decoded:
                    raise ValueError(
                        "decoded handle is empty"
                    )

                return decoded

            except Exception:
                log.error(
                    "Corrupted WebAuthn user handle for uid=%s",
                    uid,
                )
                return None

        generated = _b64url_encode(
            secrets.token_bytes(32)
        )

        final_value = (
            self.firebase.set_if_absent(
                f"webauthn_user_handles/{uid}",
                generated,
            )
        )

        if final_value is None:
            return None

        try:
            decoded = _b64url_decode(
                str(final_value)
            )

            if not decoded:
                raise ValueError(
                    "decoded handle is empty"
                )

            return decoded

        except Exception:
            log.error(
                "Invalid WebAuthn user handle after transaction "
                "for uid=%s",
                uid,
            )
            return None

    # ============================================================
    # CREDENTIAL HELPERS
    # ============================================================
    def _credential_descriptors(
        self,
        uid: str,
    ) -> list[PublicKeyCredentialDescriptor]:
        stored = (
            self.firebase.get_webauthn_credentials(
                uid
            )
            or {}
        )

        result: list[
            PublicKeyCredentialDescriptor
        ] = []

        for record in stored.values():
            if not isinstance(
                record,
                dict,
            ):
                continue

            encoded_id = str(
                record.get(
                    "credential_id",
                    "",
                )
            ).strip()

            if not encoded_id:
                continue

            try:
                credential_id = (
                    _b64url_decode(
                        encoded_id
                    )
                )

            except Exception:
                continue

            result.append(
                PublicKeyCredentialDescriptor(
                    id=credential_id,
                )
            )

        return result

    # ============================================================
    # REGISTRATION OPTIONS
    # ============================================================
    def begin_registration(
        self,
        uid: str,
        email: str,
        display_name: str = "",
    ) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "status": "error",
                "message": "Passkeys are not configured.",
            }

        uid = str(uid or "").strip()
        email = str(email or "").strip()

        if not uid or not email:
            return {
                "status": "error",
                "message": "Invalid account.",
            }

        user_handle = (
            self._get_or_create_user_handle(
                uid
            )
        )

        if user_handle is None:
            return {
                "status": "error",
                "message": "Could not prepare passkey account.",
            }

        try:
            options = (
                generate_registration_options(
                    rp_id=self.rp_id,
                    rp_name=self.rp_name,
                    user_id=user_handle,
                    user_name=email,
                    user_display_name=(
                        display_name
                        or email
                    ),
                    exclude_credentials=(
                        self._credential_descriptors(
                            uid
                        )
                    ),
                    authenticator_selection=(
                        AuthenticatorSelectionCriteria(
                            resident_key=(
                                ResidentKeyRequirement.PREFERRED
                            ),
                            user_verification=(
                                UserVerificationRequirement.REQUIRED
                            ),
                        )
                    ),
                )
            )

            ceremony_id = (
                self.ceremonies.create(
                    {
                        "type": "registration",
                        "uid": uid,
                        "challenge": (
                            _b64url_encode(
                                options.challenge
                            )
                        ),
                    }
                )
            )

            return {
                "status": "success",
                "ceremony_id": ceremony_id,
                "options": json.loads(
                    options_to_json(
                        options
                    )
                ),
            }

        except Exception:
            log.exception(
                "WebAuthn registration options failed"
            )

            return {
                "status": "error",
                "message": "Could not start passkey registration.",
            }

    # ============================================================
    # REGISTRATION VERIFY
    # ============================================================
    def finish_registration(
        self,
        ceremony_id: str,
        expected_uid: str,
        credential: Dict[str, Any],
        credential_name: str = "",
    ) -> Dict[str, Any]:
        ceremony = self.ceremonies.pop(
            ceremony_id
        )

        if not ceremony:
            return {
                "status": "error",
                "message": "Passkey ceremony expired or was already used.",
            }

        if ceremony.get("type") != "registration":
            return {
                "status": "error",
                "message": "Invalid passkey ceremony.",
            }

        expected_uid = str(
            expected_uid or ""
        ).strip()

        ceremony_uid = str(
            ceremony.get("uid", "")
        ).strip()

        # Critical binding: ceremony belongs to the authenticated UID.
        if (
            not expected_uid
            or ceremony_uid != expected_uid
        ):
            return {
                "status": "error",
                "message": "Passkey ceremony does not belong to this account.",
            }

        try:
            verification = (
                verify_registration_response(
                    credential=credential,
                    expected_challenge=(
                        _b64url_decode(
                            ceremony["challenge"]
                        )
                    ),
                    expected_rp_id=self.rp_id,
                    expected_origin=self.origin,

                    # Required and intentionally explicit.
                    require_user_verification=True,
                )
            )

        except Exception:
            log.exception(
                "WebAuthn registration verification failed"
            )

            return {
                "status": "error",
                "message": "Passkey verification failed.",
            }

        credential_id = (
            verification.credential_id
        )

        storage_key = _b64url_encode(
            credential_id
        )

        now = int(time.time())

        record = {
            "credential_id": storage_key,
            "public_key": _b64url_encode(
                verification.credential_public_key
            ),
            "sign_count": int(
                verification.sign_count
            ),
            "name": (
                str(
                    credential_name
                    or "Passkey"
                )[:100]
            ),
            "created_at": now,
            "last_used_at": None,
            "device_type": str(
                getattr(
                    verification,
                    "credential_device_type",
                    "",
                )
                or ""
            ),
            "backed_up": bool(
                getattr(
                    verification,
                    "credential_backed_up",
                    False,
                )
            ),
        }

        # Credential and reverse index must appear atomically.
        ok = self.firebase.atomic_update(
            {
                (
                    "webauthn_credentials/"
                    f"{expected_uid}/{storage_key}"
                ): record,

                (
                    "webauthn_credential_index/"
                    f"{storage_key}"
                ): expected_uid,
            }
        )

        if not ok:
            return {
                "status": "error",
                "message": "Could not save passkey.",
            }

        return {
            "status": "success",
            "credential": {
                "id": storage_key,
                "name": record["name"],
                "created_at": now,
            },
        }

    # ============================================================
    # AUTHENTICATION OPTIONS
    # ============================================================
    def begin_authentication(
        self,
        email: str,
    ) -> Dict[str, Any]:
        """
        Returns a generic successful options response even when the
        email is unknown, reducing account-enumeration leakage.
        """
        if not self.is_configured():
            return {
                "status": "error",
                "message": "Passkeys are not configured.",
            }

        email = str(
            email or ""
        ).strip()

        uid: Optional[str] = None
        descriptors: list[
            PublicKeyCredentialDescriptor
        ] = []

        if email:
            try:
                user = (
                    firebase_auth.get_user_by_email(
                        email
                    )
                )

                uid = user.uid

                descriptors = (
                    self._credential_descriptors(
                        uid
                    )
                )

            except Exception:
                # Deliberately generic.
                uid = None
                descriptors = []

        try:
            options = (
                generate_authentication_options(
                    rp_id=self.rp_id,
                    allow_credentials=descriptors,
                    user_verification=(
                        UserVerificationRequirement.REQUIRED
                    ),
                )
            )

            ceremony_id = (
                self.ceremonies.create(
                    {
                        "type": "authentication",
                        "uid": uid,
                        "challenge": (
                            _b64url_encode(
                                options.challenge
                            )
                        ),
                    }
                )
            )

            return {
                "status": "success",
                "ceremony_id": ceremony_id,
                "options": json.loads(
                    options_to_json(
                        options
                    )
                ),
            }

        except Exception:
            log.exception(
                "WebAuthn authentication options failed"
            )

            return {
                "status": "error",
                "message": "Could not start passkey authentication.",
            }

    # ============================================================
    # AUTHENTICATION VERIFY
    # ============================================================
    def finish_authentication(
        self,
        ceremony_id: str,
        credential: Dict[str, Any],
    ) -> Dict[str, Any]:
        ceremony = self.ceremonies.pop(
            ceremony_id
        )

        if not ceremony:
            return {
                "status": "error",
                "message": "Passkey ceremony expired or was already used.",
            }

        if ceremony.get("type") != "authentication":
            return {
                "status": "error",
                "message": "Invalid passkey ceremony.",
            }

        expected_uid = ceremony.get(
            "uid"
        )

        # Generic failure for unknown account.
        if not expected_uid:
            return {
                "status": "error",
                "message": "Passkey authentication failed.",
            }

        try:
            raw_id = str(
                credential.get("rawId")
                or credential.get("id")
                or ""
            ).strip()

            if not raw_id:
                raise ValueError(
                    "credential id missing"
                )

            credential_id = (
                _b64url_decode(
                    raw_id
                )
            )

            storage_key = _b64url_encode(
                credential_id
            )

        except Exception:
            return {
                "status": "error",
                "message": "Passkey authentication failed.",
            }

        owner = (
            self.firebase.get_webauthn_credential_owner(
                storage_key
            )
        )

        if str(owner or "") != str(
            expected_uid
        ):
            return {
                "status": "error",
                "message": "Passkey authentication failed.",
            }

        stored = (
            self.firebase.get_webauthn_credential(
                str(expected_uid),
                storage_key,
            )
        )

        if not stored:
            return {
                "status": "error",
                "message": "Passkey authentication failed.",
            }

        try:
            public_key = _b64url_decode(
                str(
                    stored.get(
                        "public_key",
                        "",
                    )
                )
            )

            current_sign_count = int(
                stored.get(
                    "sign_count",
                    0,
                )
            )

            verification = (
                verify_authentication_response(
                    credential=credential,
                    expected_challenge=(
                        _b64url_decode(
                            ceremony["challenge"]
                        )
                    ),
                    expected_rp_id=self.rp_id,
                    expected_origin=self.origin,
                    credential_public_key=public_key,
                    credential_current_sign_count=(
                        current_sign_count
                    ),

                    # Required and intentionally explicit.
                    require_user_verification=True,
                )
            )

        except Exception:
            log.exception(
                "WebAuthn authentication verification failed"
            )

            return {
                "status": "error",
                "message": "Passkey authentication failed.",
            }

        # IMPORTANT:
        # Sign count must be persisted BEFORE issuing the custom token.
        updated = self.firebase.patch(
            (
                "webauthn_credentials/"
                f"{expected_uid}/{storage_key}"
            ),
            {
                "sign_count": int(
                    verification.new_sign_count
                ),
                "last_used_at": int(
                    time.time()
                ),
            },
        )

        if not updated:
            return {
                "status": "error",
                "message": "Could not update passkey state.",
            }

        try:
            token = firebase_auth.create_custom_token(
                str(expected_uid)
            )

            if isinstance(
                token,
                bytes,
            ):
                token = token.decode(
                    "utf-8"
                )

            token = str(token)

        except Exception:
            log.exception(
                "Firebase custom token creation failed "
                "after passkey authentication"
            )

            return {
                "status": "error",
                "message": "Could not complete authentication.",
            }

        return {
            "status": "success",
            "custom_token": token,
        }

    # ============================================================
    # LIST CREDENTIALS
    # ============================================================
    def list_credentials(
        self,
        uid: str,
    ) -> list[Dict[str, Any]]:
        uid = str(uid or "").strip()

        if not uid:
            return []

        stored = (
            self.firebase.get_webauthn_credentials(
                uid
            )
            or {}
        )

        result: list[
            Dict[str, Any]
        ] = []

        for storage_key, record in stored.items():
            if not isinstance(
                record,
                dict,
            ):
                continue

            result.append(
                {
                    "id": storage_key,
                    "name": record.get(
                        "name",
                        "Passkey",
                    ),
                    "created_at": record.get(
                        "created_at"
                    ),
                    "last_used_at": record.get(
                        "last_used_at"
                    ),
                    "device_type": record.get(
                        "device_type"
                    ),
                    "backed_up": bool(
                        record.get(
                            "backed_up",
                            False,
                        )
                    ),
                }
            )

        result.sort(
            key=lambda item: int(
                item.get("created_at")
                or 0
            ),
            reverse=True,
        )

        return result

    # ============================================================
    # DELETE CREDENTIAL
    # ============================================================
    def remove_user_credential(
        self,
        uid: str,
        storage_key: str,
        *,
        allow_last: bool = False,
    ) -> Dict[str, Any]:
        """
        Route layer must:
        - derive uid from verified authentication
        - require recent authentication
        - never accept allow_last from the client

        allow_last=True is therefore backend-controlled only.
        """
        uid = str(uid or "").strip()
        storage_key = str(
            storage_key or ""
        ).strip()

        if not uid or not storage_key:
            return {
                "status": "error",
                "message": "Invalid credential.",
            }

        credentials = (
            self.firebase.get_webauthn_credentials(
                uid
            )
            or {}
        )

        if storage_key not in credentials:
            return {
                "status": "error",
                "message": "Passkey not found.",
            }

        if (
            len(credentials) <= 1
            and not allow_last
        ):
            return {
                "status": "error",
                "message": "Cannot remove the last passkey.",
            }

        # Credential and reverse index are removed atomically.
        ok = self.firebase.atomic_update(
            {
                (
                    "webauthn_credentials/"
                    f"{uid}/{storage_key}"
                ): None,

                (
                    "webauthn_credential_index/"
                    f"{storage_key}"
                ): None,
            }
        )

        if not ok:
            return {
                "status": "error",
                "message": "Could not remove passkey.",
            }

        return {
            "status": "success",
        }

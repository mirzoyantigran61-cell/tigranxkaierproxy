"""
TIGRAN AI V4 — authentication routes.

Provides:
- Firebase email/password auth
- Firebase ID-token session sync
- current-user endpoint
- logout
- password reset
- email verification
- Google/Firebase token sync
- WebAuthn / Passkeys
- legacy-session compatibility through auth_guard
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from services.auth_guard import (
    authenticate_token,
    is_recent_auth,
    require_session,
)
from services.runtime import (
    get_auth,
    get_firebase,
    get_sessions,
    get_webauthn,
    user_storage_id,
)


log = logging.getLogger("auth-routes")

auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/api/auth",
)


# ============================================================
# WEBAUTHN SERVICE
# ============================================================

def _webauthn():
    service = get_webauthn()

    if service is None:
        raise RuntimeError(
            "WebAuthn service is not ready"
        )

    return service

# ============================================================
# HELPERS
# ============================================================
def _json() -> Dict[str, Any]:
    data = request.get_json(
        silent=True
    )

    if isinstance(data, dict):
        return data

    return {}


def _bearer_token() -> str:
    authorization = str(
        request.headers.get(
            "Authorization",
            "",
        )
    ).strip()

    if authorization.lower().startswith(
        "bearer "
    ):
        return authorization[7:].strip()

    return ""


def _id_token_from_request(
) -> str:
    payload = _json()

    return str(
        request.headers.get(
            "X-ID-Token"
        )
        or _bearer_token()
        or payload.get(
            "id_token"
        )
        or payload.get(
            "idToken"
        )
        or ""
    ).strip()


def _client_key() -> str:
    """
    Rate-limit key for passkey login.

    ProxyFix in app.py should already normalize request.remote_addr.
    """
    return str(
        request.remote_addr
        or "unknown"
    ).strip()


def _public_user(
    item: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "uid": (
            item.get("uid")
            or item.get("user_id")
        ),
        "email": item.get("email"),
        "email_verified": bool(
            item.get(
                "email_verified",
                False,
            )
        ),
        "display_name": (
            item.get("display_name")
            or item.get("name")
        ),
        "photo_url": (
    item.get("photo_url")
    or item.get("picture")
),
        "role": item.get(
            "role",
            "user",
        ),
        "provider": item.get(
            "provider"
        ),
    }


# ============================================================
# EMAIL / PASSWORD — SIGN UP
# ============================================================
@auth_bp.post("/signup")
def signup():
    payload = _json()

    email = str(
        payload.get(
            "email",
            "",
        )
    ).strip()

    password = str(
        payload.get(
            "password",
            "",
        )
    )

    if not email or not password:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": (
                        "email and password required"
                    ),
                }
            ),
            400,
        )

    auth_service = get_auth()

    if auth_service is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "auth service unavailable",
                }
            ),
            503,
        )

    result = auth_service.sign_up(
        email,
        password,
    )

    if result.get("status") != "success":
        return jsonify(result), 400

    data = result.get(
        "data",
        {},
    )

    return jsonify(
        {
            "status": "success",
            "id_token": data.get(
                "idToken"
            ),
            "refresh_token": data.get(
                "refreshToken"
            ),
            "expires_in": data.get(
                "expiresIn"
            ),
            "uid": data.get(
                "localId"
            ),
            "email": data.get(
                "email"
            ),
        }
    )


# ============================================================
# EMAIL / PASSWORD — SIGN IN
# ============================================================
@auth_bp.post("/signin")
def signin():
    payload = _json()

    email = str(
        payload.get(
            "email",
            "",
        )
    ).strip()

    password = str(
        payload.get(
            "password",
            "",
        )
    )

    if not email or not password:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": (
                        "email and password required"
                    ),
                }
            ),
            400,
        )

    auth_service = get_auth()

    if auth_service is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "auth service unavailable",
                }
            ),
            503,
        )

    result = auth_service.sign_in(
        email,
        password,
    )

    if result.get("status") != "success":
        return jsonify(result), 401

    data = result.get(
        "data",
        {},
    )

    return jsonify(
        {
            "status": "success",
            "id_token": data.get(
                "idToken"
            ),
            "refresh_token": data.get(
                "refreshToken"
            ),
            "expires_in": data.get(
                "expiresIn"
            ),
            "uid": data.get(
                "localId"
            ),
            "email": data.get(
                "email"
            ),
        }
    )


# ============================================================
# PASSWORD RESET
# ============================================================
@auth_bp.post("/password-reset")
def password_reset():
    payload = _json()

    email = str(
        payload.get(
            "email",
            "",
        )
    ).strip()

    if not email:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "email required",
                }
            ),
            400,
        )

    auth_service = get_auth()

    if auth_service is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "auth service unavailable",
                }
            ),
            503,
        )

    result = (
        auth_service.send_password_reset(
            email
        )
    )

    if result.get("status") != "success":
        return jsonify(result), 400

    # Keep the public response generic.
    return jsonify(
        {
            "status": "success",
            "message": (
                "If the account exists, "
                "a password-reset email was sent."
            ),
        }
    )


# ============================================================
# SEND EMAIL VERIFICATION
# ============================================================
@auth_bp.post("/email-verification")
def email_verification():
    token = _id_token_from_request()

    if not token:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "authentication required",
                }
            ),
            401,
        )

    auth_service = get_auth()

    if auth_service is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "auth service unavailable",
                }
            ),
            503,
        )

    if not auth_service.verify_id_token(
        token
    ):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "invalid authentication token",
                }
            ),
            401,
        )

    result = (
        auth_service.send_email_verification(
            token
        )
    )

    status_code = (
        200
        if result.get("status")
        == "success"
        else 400
    )

    return jsonify(
        result
    ), status_code


# ============================================================
# FIREBASE TOKEN SYNC
# ============================================================
@auth_bp.post("/session")
def sync_session():
    """
    Verify Firebase ID token and persist/update the V4 profile.

    This is also used after Google sign-in on the frontend.
    """
    token = _id_token_from_request()

    if not token:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "authentication required",
                }
            ),
            401,
        )

    item = authenticate_token(
        token
    )

    if not item:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "invalid authentication token",
                }
            ),
            401,
        )

    firebase = get_firebase()

    if firebase is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "database unavailable",
                }
            ),
            503,
        )

    uid = user_storage_id(
        str(
            item.get("uid")
            or ""
        ),
        item,
    )

    if not uid:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "invalid user",
                }
            ),
            400,
        )

    profile = {
        "uid": item.get(
            "uid"
        ),
        "email": item.get(
            "email"
        ),
        "email_verified": bool(
            item.get(
                "email_verified",
                False,
            )
        ),
        "display_name": item.get(
            "display_name"
        ),
        "photo_url": (
    item.get("photo_url")
    or item.get("picture")
),
        "role": item.get(
            "role",
            "user",
        ),
        "provider": item.get(
            "provider",
            "firebase",
        ),
    }

    try:
        firebase.patch(
            f"users/{uid}",
            profile,
        )
    except Exception:
        log.exception(
            "Could not sync Firebase user profile"
        )

    return jsonify(
        {
            "status": "success",
            "user": _public_user(
                item
            ),
        }
    )


# ============================================================
# GOOGLE LOGIN
# ============================================================
@auth_bp.post("/google")
def google_login():
    """
    Frontend signs into Google through Firebase Authentication.

    The token sent here must therefore be a Firebase ID token,
    not a raw Google OAuth access token.
    """
    token = _id_token_from_request()

    if not token:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "authentication required",
                }
            ),
            401,
        )

    item = authenticate_token(
        token
    )

    if not item:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "invalid Firebase ID token",
                }
            ),
            401,
        )

    return jsonify(
        {
            "status": "success",
            "user": _public_user(
                item
            ),
        }
    )


# ============================================================
# CURRENT USER
# ============================================================
@auth_bp.get("/me")
@require_session
def me(
    sid: str,
    item: Dict[str, Any],
):
    storage_id = user_storage_id(
        sid,
        item,
    )

    return jsonify(
        {
            "status": "success",
            "storage_id": storage_id,
            "user": _public_user(
                item
            ),
        }
    )


# ============================================================
# LOGOUT
# ============================================================
@auth_bp.post("/logout")
def logout():
    """
    Firebase ID tokens are normally signed out client-side.

    A legacy V3 session ID, if present, is deleted server-side.
    """
    session_id = str(
        request.headers.get(
            "X-Session-ID",
            "",
        )
    ).strip()

    if session_id:
        sessions = get_sessions()

        if sessions:
            sessions.delete(
                session_id
            )

    return jsonify(
        {
            "status": "success",
        }
    )


# ============================================================
# PASSKEY — REGISTRATION OPTIONS
# ============================================================
@auth_bp.post("/passkeys/register/options")
@require_session
def passkey_registration_options(
    sid: str,
    item: Dict[str, Any],
):
    uid = str(
        item.get("uid")
        or item.get("user_id")
        or ""
    ).strip()

    # Passkeys are only bound to verified Firebase identities,
    # not legacy username sessions.
    if not uid:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": (
                        "Firebase authentication required"
                    ),
                }
            ),
            401,
        )

    email = str(
        item.get(
            "email",
            "",
        )
    ).strip()

    if not email:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": (
                        "Account email is required"
                    ),
                }
            ),
            400,
        )

    result = (
        _webauthn().begin_registration(
            uid=uid,
            email=email,
            display_name=str(
                item.get(
                    "display_name"
                )
                or email
            ),
        )
    )

    code = (
        200
        if result.get("status")
        == "success"
        else 400
    )

    return jsonify(
        result
    ), code


# ============================================================
# PASSKEY — REGISTRATION VERIFY
# ============================================================
@auth_bp.post("/passkeys/register/verify")
@require_session
def passkey_registration_verify(
    sid: str,
    item: Dict[str, Any],
):
    uid = str(
        item.get("uid")
        or item.get("user_id")
        or ""
    ).strip()

    if not uid:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": (
                        "Firebase authentication required"
                    ),
                }
            ),
            401,
        )

    payload = _json()

    ceremony_id = str(
        payload.get(
            "ceremony_id",
            "",
        )
    ).strip()

    credential = payload.get(
        "credential"
    )

    if not isinstance(
        credential,
        dict,
    ):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "credential required",
                }
            ),
            400,
        )

    result = (
        _webauthn().finish_registration(
            ceremony_id=ceremony_id,
            expected_uid=uid,
            credential=credential,
            credential_name=str(
                payload.get(
                    "name",
                    "Passkey",
                )
            ),
        )
    )

    code = (
        200
        if result.get("status")
        == "success"
        else 400
    )

    return jsonify(
        result
    ), code


# ============================================================
# PASSKEY — LOGIN OPTIONS
# ============================================================
@auth_bp.post("/passkeys/login/options")
def passkey_login_options():
    if not _webauthn().check_login_rate(
        _client_key()
    ):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "too many requests",
                }
            ),
            429,
        )

    payload = _json()

    email = str(
        payload.get(
            "email",
            "",
        )
    ).strip()

    result = (
        _webauthn().begin_authentication(
            email
        )
    )

    code = (
        200
        if result.get("status")
        == "success"
        else 400
    )

    return jsonify(
        result
    ), code


# ============================================================
# PASSKEY — LOGIN VERIFY
# ============================================================
@auth_bp.post("/passkeys/login/verify")
def passkey_login_verify():
    if not _webauthn().check_login_rate(
        _client_key()
    ):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "too many requests",
                }
            ),
            429,
        )

    payload = _json()

    ceremony_id = str(
        payload.get(
            "ceremony_id",
            "",
        )
    ).strip()

    credential = payload.get(
        "credential"
    )

    if not isinstance(
        credential,
        dict,
    ):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "credential required",
                }
            ),
            400,
        )

    result = (
        _webauthn().finish_authentication(
            ceremony_id=ceremony_id,
            credential=credential,
        )
    )

    code = (
        200
        if result.get("status")
        == "success"
        else 401
    )

    return jsonify(
        result
    ), code


# ============================================================
# PASSKEY — LIST
# ============================================================
@auth_bp.get("/passkeys")
@require_session
def passkey_list(
    sid: str,
    item: Dict[str, Any],
):
    uid = str(
        item.get("uid")
        or item.get("user_id")
        or ""
    ).strip()

    if not uid:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": (
                        "Firebase authentication required"
                    ),
                }
            ),
            401,
        )

    return jsonify(
        {
            "status": "success",
            "credentials": (
                _webauthn().list_credentials(
                    uid
                )
            ),
        }
    )


# ============================================================
# PASSKEY — DELETE
# ============================================================
@auth_bp.delete("/passkeys/<credential_id>")
@require_session
def passkey_delete(
    sid: str,
    item: Dict[str, Any],
    credential_id: str,
):
    uid = str(
        item.get("uid")
        or item.get("user_id")
        or ""
    ).strip()

    if not uid:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": (
                        "Firebase authentication required"
                    ),
                }
            ),
            401,
        )

    # Sensitive action: require a recent Firebase authentication.
    if not is_recent_auth(
        item,
        300,
    ):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "recent authentication required",
                }
            ),
            401,
        )

    # Important:
    # allow_last is BACKEND-controlled.
    # It is never read from request JSON/query params.
    result = (
        _webauthn().remove_user_credential(
            uid,
            credential_id,
            allow_last=True,
        )
    )

    code = (
        200
        if result.get("status")
        == "success"
        else 400
    )

    return jsonify(
        result
    ), code

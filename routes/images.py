"""
TIGRAN AI V4 — image generation routes.

Stores only metadata in Firebase.
Generated image payload itself is returned to the client
and is not duplicated into Realtime Database.
"""
from __future__ import annotations

import logging
import secrets
import time
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from services.auth_guard import require_session
from services.runtime import (
    get_ai,
    get_firebase,
    user_storage_id,
)


log = logging.getLogger("image-routes")

images_bp = Blueprint(
    "images",
    __name__,
    url_prefix="/api/images",
)


def _json() -> Dict[str, Any]:
    data = request.get_json(silent=True)

    return data if isinstance(data, dict) else {}


def _now() -> int:
    return int(time.time())


# ============================================================
# GENERATE IMAGE
# ============================================================
@images_bp.post("/generate")
@require_session
def api_generate_image(
    sid: str,
    item: Dict[str, Any],
):
    payload = _json()

    prompt = str(
        payload.get(
            "prompt",
            "",
        )
    ).strip()

    if not prompt:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "prompt required",
                }
            ),
            400,
        )

    ai = get_ai()

    if not ai or not ai.is_configured():
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "AI is not configured",
                }
            ),
            503,
        )

    try:
        result = ai.generate_image(
            prompt
        )

    except Exception:
        log.exception(
            "Image generation failed"
        )

        return (
            jsonify(
                {
                    "status": "error",
                    "message": "image generation failed",
                }
            ),
            500,
        )

    if not isinstance(result, dict):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "invalid image response",
                }
            ),
            500,
        )

    if result.get("status") != "success":
        return jsonify(result), 500

    firebase = get_firebase()

    user_id = user_storage_id(
        sid,
        item,
    )

    image_id = (
        "img_"
        + secrets.token_hex(8)
    )

    # IMPORTANT:
    # Never save base64 image data in Firebase.
    # Only metadata / remote URL if available.
    metadata = {
        "prompt": prompt,
        "created_at": _now(),
        "model": getattr(
            ai,
            "image_model",
            None,
        ),
        "status": "success",
    }

    image_url = result.get(
        "image_url"
    )

    if image_url:
        metadata["image_url"] = image_url

    try:
        if firebase:
            firebase.save_image(
                user_id,
                image_id,
                metadata,
            )

    except Exception:
        log.exception(
            "Failed to save image metadata"
        )

    response = dict(result)

    response["image_id"] = image_id

    return jsonify(
        response
    )


# ============================================================
# IMAGE HISTORY
# ============================================================
@images_bp.get("/history")
@require_session
def api_image_history(
    sid: str,
    item: Dict[str, Any],
):
    firebase = get_firebase()

    if not firebase:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "database unavailable",
                }
            ),
            503,
        )

    user_id = user_storage_id(
        sid,
        item,
    )

    images = (
        firebase.get_images(
            user_id
        )
        or {}
    )

    result = []

    if isinstance(images, dict):
        for image_id, image in images.items():
            if not isinstance(image, dict):
                continue

            # Safety against old records that may contain
            # accidentally stored base64/image payloads.
            clean = {
                key: value
                for key, value in image.items()
                if key not in {
                    "b64",
                    "b64_json",
                    "image_base64",
                    "data",
                }
            }

            result.append(
                {
                    "image_id": image_id,
                    **clean,
                }
            )

    result.sort(
        key=lambda value: int(
            value.get(
                "created_at",
                0,
            )
            or 0
        ),
        reverse=True,
    )

    return jsonify(
        {
            "status": "success",
            "images": result,
        }
    )

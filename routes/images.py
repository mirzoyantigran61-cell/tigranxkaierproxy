from __future__ import annotations

import logging
import secrets
import time

from flask import Blueprint, request, jsonify

from services.runtime import get_firebase, get_ai
from services.auth_guard import require_session

log = logging.getLogger("image-routes")

images_bp = Blueprint("images", __name__, url_prefix="/api/images")


@images_bp.post("/generate")
def api_generate_image():
    sid, item, error = require_session()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        return jsonify({"status": "error", "message": "prompt required"}), 400

    ai = get_ai()
    result = ai.generate_image(prompt)
    if result.get("status") == "success":
        firebase = get_firebase()
        image_id = f"img_{secrets.token_hex(8)}"
        firebase.save_image(sid, image_id, {
            "prompt": prompt,
            "created_at": int(time.time()),
            "model": ai.image_model,
            "status": "success",
            "image_url": result.get("image_url", ""),
        })
        result["image_id"] = image_id

    return jsonify(result)


@images_bp.get("/history")
def api_image_history():
    sid, item, error = require_session()
    if error:
        return error
    firebase = get_firebase()
    images = firebase.get_images(sid)
    result = []
    for iid, img in images.items():
        result.append({"image_id": iid, **img})
    result.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return jsonify({"status": "success", "images": result})

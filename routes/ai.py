"""
TIGRAN AI V4 — AI routes.

Features:
- regular chat
- streaming SSE chat
- OpenAI tool calling
- chat history CRUD
- vision
- partial stream persistence
- exactly one [DONE] on completed SSE responses
"""
from __future__ import annotations

import base64
import json
import logging
import secrets
import time
from typing import Any, Dict

from flask import (
    Blueprint,
    Response,
    jsonify,
    request,
    stream_with_context,
)

from config import Config
from services.auth_guard import require_session
from services.runtime import (
    get_ai,
    get_firebase,
    get_tools,
    user_storage_id,
)


log = logging.getLogger("ai-routes")


ai_bp = Blueprint(
    "ai",
    __name__,
    url_prefix="/api/ai",
)


# ============================================================
# HELPERS
# ============================================================
def _json() -> Dict[str, Any]:
    data = request.get_json(
        silent=True
    )

    return (
        data
        if isinstance(data, dict)
        else {}
    )


def _storage_id(
    sid: str,
    item: Dict[str, Any],
) -> str:
    return user_storage_id(
        sid,
        item,
    )


def _new_id(
    prefix: str,
) -> str:
    return (
        f"{prefix}_"
        f"{secrets.token_hex(8)}"
    )


def _now() -> int:
    return int(
        time.time()
    )


def _sse_json(
    payload: Dict[str, Any],
) -> str:
    return (
        "data: "
        + json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n\n"
    )


def _sse_done() -> str:
    return "data: [DONE]\n\n"


def _load_context(
    firebase,
    user_id: str,
    chat_id: str,
) -> list[Dict[str, Any]]:
    messages = (
        firebase.get_messages(
            user_id,
            chat_id,
        )
        or {}
    )

    if not isinstance(
        messages,
        dict,
    ):
        return []

    ordered = sorted(
        messages.values(),
        key=lambda item: int(
            (
                item
                if isinstance(
                    item,
                    dict,
                )
                else {}
            ).get(
                "ts",
                0,
            )
            or 0
        ),
    )

    try:
        limit = max(
            1,
            int(
                Config.AI_HISTORY_LIMIT
            ),
        )
    except Exception:
        limit = 20

    ordered = ordered[
        -limit:
    ]

    result: list[
        Dict[str, Any]
    ] = []

    for message in ordered:
        if not isinstance(
            message,
            dict,
        ):
            continue

        role = str(
            message.get(
                "role",
                "",
            )
        ).strip()

        content = message.get(
            "content"
        )

        if (
            role
            not in {
                "user",
                "assistant",
                "system",
            }
            or not isinstance(
                content,
                str,
            )
        ):
            continue

        result.append(
            {
                "role": role,
                "content": content,
            }
        )

    return result


def _ensure_chat(
    firebase,
    user_id: str,
    chat_id: str,
    initial_message: str,
) -> str:
    chat_id = str(
        chat_id or ""
    ).strip()

    if chat_id:
        existing = firebase.get_chat(
            user_id,
            chat_id,
        )

        if existing:
            return chat_id

    chat_id = _new_id(
        "chat"
    )

    now = _now()

    firebase.create_chat(
        user_id,
        chat_id,
        {
            "title": (
                initial_message[:60]
                or "New Chat"
            ),
            "created_at": now,
            "updated_at": now,
        },
    )

    return chat_id


def _save_message(
    firebase,
    user_id: str,
    chat_id: str,
    role: str,
    content: str,
) -> None:
    firebase.add_message(
        user_id,
        chat_id,
        _new_id(
            "msg"
        ),
        {
            "role": role,
            "content": content,
            "ts": _now(),
        },
    )


# ============================================================
# CHAT — NON STREAMING
# ============================================================
@ai_bp.post("/chat")
@require_session
def api_chat(
    sid: str,
    item: Dict[str, Any],
):
    payload = _json()

    message = str(
        payload.get(
            "message",
            "",
        )
    ).strip()

    chat_id = str(
        payload.get(
            "chat_id",
            "",
        )
    ).strip()

    if not message:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "empty message",
                }
            ),
            400,
        )

    firebase = get_firebase()
    ai = get_ai()
    tools = get_tools()

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

    user_id = _storage_id(
        sid,
        item,
    )

    chat_id = _ensure_chat(
        firebase,
        user_id,
        chat_id,
        message,
    )

    context = _load_context(
        firebase,
        user_id,
        chat_id,
    )

    context.append(
        {
            "role": "user",
            "content": message,
        }
    )

    try:
        _save_message(
            firebase,
            user_id,
            chat_id,
            "user",
            message,
        )

        if tools:
            result = ai.run_with_tools(
                context,
                tools,
                item,
            )
        else:
            result = ai.chat(
                context
            )

    except Exception:
        log.exception(
            "AI chat request failed"
        )

        return (
            jsonify(
                {
                    "status": "error",
                    "message": "AI request failed",
                }
            ),
            500,
        )

    if (
        not isinstance(
            result,
            dict,
        )
        or result.get(
            "status"
        )
        != "success"
    ):
        return (
            jsonify(
                result
                if isinstance(
                    result,
                    dict,
                )
                else {
                    "status": "error",
                    "message": "AI request failed",
                }
            ),
            500,
        )

    reply = str(
        result.get(
            "reply",
            "",
        )
        or result.get(
            "text",
            "",
        )
    )

    try:
        _save_message(
            firebase,
            user_id,
            chat_id,
            "assistant",
            reply,
        )

        firebase.update_chat_meta(
            user_id,
            chat_id,
            {
                "updated_at": _now(),
            },
        )

    except Exception:
        log.exception(
            "Failed to persist AI response"
        )

    return jsonify(
        {
            "status": "success",
            "reply": reply,
            "chat_id": chat_id,
        }
    )


# ============================================================
# CHAT — STREAMING SSE
# ============================================================
@ai_bp.post("/chat/stream")
@require_session
def api_chat_stream(
    sid: str,
    item: Dict[str, Any],
):
    payload = _json()

    message = str(
        payload.get(
            "message",
            "",
        )
    ).strip()

    chat_id = str(
        payload.get(
            "chat_id",
            "",
        )
    ).strip()

    if not message:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "empty message",
                }
            ),
            400,
        )

    firebase = get_firebase()
    ai = get_ai()
    tools = get_tools()

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

    user_id = _storage_id(
        sid,
        item,
    )

    chat_id = _ensure_chat(
        firebase,
        user_id,
        chat_id,
        message,
    )

    context = _load_context(
        firebase,
        user_id,
        chat_id,
    )

    context.append(
        {
            "role": "user",
            "content": message,
        }
    )

    try:
        _save_message(
            firebase,
            user_id,
            chat_id,
            "user",
            message,
        )

    except Exception:
        log.exception(
            "Failed to persist user message"
        )

        return (
            jsonify(
                {
                    "status": "error",
                    "message": (
                        "Could not save message"
                    ),
                }
            ),
            500,
        )

    def generate():
        accumulated: list[str] = []

        try:
            if tools:
                stream = (
                    ai.run_with_tools_stream(
                        context,
                        tools,
                        item,
                    )
                )
            else:
                stream = ai.chat_stream(
                    context
                )

            for delta in stream:
                if delta is None:
                    continue

                delta = str(
                    delta
                )

                if not delta:
                    continue

                accumulated.append(
                    delta
                )

                yield _sse_json(
                    {
                        "type": "delta",
                        "delta": delta,
                    }
                )

        except GeneratorExit:
            # Client disconnected / Stop button pressed.
            # Do not try to yield anything else.
            log.info(
                "AI stream disconnected: chat=%s",
                chat_id,
            )

            raise

        except Exception:
            log.exception(
                "AI streaming failed: chat=%s",
                chat_id,
            )

            # Warning must be sent BEFORE the final [DONE].
            yield _sse_json(
                {
                    "type": "warning",
                    "message": (
                        "The response ended early."
                    ),
                }
            )

        finally:
            partial_reply = "".join(
                accumulated
            )

            if partial_reply:
                try:
                    _save_message(
                        firebase,
                        user_id,
                        chat_id,
                        "assistant",
                        partial_reply,
                    )

                    firebase.update_chat_meta(
                        user_id,
                        chat_id,
                        {
                            "updated_at": _now(),
                        },
                    )

                except Exception:
                    log.exception(
                        "Failed to persist streamed AI response"
                    )

        # This route — not AIService — owns the SSE terminator.
        # There is exactly one normal completion marker.
        yield _sse_done()

    return Response(
        stream_with_context(
            generate()
        ),
        mimetype=(
            "text/event-stream"
        ),
        headers={
            "Cache-Control": (
                "no-cache, no-transform"
            ),
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Chat-Id": chat_id,
        },
    )


# ============================================================
# CHAT LIST
# ============================================================
@ai_bp.get("/chats")
@require_session
def api_chats(
    sid: str,
    item: Dict[str, Any],
):
    firebase = get_firebase()

    user_id = _storage_id(
        sid,
        item,
    )

    chats = (
        firebase.get_chats(
            user_id
        )
        or {}
    )

    result = []

    if isinstance(
        chats,
        dict,
    ):
        for chat_id, chat in chats.items():
            if not isinstance(
                chat,
                dict,
            ):
                continue

            result.append(
                {
                    "chat_id": chat_id,
                    "title": chat.get(
                        "title",
                        "Untitled",
                    ),
                    "created_at": chat.get(
                        "created_at",
                        0,
                    ),
                    "updated_at": chat.get(
                        "updated_at",
                        0,
                    ),
                }
            )

    result.sort(
        key=lambda value: int(
            value.get(
                "updated_at",
                0,
            )
            or 0
        ),
        reverse=True,
    )

    return jsonify(
        {
            "status": "success",
            "chats": result,
        }
    )


# ============================================================
# CHAT DETAIL
# ============================================================
@ai_bp.get("/chats/<chat_id>")
@require_session
def api_chat_detail(
    sid: str,
    item: Dict[str, Any],
    chat_id: str,
):
    firebase = get_firebase()

    user_id = _storage_id(
        sid,
        item,
    )

    chat = firebase.get_chat(
        user_id,
        chat_id,
    )

    if not chat:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "chat not found",
                }
            ),
            404,
        )

    return jsonify(
        {
            "status": "success",
            "chat": chat,
        }
    )


# ============================================================
# CREATE CHAT
# ============================================================
@ai_bp.post("/chats")
@require_session
def api_chat_create(
    sid: str,
    item: Dict[str, Any],
):
    firebase = get_firebase()

    user_id = _storage_id(
        sid,
        item,
    )

    chat_id = _new_id(
        "chat"
    )

    now = _now()

    firebase.create_chat(
        user_id,
        chat_id,
        {
            "title": "New Chat",
            "created_at": now,
            "updated_at": now,
        },
    )

    return jsonify(
        {
            "status": "success",
            "chat_id": chat_id,
        }
    )


# ============================================================
# RENAME CHAT
# ============================================================
@ai_bp.patch("/chats/<chat_id>")
@require_session
def api_chat_rename(
    sid: str,
    item: Dict[str, Any],
    chat_id: str,
):
    payload = _json()

    title = str(
        payload.get(
            "title",
            "",
        )
    ).strip()[:80]

    if not title:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "title required",
                }
            ),
            400,
        )

    firebase = get_firebase()

    user_id = _storage_id(
        sid,
        item,
    )

    if not firebase.get_chat(
        user_id,
        chat_id,
    ):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "chat not found",
                }
            ),
            404,
        )

    firebase.update_chat_meta(
        user_id,
        chat_id,
        {
            "title": title,
            "updated_at": _now(),
        },
    )

    return jsonify(
        {
            "status": "success",
        }
    )


# ============================================================
# DELETE CHAT
# ============================================================
@ai_bp.delete("/chats/<chat_id>")
@require_session
def api_chat_delete(
    sid: str,
    item: Dict[str, Any],
    chat_id: str,
):
    firebase = get_firebase()

    user_id = _storage_id(
        sid,
        item,
    )

    firebase.delete_chat(
        user_id,
        chat_id,
    )

    return jsonify(
        {
            "status": "success",
        }
    )


# ============================================================
# VISION
# ============================================================
@ai_bp.post("/vision")
@require_session
def api_vision(
    sid: str,
    item: Dict[str, Any],
):
    if "image" not in request.files:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "image required",
                }
            ),
            400,
        )

    file = request.files[
        "image"
    ]

    if (
        not file
        or not file.filename
    ):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "empty image",
                }
            ),
            400,
        )

    allowed_mimes = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    mime = str(
        file.mimetype
        or ""
    ).lower()

    if mime not in allowed_mimes:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "unsupported image format",
                }
            ),
            400,
        )

    # Read at most 8 MB + 1 byte so oversized uploads can be rejected
    # without reading an unlimited body into memory here.
    raw = file.stream.read(
        (8 * 1024 * 1024)
        + 1
    )

    if len(raw) > (
        8 * 1024 * 1024
    ):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": (
                        "image too large (max 8MB)"
                    ),
                }
            ),
            413,
        )

    if not raw:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "empty image",
                }
            ),
            400,
        )

    prompt = str(
        request.form.get(
            "prompt",
            "Describe this image.",
        )
    ).strip()

    if not prompt:
        prompt = "Describe this image."

    image_b64 = base64.b64encode(
        raw
    ).decode(
        "ascii"
    )

    data_uri = (
        f"data:{mime};base64,"
        f"{image_b64}"
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
        result = ai.vision(
            prompt,
            data_uri,
        )

    except Exception:
        log.exception(
            "Vision request failed"
        )

        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Vision request failed",
                }
            ),
            500,
        )

    return jsonify(
        result
    )


# ============================================================
# AI STATUS
# ============================================================
@ai_bp.get("/status")
def api_ai_status():
    ai = get_ai()

    configured = bool(
        ai
        and ai.is_configured()
    )

    return jsonify(
        {
            "status": "success",
            "configured": configured,
            "model": (
                getattr(
                    ai,
                    "text_model",
                    None,
                )
                if configured
                else None
            ),
            "image_model": (
                getattr(
                    ai,
                    "image_model",
                    None,
                )
                if configured
                else None
            ),
        }
    )

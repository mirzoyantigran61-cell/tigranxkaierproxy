from __future__ import annotations

import json
import logging
import secrets
import time

from flask import Blueprint, request, jsonify, Response, stream_with_context

from services.runtime import get_firebase, get_ai, get_tools
from services.auth_guard import require_session
from config import Config

log = logging.getLogger("ai-routes")

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


def _load_context(firebase, user_id: str, chat_id: str) -> list:
    msgs = firebase.get_messages(user_id, chat_id) or {}
    ordered = sorted(msgs.items(), key=lambda x: x[1].get("ts", 0))
    limit = Config.AI_HISTORY_LIMIT
    recent = ordered[-limit:] if len(ordered) > limit else ordered
    return [{"role": m["role"], "content": m["content"]} for _, m in recent]


def _run_tool_loop(ai, tools, messages, user, max_iters: int = 5):
    """Полный tool execution loop."""
    result = ai.create_tool_response(messages, tools.get_definitions(user.get("role", "user")))
    if result.get("status") != "success":
        return result

    response = result["response"]

    for _ in range(max_iters):
        # Извлекаем function_call items
        tool_calls = [item for item in getattr(response, "output", [])
                      if getattr(item, "type", None) == "function_call"]
        if not tool_calls:
            break

        tool_outputs = []
        for call in tool_calls:
            try:
                args = json.loads(call.arguments) if isinstance(call.arguments, str) else (call.arguments or {})
            except Exception:
                args = {}
            output = tools.execute(call.name, args, user)
            tool_outputs.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(output, ensure_ascii=False),
            })

        result = ai.submit_tool_outputs(response.id, tool_outputs)
        if result.get("status") != "success":
            return result
        response = result["response"]

    return {"status": "success", "reply": getattr(response, "output_text", "") or ""}


@ai_bp.post("/chat")
def api_chat():
    sid, item, error = require_session()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    chat_id = str(payload.get("chat_id", "")).strip()
    if not message:
        return jsonify({"status": "error", "message": "empty message"}), 400

    firebase = get_firebase()
    ai = get_ai()
    tools = get_tools()

    # Создаём chat если нет
    if not chat_id:
        chat_id = f"chat_{secrets.token_hex(8)}"
        firebase.create_chat(sid, chat_id, {
            "title": message[:60],
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
        })

    # Загружаем контекст
    context = _load_context(firebase, sid, chat_id)
    context.append({"role": "user", "content": message})

    # Сохраняем user message
    firebase.add_message(sid, chat_id, f"msg_{secrets.token_hex(8)}", {
        "role": "user", "content": message, "ts": int(time.time())
    })

    # Вызываем AI с tools
    result = _run_tool_loop(ai, tools, context, item)
    if result.get("status") != "success":
        return jsonify(result), 500

    reply = result["reply"]

    # Сохраняем assistant message
    firebase.add_message(sid, chat_id, f"msg_{secrets.token_hex(8)}", {
        "role": "assistant", "content": reply, "ts": int(time.time())
    })
    firebase.update_chat_meta(sid, chat_id, {"updated_at": int(time.time())})

    return jsonify({"status": "success", "reply": reply, "chat_id": chat_id})


@ai_bp.post("/chat/stream")
def api_chat_stream():
    sid, item, error = require_session()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    chat_id = str(payload.get("chat_id", "")).strip()
    if not message:
        return jsonify({"status": "error", "message": "empty message"}), 400

    firebase = get_firebase()
    ai = get_ai()

    if not chat_id:
        chat_id = f"chat_{secrets.token_hex(8)}"
        firebase.create_chat(sid, chat_id, {
            "title": message[:60],
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
        })

    context = _load_context(firebase, sid, chat_id)
    context.append({"role": "user", "content": message})

    firebase.add_message(sid, chat_id, f"msg_{secrets.token_hex(8)}", {
        "role": "user", "content": message, "ts": int(time.time())
    })

    accumulated = {"text": ""}

    def generate():
        try:
            for chunk in ai.chat_stream(context, user_role=item.get("role", "user")):
                # парсим delta для накопления
                if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                    try:
                        payload_json = json.loads(chunk[6:].strip())
                        if "delta" in payload_json:
                            accumulated["text"] += payload_json["delta"]
                    except Exception:
                        pass
                yield chunk
        finally:
            # Сохраняем assistant message даже при частичном стриме
            if accumulated["text"]:
                try:
                    firebase.add_message(sid, chat_id, f"msg_{secrets.token_hex(8)}", {
                        "role": "assistant",
                        "content": accumulated["text"],
                        "ts": int(time.time()),
                    })
                    firebase.update_chat_meta(sid, chat_id, {"updated_at": int(time.time())})
                except Exception:
                    log.exception("Failed to save streamed message")

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Chat-Id": chat_id,
        },
    )


@ai_bp.get("/chats")
def api_chats():
    sid, item, error = require_session()
    if error:
        return error
    firebase = get_firebase()
    chats = firebase.get_chats(sid)
    # Возвращаем только метаданные без messages
    result = []
    for cid, c in chats.items():
        result.append({
            "chat_id": cid,
            "title": c.get("title", "Untitled"),
            "created_at": c.get("created_at", 0),
            "updated_at": c.get("updated_at", 0),
        })
    result.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return jsonify({"status": "success", "chats": result})


@ai_bp.get("/chats/<chat_id>")
def api_chat_detail(chat_id):
    sid, item, error = require_session()
    if error:
        return error
    firebase = get_firebase()
    chat = firebase.get_chat(sid, chat_id)
    if not chat:
        return jsonify({"status": "error", "message": "chat not found"}), 404
    return jsonify({"status": "success", "chat": chat})


@ai_bp.post("/chats")
def api_chat_create():
    sid, item, error = require_session()
    if error:
        return error
    chat_id = f"chat_{secrets.token_hex(8)}"
    firebase = get_firebase()
    firebase.create_chat(sid, chat_id, {
        "title": "New Chat",
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    })
    return jsonify({"status": "success", "chat_id": chat_id})


@ai_bp.patch("/chats/<chat_id>")
def api_chat_rename(chat_id):
    sid, item, error = require_session()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()[:80]
    if not title:
        return jsonify({"status": "error", "message": "title required"}), 400
    firebase = get_firebase()
    chat = firebase.get_chat(sid, chat_id)
    if not chat:
        return jsonify({"status": "error", "message": "chat not found"}), 404
    firebase.update_chat_meta(sid, chat_id, {"title": title})
    return jsonify({"status": "success"})


@ai_bp.delete("/chats/<chat_id>")
def api_chat_delete(chat_id):
    sid, item, error = require_session()
    if error:
        return error
    firebase = get_firebase()
    firebase.delete_chat(sid, chat_id)
    return jsonify({"status": "success"})


@ai_bp.post("/vision")
def api_vision():
    sid, item, error = require_session()
    if error:
        return error

    # multipart/form-data
    if "image" not in request.files:
        return jsonify({"status": "error", "message": "image required"}), 400

    file = request.files["image"]
    if not file or not file.filename:
        return jsonify({"status": "error", "message": "empty image"}), 400

    allowed_mimes = {"image/jpeg", "image/png", "image/webp"}
    if file.mimetype not in allowed_mimes:
        return jsonify({"status": "error", "message": "unsupported format"}), 400

    raw = file.read()
    if len(raw) > 8 * 1024 * 1024:
        return jsonify({"status": "error", "message": "image too large (max 8MB)"}), 400

    import base64
    b64 = base64.b64encode(raw).decode("ascii")
    data_uri = f"data:{file.mimetype};base64,{b64}"

    prompt = request.form.get("prompt", "Что на этом изображении?").strip()
    ai = get_ai()
    result = ai.vision(prompt, data_uri, user_role=item.get("role", "user"))
    return jsonify(result)


@ai_bp.get("/status")
def api_ai_status():
    ai = get_ai()
    return jsonify({
        "status": "success",
        "configured": ai.is_configured() if ai else False,
        "model": ai.text_model if ai and ai.is_configured() else None,
    })

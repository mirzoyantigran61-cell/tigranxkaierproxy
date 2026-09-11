"""
TIGRAN AI V4 — Main Application Entry Point
"""
from __future__ import annotations

import logging
import time

import requests
from flask import Flask, Response, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import socketio
from middleware.maintenance import check_maintenance
from services.auth_guard import authenticate_token, require_session
from services.runtime import (
    APP_START_TIME,
    apply_logging_setting,
    get_ai,
    get_firebase,
    get_sessions,
    init_services,
)


# ============================================================
# APP
# ============================================================
app = Flask(__name__)
app.config["SECRET_KEY"] = Config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH

app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
)

socketio.init_app(app)


# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

log = logging.getLogger("tigran-ai")


# ============================================================
# SERVICES
# ============================================================
init_services()

try:
    apply_logging_setting()
except Exception:
    log.exception("Failed to apply runtime logging setting")


# ============================================================
# REQUEST MIDDLEWARE
# ============================================================
@app.before_request
def before_request():
    request._started_at = time.perf_counter()

    maintenance_response = check_maintenance()
    if maintenance_response is not None:
        return maintenance_response

    return None


@app.after_request
def after_request(response):
    started_at = getattr(request, "_started_at", None)

    if started_at is not None:
        elapsed_ms = (time.perf_counter() - started_at) * 1000

        log.info(
            "%s %s -> %s %.1fms",
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
        )

    response.headers["Cache-Control"] = "no-store"

    return response


# ============================================================
# FIREBASE AUTH REVERSE PROXY
# ============================================================
_FIREBASE_AUTH_HOST = "yourtigranmods-papaji-devffsrc.firebaseapp.com"


@app.route(
    "/__/auth/<path:path>",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
def firebase_auth_proxy(path: str):
    target = f"https://{_FIREBASE_AUTH_HOST}/__/auth/{path}"

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {
            "host",
            "content-length",
            "connection",
        }
    }

    try:
        upstream = requests.request(
            method=request.method,
            url=target,
            params=request.args,
            data=request.get_data(),
            headers=headers,
            allow_redirects=False,
            timeout=20,
        )
    except requests.RequestException:
        log.exception("Firebase auth proxy failed")
        return jsonify({"error": "firebase_auth_proxy_failed"}), 502

    excluded_headers = {
        "content-encoding",
        "transfer-encoding",
        "connection",
        "content-length",
    }

    response_headers = [
        (key, value)
        for key, value in upstream.headers.items()
        if key.lower() not in excluded_headers
    ]

    return Response(
        upstream.content,
        status=upstream.status_code,
        headers=response_headers,
    )


# ============================================================
# BLUEPRINTS
# ============================================================
from routes.auth import auth_bp
from routes.ai import ai_bp
from routes.images import images_bp
from routes.payments import payments_bp
from routes.admin import admin_bp
from routes.dashboard import dashboard_bp
from routes.server_controls import server_controls_bp
from routes.settings import settings_bp
from routes.config import config_bp
from proxy import proxy_bp


app.register_blueprint(auth_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(images_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(server_controls_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(config_bp)
app.register_blueprint(proxy_bp)


# ============================================================
# FRONTEND
# ============================================================
@app.route("/")
@app.route("/panel")
@app.route("/dashboard")
def index():
    return render_template("index.html")


@app.route("/verify")
def verify_page():
    return render_template("index.html")


# ============================================================
# PUBLIC HEALTH
# ============================================================
@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "version": Config.APP_VERSION,
            "time": int(time.time()),
            "uptime": int(time.time() - APP_START_TIME),
        }
    )


@app.route("/api/ping")
def ping():
    return jsonify(
        {
            "ok": True,
            "time": int(time.time()),
        }
    )


# ============================================================
# AUTHENTICATED SYSTEM HEALTH
# ============================================================
@app.route("/api/system/health")
@require_session
def system_health(sid, item):
    firebase = get_firebase()
    sessions = get_sessions()
    ai = get_ai()

    firebase_ok = False
    ai_ok = False

    try:
        firebase_ok = bool(firebase and firebase.enabled)
    except Exception:
        firebase_ok = False

    try:
        ai_ok = bool(ai and ai.is_configured())
    except Exception:
        ai_ok = False

    active_sessions = 0

    try:
        if sessions:
            active_sessions = sessions.count()
    except Exception:
        active_sessions = 0

    return jsonify(
        {
            "server": True,
            "firebase": firebase_ok,
            "ai": ai_ok,
            "sessions": active_sessions,
            "version": Config.APP_VERSION,
            "uptime": int(time.time() - APP_START_TIME),
        }
    )


# ============================================================
# SOCKET.IO AUTH
# ============================================================
@socketio.on("connect")
def ws_connect(auth):
    if not isinstance(auth, dict):
        return False

    token = str(
        auth.get("token")
        or auth.get("id_token")
        or ""
    ).strip()

    if not token:
        return False

    item = authenticate_token(token)

    if not item:
        return False

    return True


# ============================================================
# STARTUP
# ============================================================
if __name__ == "__main__":
    print()
    print("=" * 60)
    print(f"  TIGRAN AI V{Config.APP_VERSION}")
    print("=" * 60)
    print(f"  Panel:    http://127.0.0.1:{Config.PORT}/panel")
    print(f"  Health:   http://127.0.0.1:{Config.PORT}/health")
    print(f"  AI Model: {Config.OPENAI_TEXT_MODEL}")
    print(f"  Image:    {Config.OPENAI_IMAGE_MODEL}")
    print("=" * 60)
    print()

    socketio.run(
        app,
        host="0.0.0.0",
        port=Config.PORT,
        debug=False,
    )

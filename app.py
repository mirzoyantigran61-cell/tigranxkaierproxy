"""
TIGRAN AI V3 — Main Application Entry Point
"""
from __future__ import annotations

import logging
import time

from flask import Flask, jsonify, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import socketio
from services.runtime import init_services, APP_START_TIME
from services.auth_guard import require_session


# ============================================================
#  APP FACTORY
# ============================================================
app = Flask(__name__)
app.config["SECRET_KEY"] = Config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

socketio.init_app(app)

# ============================================================
#  LOGGING
# ============================================================
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("tigran-ai")

# ============================================================
#  SERVICES INIT (до регистрации blueprint'ов)
# ============================================================
init_services()

# ============================================================
#  BLUEPRINTS
# ============================================================
from routes.auth import auth_bp
from routes.ai import ai_bp
from routes.images import images_bp
from routes.payments import payments_bp
from routes.admin import admin_bp
from proxy import proxy_bp

app.register_blueprint(auth_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(images_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(proxy_bp)


# ============================================================
#  FRONTEND ROUTES
# ============================================================
@app.route("/")
@app.route("/panel")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": Config.APP_VERSION, "time": int(time.time())})


@app.route("/verify")
def verify_page():
    return render_template("index.html")


# ============================================================
#  WEBSOCKET
# ============================================================
@socketio.on("connect")
def ws_connect(auth):
    from services.runtime import get_sessions
    sid = ""
    if isinstance(auth, dict):
        sid = str(auth.get("session_id", "")).strip()
    sessions = get_sessions()
    item = sessions.get(sid) if sessions else None
    if not item:
        return False
    return True


# ============================================================
#  STARTUP
# ============================================================
if __name__ == "__main__":
    print()
    print("=" * 60)
    print(f"  TIGRAN AI V{Config.APP_VERSION}")
    print("=" * 60)
    print(f"  Panel:    http://127.0.0.1:{Config.PORT}/panel")
    print(f"  Health:   http://127.0.0.1:{Config.PORT}/health")
    print(f"  Upstream: {Config.UPSTREAM_BASE_URL}")
    print(f"  AI Model: {Config.OPENAI_TEXT_MODEL}")
    print(f"  Image:    {Config.OPENAI_IMAGE_MODEL}")
    print("=" * 60)
    print()
    socketio.run(app, host="0.0.0.0", port=Config.PORT, debug=False)

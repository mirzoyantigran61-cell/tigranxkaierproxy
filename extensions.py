from __future__ import annotations
from flask_socketio import SocketIO

socketio = SocketIO(
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

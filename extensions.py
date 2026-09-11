"""
Shared extensions — avoids circular imports.
"""
from __future__ import annotations

from flask_socketio import SocketIO

socketio = SocketIO(
    cors_allowed_origins=[],
    async_mode="eventlet",
    logger=False,
    engineio_logger=False,
)

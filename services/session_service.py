"""
Session Service — Redis-backed with in-memory fallback.
"""
from __future__ import annotations

import json
import logging
import secrets
import time
from typing import Optional, Dict

from config import Config

log = logging.getLogger("session-service")


class SessionService:
    def __init__(self):
        self.redis = None
        self._memory: Dict[str, dict] = {}
        self._use_redis = False

        if Config.REDIS_URL:
            try:
                import redis
                self.redis = redis.from_url(Config.REDIS_URL, decode_responses=True)
                self.redis.ping()
                self._use_redis = True
                log.info("Session store: Redis")
            except Exception as exc:
                log.warning("Redis unavailable, falling back to memory: %s", exc)
        else:
            log.info("Session store: in-memory (set REDIS_URL for production)")

    def create(self, login: str, role: str) -> str:
        sid = secrets.token_urlsafe(32)
        data = {
            "login": login,
            "role": role,
            "created_at": int(time.time()),
        }
        if self._use_redis:
            self.redis.setex(f"sess:{sid}", Config.SESSION_TTL, json.dumps(data))
        else:
            self._memory[sid] = data
        return sid

    def get(self, sid: str) -> Optional[dict]:
        if not sid:
            return None
        if self._use_redis:
            raw = self.redis.get(f"sess:{sid}")
            return json.loads(raw) if raw else None
        else:
            item = self._memory.get(sid)
            if not item:
                return None
            if item["created_at"] + Config.SESSION_TTL < time.time():
                del self._memory[sid]
                return None
            return item

    def delete(self, sid: str) -> bool:
        if self._use_redis:
            return bool(self.redis.delete(f"sess:{sid}"))
        return bool(self._memory.pop(sid, None))

    def count(self) -> int:
        if self._use_redis:
            return len(self.redis.keys("sess:*"))
        return len(self._memory)

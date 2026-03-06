import json
import logging
import time
from typing import Literal

import redis

from app.config import settings

logger = logging.getLogger(__name__)

Phase = Literal["init", "clone", "commits", "branches", "prs", "stats", "assigning", "complete", "error", "cancelled"]
Level = Literal["info", "warning", "error"]

LOG_TTL_SECONDS = 3600


class SyncLogger:
    """Structured logger for sync jobs — writes to Python logger and Redis."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.list_key = f"sync:logs:{job_id}"
        self.channel_key = f"sync:logs:live:{job_id}"
        self._redis: redis.Redis | None = None
        try:
            self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            logger.debug("SyncLogger could not connect to Redis", exc_info=True)

    def _emit(self, phase: str, level: str, message: str):
        entry = json.dumps({
            "ts": time.time(),
            "phase": phase,
            "level": level,
            "message": message,
        })

        py_level = getattr(logging, level.upper(), logging.INFO)
        logger.log(py_level, "[sync:%s][%s] %s", self.job_id[:8], phase, message)

        if not self._redis:
            return
        try:
            pipe = self._redis.pipeline()
            pipe.rpush(self.list_key, entry)
            pipe.expire(self.list_key, LOG_TTL_SECONDS)
            pipe.publish(self.channel_key, entry)
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish sync log to Redis", exc_info=True)

    def info(self, phase: str, message: str):
        self._emit(phase, "info", message)

    def warning(self, phase: str, message: str):
        self._emit(phase, "warning", message)

    def error(self, phase: str, message: str):
        self._emit(phase, "error", message)

    def complete(self):
        self._emit("complete", "info", "Sync completed successfully")
        self._finalize()

    def fail(self, error: str):
        self._emit("error", "error", f"Sync failed: {error}")
        self._finalize()

    def cancel(self):
        self._emit("cancelled", "info", "Sync cancelled by user")
        self._finalize()

    def _finalize(self):
        sentinel = json.dumps({"ts": time.time(), "phase": "__done__", "level": "info", "message": ""})
        if not self._redis:
            return
        try:
            pipe = self._redis.pipeline()
            pipe.rpush(self.list_key, sentinel)
            pipe.expire(self.list_key, LOG_TTL_SECONDS)
            pipe.publish(self.channel_key, sentinel)
            pipe.execute()
        except Exception:
            pass

    def close(self):
        if self._redis:
            try:
                self._redis.close()
            except Exception:
                pass

import json
import logging
import time
from typing import AsyncGenerator, Literal

import redis
import redis.asyncio as aioredis
from starlette.requests import Request

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


async def stream_log_events(
    list_key: str,
    channel_key: str,
    request: Request,
) -> AsyncGenerator[dict[str, str], None]:
    """Yield SSE dicts from a Redis list + pub/sub channel without race gaps.

    Subscribe to the pub/sub channel *before* reading the list so that any
    messages published between the list read and the pub/sub poll are captured
    by the subscription buffer instead of being silently lost.
    """
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        pubsub = r.pubsub()
        await pubsub.subscribe(channel_key)

        existing = await r.lrange(list_key, 0, -1)
        sent = len(existing)
        for entry in existing:
            data = json.loads(entry)
            if data.get("phase") == "__done__":
                yield {"event": "done", "data": entry}
                return
            yield {"event": "log", "data": entry}

        try:
            while True:
                if await request.is_disconnected():
                    break

                new_entries = await r.lrange(list_key, sent, -1)
                if new_entries:
                    sent += len(new_entries)
                    for entry in new_entries:
                        data = json.loads(entry)
                        if data.get("phase") == "__done__":
                            yield {"event": "done", "data": entry}
                            return
                        yield {"event": "log", "data": entry}
                    continue

                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0,
                )
                if msg is None:
                    continue
                # Don't yield pub/sub messages directly — they also exist in the
                # list and would be sent twice.  Just loop back so the list poll
                # picks them up with proper `sent` tracking.
        finally:
            await pubsub.unsubscribe(channel_key)
            await pubsub.aclose()
    finally:
        await r.aclose()

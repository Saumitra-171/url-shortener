import json
import logging
import threading
from collections import Counter
from datetime import datetime, timezone

import redis
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.cache import redis_client
from app.models.click import Click
from app.models.url import URL

logger = logging.getLogger(__name__)

QUEUE_KEY = "clicks:queue"
DEAD_KEY = "clicks:dead"
MAX_QUEUE = 10_000  # backpressure: if the worker falls far behind, the oldest events are dropped


def _clip(value: str | None, limit: int) -> str | None:
    # The clicks columns are VARCHAR(512)/VARCHAR(45). Postgres rejects longer values, and one
    # oversized user agent would make a whole batch fail.
    return value[:limit] if value else None


# ---------- producer (runs in the request path, must be fast) ----------

def enqueue_click(url_id: int, referrer: str | None, user_agent: str | None, ip_address: str | None) -> bool:
    """Queue one click. Returns False if Redis is unavailable, so the caller can fall back."""
    event = json.dumps({
        "url_id": url_id,
        # Record WHEN the click happened. If we let the database stamp it, a delayed
        # worker would store the processing time instead.
        "ts": datetime.now(timezone.utc).isoformat(),
        "referrer": _clip(referrer, 512),
        "user_agent": _clip(user_agent, 512),
        "ip": _clip(ip_address, 45),
    })
    try:
        pipe = redis_client.pipeline(transaction=False)
        pipe.lpush(QUEUE_KEY, event)                # newest at the head
        pipe.ltrim(QUEUE_KEY, 0, MAX_QUEUE - 1)     # keep the newest MAX_QUEUE, drop the oldest
        pipe.execute()                              # one network round trip
        return True
    except redis.RedisError:
        logger.warning("Redis unavailable, click for url %s will be written directly", url_id)
        return False


# ---------- consumer ----------

def _parse(raw: str) -> dict | None:
    try:
        event = json.loads(raw)
        int(event["url_id"])
        datetime.fromisoformat(event["ts"])
        return event
    except (ValueError, KeyError, TypeError):
        return None  # malformed: caller sends it to the dead-letter queue


def _write_batch(db: Session, events: list[dict]) -> int:
    """Write a batch in ONE transaction. Returns how many clicks were stored."""
    # A link may have been deleted while its clicks sat in the queue. Inserting those would
    # violate the foreign key and fail the whole batch, so skip them.
    ids = {e["url_id"] for e in events}
    existing = set(db.scalars(select(URL.id).where(URL.id.in_(ids))))
    parsed = [(e, datetime.fromisoformat(e["ts"])) for e in events if e["url_id"] in existing]
    if not parsed:
        return 0

    db.add_all([
        Click(
            url_id=e["url_id"],
            clicked_at=ts,
            referrer=e.get("referrer"),
            user_agent=e.get("user_agent"),
            ip_address=e.get("ip"),
        )
        for e, ts in parsed
    ])

    # Aggregate first: 50 clicks on one link become ONE counter update, not 50.
    counts = Counter(e["url_id"] for e, _ in parsed)
    latest: dict[int, datetime] = {}
    for e, ts in parsed:
        if e["url_id"] not in latest or ts > latest[e["url_id"]]:
            latest[e["url_id"]] = ts
    for url_id, n in counts.items():
        db.execute(
            update(URL)
            .where(URL.id == url_id)
            .values(click_count=URL.click_count + n, last_clicked_at=latest[url_id])
        )
    db.commit()
    return len(parsed)


class ClickWorker:
    def __init__(self, session_factory, batch_size=100, min_poll=0.5, max_poll=10.0,
                 max_retries=5, backoff_base=0.5):
        self.session_factory = session_factory
        self.batch_size = batch_size
        self.min_poll = min_poll          # polling interval while there is work
        self.max_poll = max_poll          # polling interval when idle (the cap)
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # --- lifecycle ---

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="click-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    def _run(self) -> None:
        delay = self.min_poll
        while not self._stop.is_set():
            try:
                handled = self.run_once()
            except Exception:
                logger.exception("click worker iteration failed")
                handled = 0
            if handled >= self.batch_size:
                continue  # a full batch means there is probably more waiting: don't sleep
            # Adaptive polling: fast while busy, backing off to max_poll when idle. Every poll
            # is a command against your Redis plan, so idle polling should be cheap.
            delay = self.min_poll if handled else min(delay * 2, self.max_poll)
            self._stop.wait(delay)
        try:
            self.drain()  # flush what is left before the process exits
        except Exception:
            logger.exception("click worker could not drain on shutdown")

    # --- one unit of work ---

    def run_once(self) -> int:
        """Process at most one batch. Returns how many queue items were handled."""
        raw_items = self._pop_batch()
        if not raw_items:
            return 0
        good: list[tuple[str, dict]] = []
        bad: list[str] = []
        for raw in raw_items:
            event = _parse(raw)
            if event is None:
                bad.append(raw)
            else:
                good.append((raw, event))
        self._dead_letter(bad)
        if good:
            self._write_with_retry([e for _, e in good], [r for r, _ in good])
        return len(raw_items)

    def drain(self, max_batches: int = 50) -> None:
        for _ in range(max_batches):
            if not self.run_once():
                break

    def _pop_batch(self) -> list[str]:
        try:
            # RPOP with a count takes up to N items atomically from the tail (the oldest).
            # It is non-blocking, so an idle worker costs one cheap command per poll.
            return redis_client.rpop(QUEUE_KEY, self.batch_size) or []
        except redis.RedisError:
            logger.warning("Redis unavailable, click worker is idle")
            return []

    def _write_with_retry(self, events: list[dict], raw_items: list[str]) -> None:
        for attempt in range(1, self.max_retries + 1):
            db = self.session_factory()
            try:
                _write_batch(db, events)
                return
            except Exception:
                db.rollback()
                logger.warning("click batch failed (attempt %d/%d)", attempt, self.max_retries, exc_info=True)
            finally:
                db.close()
            if attempt < self.max_retries:
                # Exponential backoff: 1x, 2x, 4x... capped at 30 seconds. Returns early on shutdown.
                self._stop.wait(min(self.backoff_base * 2**attempt, 30))
        logger.error("click batch failed %d times, moving %d events to dead-letter queue",
                     self.max_retries, len(raw_items))
        self._dead_letter(raw_items)

    def _dead_letter(self, raw_items: list[str]) -> None:
        if not raw_items:
            return
        try:
            redis_client.lpush(DEAD_KEY, *raw_items)
        except redis.RedisError:
            logger.error("could not dead-letter %d click events, they are lost", len(raw_items))
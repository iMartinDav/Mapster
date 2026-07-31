"""Job status tracking, backed by Upstash Redis when configured.

Redis gives job state a TTL (auto-cleanup, no periodic sweep needed) and
makes the concurrency limit cluster-wide via an atomic counter — both
matter once the app runs as more than one process/instance. Falls back
to the original in-memory dict + threading primitives when Upstash
credentials aren't set, so local dev keeps working with zero cloud setup.
"""

import json
import threading
import time
import uuid
from typing import Any, Optional

from mapster.config import get_settings

try:
    from upstash_redis import Redis
except ImportError:
    Redis = None

_JOB_PREFIX = "mapster:job:"
_CONCURRENCY_KEY = "mapster:active_generations"
# Safety-net TTL on the concurrency counter: if a worker process dies mid-job
# (crash, OOM, restart) without reaching its release_slot() finally block, the
# counter would otherwise leak upward forever and permanently block new
# generations. Refreshing this TTL on every acquire means the counter
# self-clears if nothing acquires/releases for this long — generous enough to
# outlast any real generation.
_SLOT_SAFETY_TTL_SECONDS = 25 * 60

_redis_client = None
_redis_checked = False

_mem_jobs: dict[str, dict[str, Any]] = {}
_mem_lock = threading.Lock()
_mem_semaphore: Optional[threading.Semaphore] = None


def _get_redis():
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    settings = get_settings()
    if Redis and settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
        _redis_client = Redis(url=settings.UPSTASH_REDIS_REST_URL, token=settings.UPSTASH_REDIS_REST_TOKEN)
        print("Job store: Upstash Redis")
    else:
        print("Job store: in-memory (set UPSTASH_REDIS_REST_URL/TOKEN to use Redis)")
    return _redis_client


def _get_mem_semaphore() -> threading.Semaphore:
    global _mem_semaphore
    if _mem_semaphore is None:
        settings = get_settings()
        _mem_semaphore = threading.Semaphore(settings.MAX_CONCURRENT_GENERATIONS)
    return _mem_semaphore


def acquire_slot() -> bool:
    """Claim a concurrent-generation slot. Returns False if the server is at capacity."""
    r = _get_redis()
    if r is None:
        return _get_mem_semaphore().acquire(timeout=0)

    settings = get_settings()
    try:
        current = r.incr(_CONCURRENCY_KEY)
        r.expire(_CONCURRENCY_KEY, _SLOT_SAFETY_TTL_SECONDS)
        if current > settings.MAX_CONCURRENT_GENERATIONS:
            r.decr(_CONCURRENCY_KEY)
            return False
        return True
    except Exception as e:
        print(f"Upstash concurrency check failed, allowing request: {e}")
        return True


def release_slot() -> None:
    r = _get_redis()
    if r is None:
        _get_mem_semaphore().release()
        return
    try:
        r.decr(_CONCURRENCY_KEY)
    except Exception as e:
        print(f"Upstash slot release failed: {e}")


def _store_job(job_id: str, job: dict) -> None:
    r = _get_redis()
    settings = get_settings()
    if r is not None:
        try:
            r.set(_JOB_PREFIX + job_id, json.dumps(job), ex=settings.JOB_TTL_SECONDS)
            return
        except Exception as e:
            print(f"Upstash job write failed, falling back to memory: {e}")
            try:
                # Remove any stale (smaller/older) value so get_job() doesn't
                # keep serving it instead of falling through to memory below.
                r.delete(_JOB_PREFIX + job_id)
            except Exception:
                pass
    with _mem_lock:
        _mem_jobs[job_id] = job


def create_job(job_type: str, initial_message: str = "Initializing...") -> str:
    job_id = str(uuid.uuid4())
    job = {
        "status": "running",
        "progress": 0,
        "message": initial_message,
        "type": job_type,
        "created_at": time.time(),
    }
    _store_job(job_id, job)
    cleanup()
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    """Read a job, preferring Redis but always falling back to the memory store.

    A job can end up memory-only even when Redis is configured (e.g. a
    result payload too large for Upstash's request-size limit), so a Redis
    miss/error must fall through instead of returning None outright.
    """
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(_JOB_PREFIX + job_id)
            if raw:
                return json.loads(raw)
        except Exception as e:
            print(f"Upstash job read failed: {e}")
    return _mem_jobs.get(job_id)


def update_job(job_id: str, message: str, percent: float, partial_data: Any = None) -> None:
    job = get_job(job_id)
    if job is None:
        return
    job["progress"] = percent
    job["message"] = message
    if partial_data is not None:
        job["partial_data"] = partial_data
    _store_job(job_id, job)


def complete_job(job_id: str, result: dict) -> None:
    job = get_job(job_id)
    if job is None:
        return
    job["status"] = "completed"
    job["result"] = result
    job["progress"] = 100
    _store_job(job_id, job)


def fail_job(job_id: str, error: str) -> None:
    job = get_job(job_id)
    if job is None:
        return
    job["status"] = "failed"
    job["error"] = error
    _store_job(job_id, job)


def cleanup() -> None:
    """Remove completed/failed jobs older than JOB_TTL_SECONDS from the in-memory store.

    Redis-backed jobs expire on their own via TTL and don't need this.
    """
    settings = get_settings()
    now = time.time()
    with _mem_lock:
        to_delete = [
            jid for jid, job in _mem_jobs.items()
            if job["status"] in ("completed", "failed")
            and now - job.get("created_at", 0) > settings.JOB_TTL_SECONDS
        ]
        for jid in to_delete:
            del _mem_jobs[jid]


def _periodic_cleanup():
    while True:
        time.sleep(5 * 60)
        try:
            cleanup()
        except Exception as e:
            print(f"Periodic cleanup failed: {e}")


def start_cleanup_thread():
    t = threading.Thread(target=_periodic_cleanup, daemon=True)
    t.start()

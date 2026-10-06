"""
Background jobs for slow work (embedding a large PDF or transcribing a long
recording), so the browser can show progress instead of waiting on one
long request.

    POST /personas/{id}/documents/async   same body as /documents -> {job_id}
    GET  /jobs/{job_id}                   {status, progress, message, result | error}

Jobs live in memory for an hour after they finish; a restart forgets them
(the upload itself, once done, is saved like any other).
"""

from __future__ import annotations

import secrets
import threading
import time
from typing import Callable

from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam

from services import personas as ps

KEEP_SECONDS = 3600
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _prune() -> None:
    cutoff = time.time() - KEEP_SECONDS
    for job_id in [j for j, job in _jobs.items() if job.get("finished_at", time.time()) < cutoff]:
        del _jobs[job_id]


def start(work: Callable[[Callable[[float, str], None]], dict], kind: str) -> str:
    """Run work(progress) in a thread; returns the job id."""
    job_id = secrets.token_hex(8)
    job = {"id": job_id, "kind": kind, "status": "running", "progress": 0.0, "message": "Starting",
           "user": ps.current_user.get(), "started_at": time.time()}
    with _lock:
        _prune()
        _jobs[job_id] = job

    def progress(fraction: float, message: str) -> None:
        job.update(progress=round(max(job["progress"], min(1.0, fraction)), 3), message=message)

    def run(context_user):
        token = ps.current_user.set(context_user)
        try:
            job["result"] = work(progress)
            job.update(status="done", progress=1.0, message="Done")
        except ValueError as e:
            job.update(status="failed", error=str(e))
        except Exception as e:  # never leave a job "running" forever
            job.update(status="failed", error=f"Unexpected error ({type(e).__name__})")
        finally:
            job["finished_at"] = time.time()
            ps.current_user.reset(token)

    threading.Thread(target=run, args=(job["user"],), daemon=True).start()
    return job_id


def get(job_id: str) -> dict | None:
    job = _jobs.get(job_id)
    if job is None:
        return None
    user = ps.current_user.get()
    if user is not None and job["user"] not in (None, user):
        return None
    return {k: v for k, v in job.items() if k != "user"}


def make_router() -> APIRouter:
    router = APIRouter(tags=["jobs"])

    @router.get("/jobs/{job_id}")
    def job_status(job_id: str = PathParam(pattern=r"^[0-9a-f]{16}$")):
        job = get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="No such job (finished jobs are kept for an hour)")
        return job

    return router

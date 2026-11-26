"""Tiny in-process job runner with progress reporting for the UI."""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .presenton import PresentonError
from .pptx_tools import DeckError
from .tts import TTSError
from .video import VideoError

USER_ERRORS = (DeckError, TTSError, PresentonError, VideoError)


class Job:
    def __init__(self, kind: str):
        self.id = uuid.uuid4().hex
        self.kind = kind
        self.status = "queued"  # queued | running | done | error
        self.progress = 0.0
        self.step = "Waiting to start…"
        self.error: str | None = None
        self.result: dict[str, Any] = {}
        self.created = time.time()
        self._lock = threading.Lock()

    def update(self, step: str | None = None, progress: float | None = None) -> None:
        with self._lock:
            if step is not None:
                self.step = step
            if progress is not None:
                self.progress = max(0.0, min(1.0, progress))

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "id": self.id,
                "kind": self.kind,
                "status": self.status,
                "progress": round(self.progress, 3),
                "step": self.step,
                "error": self.error,
                "result": self.result,
            }


class JobManager:
    def __init__(self, workers: int = 2, keep: int = 100):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="job")
        self._jobs: dict[str, Job] = {}
        self._keep = keep
        self._lock = threading.Lock()

    def submit(self, kind: str, fn: Callable[[Job], dict | None]) -> Job:
        job = Job(kind)
        with self._lock:
            self._jobs[job.id] = job
            if len(self._jobs) > self._keep:
                for old in sorted(self._jobs.values(), key=lambda j: j.created)[: len(self._jobs) - self._keep]:
                    if old.status in ("done", "error"):
                        self._jobs.pop(old.id, None)

        def run() -> None:
            job.status = "running"
            try:
                result = fn(job)
                job.result = result or {}
                job.progress = 1.0
                job.step = "Done"
                job.status = "done"
            except USER_ERRORS as exc:
                job.error = str(exc)
                job.status = "error"
            except Exception as exc:  # unexpected: keep the details in the container log
                traceback.print_exc()
                job.error = f"Unexpected error: {exc}"
                job.status = "error"

        self._pool.submit(run)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)


manager = JobManager()

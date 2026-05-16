"""In-memory job tracker for status & logs."""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4


class Job:
    def __init__(self, kind: str, meta: dict[str, Any]) -> None:
        self.id: str = uuid4().hex[:12]
        self.kind = kind
        self.meta = meta
        self.status: str = "running"  # running | completed | failed
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.error: Optional[str] = None
        self.logs: deque[str] = deque(maxlen=2000)
        self.result: Any = None

    def log(self, msg: str) -> None:
        self.logs.append(f"{datetime.utcnow().isoformat()} | {msg}")
        self.updated_at = datetime.utcnow()

    def complete(self, result: Any = None) -> None:
        self.status = "completed"
        self.result = result
        self.updated_at = datetime.utcnow()

    def fail(self, err: str) -> None:
        self.status = "failed"
        self.error = err
        self.updated_at = datetime.utcnow()

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error": self.error,
            "meta": self.meta,
        }


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create(self, kind: str, meta: dict[str, Any]) -> Job:
        async with self._lock:
            job = Job(kind=kind, meta=meta)
            self._jobs[job.id] = job
            return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def all(self) -> list[Job]:
        return list(self._jobs.values())

    def counts(self) -> dict[str, int]:
        c = {"running": 0, "completed": 0, "failed": 0}
        for j in self._jobs.values():
            c[j.status] = c.get(j.status, 0) + 1
        return c


registry = JobRegistry()

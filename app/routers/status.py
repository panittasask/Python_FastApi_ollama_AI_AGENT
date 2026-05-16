"""Status, logs, plans, and websocket endpoints."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.models.schemas import StatusResponse
from app.services.job_registry import registry

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    counts = registry.counts()
    return StatusResponse(
        running_jobs=counts.get("running", 0),
        completed_jobs=counts.get("completed", 0),
        failed_jobs=counts.get("failed", 0),
        details=[j.summary() for j in registry.all()[-30:]],
    )


@router.get("/status/{job_id}")
async def job_detail(job_id: str):
    job = registry.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return {**job.summary(), "result": job.result, "logs": list(job.logs)[-200:]}


@router.get("/logs/{job_id}")
async def job_logs(job_id: str):
    job = registry.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return {"job_id": job_id, "logs": list(job.logs)}


@router.get("/plans")
async def list_plans():
    out_dir = get_settings().output_dir
    if not out_dir.exists():
        return {"plans": []}
    plans = []
    for d in out_dir.iterdir():
        if d.is_dir() and (d / "project_plan.md").exists():
            plans.append({"project": d.name, "path": str(d / "project_plan.md")})
    return {"plans": plans}


@router.get("/plans/{project}")
async def get_plan(project: str):
    p = get_settings().output_dir / project / "project_plan.md"
    if not p.exists():
        raise HTTPException(404, "plan not found")
    return {"project": project, "markdown": p.read_text(encoding="utf-8")}


@router.websocket("/ws/logs/{job_id}")
async def ws_logs(ws: WebSocket, job_id: str):
    await ws.accept()
    job = registry.get(job_id)
    if not job:
        await ws.send_json({"error": "job not found"})
        await ws.close()
        return
    last = 0
    try:
        while True:
            logs = list(job.logs)
            if len(logs) > last:
                for line in logs[last:]:
                    await ws.send_text(line)
                last = len(logs)
            if job.status != "running":
                await ws.send_json({"status": job.status, "error": job.error})
                break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
    finally:
        try:
            await ws.close()
        except RuntimeError:
            pass


@router.get("/healthz")
async def healthz():
    return {"ok": True}

"""Test & Fix endpoints."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.logging_config import logger
from app.models.schemas import FixRequest, TestRequest, TestResult
from app.services.job_registry import registry
from app.services.orchestrator import Orchestrator
from app.services.test_runner import TestRunner

router = APIRouter(tags=["test-fix"])


@router.post("/test", response_model=TestResult)
async def run_tests(req: TestRequest) -> TestResult:
    p = Path(req.project_path)
    if not p.exists():
        raise HTTPException(404, f"project not found: {req.project_path}")
    runner = TestRunner(p)
    try:
        return await runner.run(command=req.command)
    except Exception as e:
        logger.exception("test run failed")
        raise HTTPException(500, str(e)) from e


@router.post("/fix")
async def fix(req: FixRequest):
    p = Path(req.project_path)
    if not p.exists():
        raise HTTPException(404, f"project not found: {req.project_path}")
    job = await registry.create("fix", {"project_path": req.project_path})
    orch = Orchestrator(req.config)
    try:
        written = await orch.fix_project(
            project_path=req.project_path,
            error_log=req.error_log,
            file_path=req.file_path,
            job=job,
        )
        job.complete({"files": written})
        return {"job_id": job.id, "files": written}
    except Exception as e:
        logger.exception("fix failed")
        job.fail(str(e))
        raise HTTPException(500, str(e)) from e

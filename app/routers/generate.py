"""Code/project generation endpoints."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.core.logging_config import logger
from app.models.schemas import (
    GenerateProjectRequest,
    GenerateRequest,
    GenerateResponse,
)
from app.services.job_registry import registry
from app.services.ollama_client import OllamaClient
from app.services.orchestrator import Orchestrator

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    """Refine + generate code for a small request (synchronous)."""
    orch = Orchestrator(req.config)
    job = await registry.create("generate", {"prompt": req.prompt[:200]})
    try:
        result = await orch.generate_simple(
            prompt=req.prompt,
            output_path=req.output_path,
            project_name=req.project_name,
            job=job,
        )
        job.complete(result.model_dump())
        return result
    except Exception as e:
        logger.exception("generate failed")
        job.fail(str(e))
        raise HTTPException(500, str(e)) from e


@router.post("/stream")
async def generate_stream(req: GenerateRequest):
    """Stream raw refiner tokens (handy for UIs). Files are NOT written here."""
    orch = Orchestrator(req.config)

    async def gen():
        try:
            async with OllamaClient() as client:
                from app.agents.refiner import PromptRefinerAgent

                refiner = PromptRefinerAgent(client, req.config)
                async for chunk in client.stream_generate(
                    model=refiner.params.model,
                    prompt=req.prompt,
                    system=refiner.system_prompt,
                    temperature=refiner.params.temperature,
                    top_p=refiner.params.top_p,
                    num_ctx=refiner.params.num_ctx,
                    num_predict=refiner.params.num_predict,
                ):
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:  # pragma: no cover
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    _ = orch  # quiet linters
    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/project")
async def generate_project(req: GenerateProjectRequest, background: BackgroundTasks):
    """Kick off a full project build. Runs asynchronously; returns a job id."""
    job = await registry.create(
        "project",
        {"prompt": req.prompt[:200], "project_name": req.project_name},
    )
    orch = Orchestrator(req.config)

    async def runner():
        try:
            result = await orch.generate_project(
                prompt=req.prompt,
                project_name=req.project_name,
                output_path=req.output_path,
                auto_test=req.auto_test,
                max_loops=req.max_loops,
                job=job,
            )
            job.complete(result.model_dump())
        except Exception as e:
            logger.exception("project generation failed")
            job.fail(str(e))

    # Run in the event loop without blocking the response.
    asyncio.create_task(runner())
    _ = background  # reserved for future task hooks
    return {"job_id": job.id, "status": job.status}

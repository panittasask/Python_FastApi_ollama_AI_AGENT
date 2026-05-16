"""Existing-project analysis endpoints.

POST /analyze          → SSE stream: scan → analyze → persist memory
POST /analyze/sync     → blocking JSON variant (handy for tests)
GET  /analyze/memory   → read previously saved memory for a path
POST /analyze/ask      → grounded Q&A about an analyzed project
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.analyzer import AnalyzerAgent
from app.core.exceptions import OllamaError
from app.core.logging_config import logger
from app.models.schemas import ModelConfig
from app.services.ollama_client import OllamaClient
from app.services.project_memory import ProjectMemory
from app.services.project_scanner import scan_project


router = APIRouter(prefix="/analyze", tags=["analyze"])


# --------------------------------------------------------------------- schemas

class AnalyzeRequest(BaseModel):
    path: str
    model: Optional[str] = None
    include_llm: bool = True  # set False to skip the LLM step (scan only)


class AskRequest(BaseModel):
    path: str
    question: str
    model: Optional[str] = None


# --------------------------------------------------------------------- helpers

def _resolve_root(path_str: str) -> Path:
    if not path_str or not path_str.strip():
        raise HTTPException(400, "path is required")
    p = Path(path_str).expanduser()
    try:
        p = p.resolve()
    except OSError as e:
        raise HTTPException(400, f"invalid path: {e}") from e
    if not p.exists():
        raise HTTPException(404, f"path not found: {p}")
    if not p.is_dir():
        raise HTTPException(400, f"path is not a directory: {p}")
    return p


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _cfg_from(model: Optional[str]) -> Optional[ModelConfig]:
    if not model:
        return None
    return ModelConfig(
        refiner_model=model,
        coder_model=model,
        planner_model=model,
        fix_model=model,
    )


# --------------------------------------------------------------------- endpoints

@router.post("/sync")
async def analyze_sync(req: AnalyzeRequest) -> dict:
    """Blocking analyze for callers that don't want SSE."""
    root = _resolve_root(req.path)
    scan = scan_project(root)
    scan_dict = scan.to_dict()

    analysis: dict = {}
    if req.include_llm:
        try:
            async with OllamaClient() as client:
                agent = AnalyzerAgent(client, _cfg_from(req.model))
                analysis = await agent.analyze(scan_dict)
        except OllamaError as e:
            raise HTTPException(502, f"ollama unreachable: {e}") from e

    mem = ProjectMemory(root)
    payload = mem.save(scan_dict, analysis or {})
    return {
        "ok": True,
        "memory_dir": str(mem.dir),
        "memory": payload,
        "markdown": mem.read_markdown(),
    }


@router.post("")
async def analyze_stream(req: AnalyzeRequest):
    """Stream scan + analysis progress as SSE."""
    root = _resolve_root(req.path)
    model = req.model

    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=500)
    result: dict = {"status": "pending"}

    def emit(msg: str) -> None:
        try:
            queue.put_nowait(msg)
        except asyncio.QueueFull:
            pass

    async def run() -> None:
        try:
            emit(f"scanning `{root}`")
            scan = await asyncio.to_thread(scan_project, root, on_progress=emit)
            scan_dict = scan.to_dict()
            emit(
                f"scan done — {scan_dict['total_files']} files, "
                f"{scan_dict['total_lines']:,} lines"
            )
            fw = scan_dict.get("frameworks") or []
            if fw:
                emit("frameworks: " + ", ".join(fw))

            analysis: dict = {}
            if req.include_llm:
                emit("calling analyzer model — this may take a minute…")
                try:
                    async with OllamaClient() as client:
                        agent = AnalyzerAgent(client, _cfg_from(model))
                        analysis = await agent.analyze(scan_dict)
                except OllamaError as e:
                    emit(f"analyzer model unreachable: {e}")
                    analysis = {
                        "overview": "_(LLM unavailable — scan-only result)_",
                        "risks": [f"ollama error: {e}"],
                    }
                else:
                    emit("analyzer model returned structured analysis")

            emit("writing .agent/ memory files…")
            mem = ProjectMemory(root)
            saved = mem.save(scan_dict, analysis or {})
            emit(f"memory saved to {mem.dir}")
            result["status"] = "ok"
            result["memory_dir"] = str(mem.dir)
            result["memory"] = saved
            result["markdown"] = mem.read_markdown()
        except Exception as e:
            logger.exception("analyze stream failed")
            result["status"] = "error"
            result["error"] = str(e)
            emit(f"ERROR: {e}")
        finally:
            await queue.put("__DONE__")

    async def event_stream():
        yield _sse({"type": "start", "path": str(root)})
        task = asyncio.create_task(run())
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=60.0)
                except asyncio.TimeoutError:
                    yield _sse({"type": "progress", "message": "still working…"})
                    continue
                if msg == "__DONE__":
                    break
                yield _sse({"type": "progress", "message": msg})
            if result.get("status") == "ok":
                yield _sse({
                    "type": "done",
                    "memory_dir": result["memory_dir"],
                    "memory": result["memory"],
                    "markdown": result["markdown"],
                })
            else:
                yield _sse({"type": "error", "message": result.get("error", "failed")})
        except asyncio.CancelledError:
            task.cancel()
            yield _sse({"type": "cancelled"})
            raise
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/memory")
async def get_memory(path: str) -> dict:
    root = _resolve_root(path)
    mem = ProjectMemory(root)
    data = mem.load()
    if not data:
        raise HTTPException(404, "no analysis saved yet for this path")
    return {
        "ok": True,
        "memory_dir": str(mem.dir),
        "memory": data,
        "markdown": mem.read_markdown(),
    }


@router.post("/ask")
async def ask(req: AskRequest) -> dict:
    """Grounded Q&A: stuffs the saved analysis into the model context."""
    root = _resolve_root(req.path)
    mem = ProjectMemory(root)
    data = mem.load()
    if not data:
        raise HTTPException(404, "run /analyze for this path first")

    scan = data.get("scan") or {}
    analysis = data.get("analysis") or {}

    context_parts = [
        f"You are answering questions about the project `{scan.get('name', root.name)}` "
        f"located at `{root}`.",
        "Use ONLY the information below. If unsure, say so.",
        "",
        "## Overview",
        analysis.get("overview", "(none)"),
        "",
        "## Architecture",
        analysis.get("architecture", "(none)"),
        "",
        "## Frameworks",
        ", ".join(scan.get("frameworks") or []) or "(none)",
        "",
        "## Folder tree",
        "```",
        (scan.get("tree") or "")[:6_000],
        "```",
    ]
    todos = analysis.get("todos") or []
    if todos:
        context_parts.append("\n## Suggested todos")
        for t in todos[:20]:
            if isinstance(t, dict):
                context_parts.append(
                    f"- [{t.get('priority','?')}] {t.get('title','')} — {t.get('why','')}"
                )

    system = "\n".join(context_parts)
    user_prompt = req.question.strip() or "Summarize this project."

    try:
        async with OllamaClient() as client:
            from app.core.config import get_settings
            s = get_settings()
            content = await client.chat(
                model=req.model or s.refiner_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=s.temperature,
                top_p=s.top_p,
                num_ctx=s.num_ctx,
                num_predict=s.max_tokens,
            )
    except OllamaError as e:
        raise HTTPException(502, f"ollama unreachable: {e}") from e

    return {"ok": True, "answer": content}

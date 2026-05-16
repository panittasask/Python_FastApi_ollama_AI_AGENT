"""Chat endpoints used by the Angular UI.

- GET  /api/models  -> list Ollama models
- POST /api/chat    -> SSE streaming response. Supports two modes:
    * "chat"  -> plain conversational reply from the chosen model
    * "agent" -> runs the full multi-agent pipeline and WRITES files to disk
    * "auto"  -> auto-detect build intent and pick "agent" or "chat"
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.exceptions import OllamaError
from app.core.logging_config import logger
from app.models.schemas import ModelConfig
from app.services.job_registry import Job
from app.services.ollama_client import OllamaClient
from app.services.orchestrator import Orchestrator
from app.services.web_search import format_results_block, search as web_search_async


router = APIRouter(prefix="/api", tags=["chat"])


# ---------- schemas ----------

class ModelInfo(BaseModel):
    name: str
    size: Optional[int] = None
    family: Optional[str] = None
    modified_at: Optional[str] = None


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class Attachment(BaseModel):
    name: str
    content: str
    mime: Optional[str] = None
    # size in bytes of the original file (informational)
    size: Optional[int] = None


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    conversationId: Optional[str] = Field(default=None, alias="conversation_id")
    history: list[ChatMessage] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    system: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    num_ctx: Optional[int] = None
    max_tokens: Optional[int] = None
    stream: bool = True
    # NEW: agent mode controls
    mode: str = "auto"              # "auto" | "chat" | "agent"
    project_name: Optional[str] = Field(default=None, alias="projectName")
    output_path: Optional[str] = Field(default=None, alias="outputPath")
    auto_test: Optional[bool] = Field(default=None, alias="autoTest")
    max_loops: Optional[int] = Field(default=None, alias="maxLoops")
    force_project: Optional[bool] = Field(default=None, alias="forceProject")
    # NEW: opt-in web search
    web_search: bool = Field(default=False, alias="webSearch")
    web_search_query: Optional[str] = Field(default=None, alias="webSearchQuery")
    # NEW: when true, each agent uses its own configured default model
    # (planner_model, coder_model, fix_model, refiner_model from settings)
    # instead of forcing them all to the user's selected model.
    per_agent_models: bool = Field(default=False, alias="perAgentModels")

    class Config:
        populate_by_name = True


class ChatResponse(BaseModel):
    conversationId: str
    model: str
    content: str


# ---------- endpoints ----------

@router.get("/models", response_model=list[ModelInfo])
async def list_models() -> list[ModelInfo]:
    """List models installed in the Ollama backend."""
    try:
        async with OllamaClient() as client:
            raw = await client.list_models()
    except OllamaError as e:
        logger.warning(f"/api/models failed: {e}")
        raise HTTPException(502, f"ollama unreachable: {e}") from e
    out: list[ModelInfo] = []
    for m in raw:
        details = m.get("details") or {}
        out.append(
            ModelInfo(
                name=m.get("name") or m.get("model") or "",
                size=m.get("size"),
                family=details.get("family"),
                modified_at=m.get("modified_at"),
            )
        )
    return [m for m in out if m.name]


@router.get("/search")
async def search_endpoint(q: str, n: int = 5) -> dict:
    """Run a DuckDuckGo web search and return top-N results."""
    q = (q or "").strip()
    if not q:
        raise HTTPException(400, "query (q) is required")
    n = max(1, min(int(n or 5), 10))
    results = await web_search_async(q, max_results=n)
    return {"query": q, "results": [r.to_dict() for r in results]}


@router.post("/chat")
async def chat(req: ChatRequest):
    """Send a chat message. If stream=True, returns SSE; else JSON."""
    settings = get_settings()
    model = req.model or settings.refiner_model
    conv_id = req.conversationId or uuid4().hex

    # ---------- decide mode ----------
    mode = (req.mode or "auto").lower()
    if mode not in {"auto", "chat", "agent"}:
        mode = "auto"
    if mode == "auto":
        mode = "agent" if _looks_like_build_intent(req.message) else "chat"

    # ---------- AGENT MODE: actually create files ----------
    if mode == "agent":
        return await _agent_stream(req, model, conv_id)

    # ---------- Optional web search grounding ----------
    web_block = ""
    web_results: list[dict] = []
    if req.web_search:
        q = (req.web_search_query or req.message or "").strip()
        try:
            results = await web_search_async(q, max_results=5)
            web_results = [r.to_dict() for r in results]
            web_block = format_results_block(results)
        except Exception as e:  # pragma: no cover
            logger.warning(f"web search failed: {e}")

    # ---------- CHAT MODE: plain conversational reply ----------
    user_content = _build_user_content(req.message, req.attachments)
    if web_block:
        user_content = (
            web_block
            + "\n---\nUse the web results above as up-to-date grounding. "
            + "Cite the source numbers like [1], [2] when relevant.\n\n"
            + user_content
        )
    messages: list[dict[str, str]] = []
    if req.system:
        messages.append({"role": "system", "content": req.system})
    for m in req.history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_content})

    temperature = settings.temperature if req.temperature is None else req.temperature
    top_p = settings.top_p if req.top_p is None else req.top_p
    num_ctx = settings.num_ctx if req.num_ctx is None else req.num_ctx
    num_predict = settings.max_tokens if req.max_tokens is None else req.max_tokens

    if not req.stream:
        try:
            async with OllamaClient() as client:
                content = await client.chat(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    num_ctx=num_ctx,
                    num_predict=num_predict,
                )
        except OllamaError as e:
            raise HTTPException(502, str(e)) from e
        return ChatResponse(conversationId=conv_id, model=model, content=content)

    # Build a prompt from messages for /api/generate streaming (more universally supported)
    def _build_prompt(msgs: list[dict[str, str]]) -> tuple[Optional[str], str]:
        system_msg: Optional[str] = None
        parts: list[str] = []
        for m in msgs:
            role = m["role"]
            text = m["content"]
            if role == "system":
                system_msg = text
            elif role == "user":
                parts.append(f"User: {text}")
            elif role == "assistant":
                parts.append(f"Assistant: {text}")
        parts.append("Assistant:")
        return system_msg, "\n\n".join(parts)

    system_msg, prompt = _build_prompt(messages)

    async def event_stream():
        # initial event with conversation/model metadata
        yield f"data: {json.dumps({'conversation_id': conv_id, 'model': model, 'type': 'start'})}\n\n"
        # surface chat-mode agent activity so the UI can render a badge
        yield f"data: {json.dumps({'type': 'agent', 'name': 'chat', 'model': model, 'status': 'start'})}\n\n"
        if web_results:
            yield f"data: {json.dumps({'type': 'web_search', 'query': (req.web_search_query or req.message), 'results': web_results})}\n\n"
        try:
            async with OllamaClient() as client:
                async for chunk in client.stream_generate(
                    model=model,
                    prompt=prompt,
                    system=system_msg,
                    temperature=temperature,
                    top_p=top_p,
                    num_ctx=num_ctx,
                    num_predict=num_predict,
                ):
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            yield f"data: {json.dumps({'type': 'agent', 'name': 'chat', 'model': model, 'status': 'end'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except asyncio.CancelledError:
            yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
            raise
        except Exception as e:  # pragma: no cover
            logger.exception("chat stream failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# =================================================================
# Agent mode: real multi-agent project/file generation
# =================================================================

# Max combined size of all attachment text we forward to the model.
_MAX_ATTACH_BYTES = 200_000  # ~200 KB total
_MAX_ONE_ATTACH = 80_000     # ~80 KB per file


def _lang_hint(name: str, mime: Optional[str]) -> str:
    n = (name or "").lower()
    ext_map = {
        ".py": "python", ".ts": "ts", ".tsx": "tsx", ".js": "js", ".jsx": "jsx",
        ".json": "json", ".md": "markdown", ".yml": "yaml", ".yaml": "yaml",
        ".html": "html", ".css": "css", ".scss": "scss", ".sh": "bash",
        ".java": "java", ".c": "c", ".cpp": "cpp", ".cs": "csharp",
        ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php",
        ".sql": "sql", ".xml": "xml", ".toml": "toml", ".ini": "ini",
        ".txt": "", ".log": "",
    }
    for ext, lang in ext_map.items():
        if n.endswith(ext):
            return lang
    if mime and "json" in mime:
        return "json"
    if mime and "xml" in mime:
        return "xml"
    return ""


def _build_user_content(message: str, attachments: list[Attachment]) -> str:
    """Prepend file contents (fenced + truncated) to the user message."""
    if not attachments:
        return message
    chunks: list[str] = []
    used = 0
    for a in attachments:
        if not a.content:
            continue
        remaining = _MAX_ATTACH_BYTES - used
        if remaining <= 0:
            chunks.append(f"_…attachment `{a.name}` omitted (size limit reached)._")
            continue
        snippet = a.content
        cap = min(_MAX_ONE_ATTACH, remaining)
        truncated = False
        if len(snippet) > cap:
            snippet = snippet[:cap]
            truncated = True
        used += len(snippet)
        lang = _lang_hint(a.name, a.mime)
        header = f"### Attached file: `{a.name}`"
        if a.size:
            header += f"  _({a.size} bytes)_"
        if truncated:
            header += "  _(truncated)_"
        chunks.append(f"{header}\n```{lang}\n{snippet}\n```")
    if not chunks:
        return message
    preamble = (
        "The user attached the following file(s). Use them as context when answering.\n\n"
        + "\n\n".join(chunks)
        + "\n\n---\n\n"
    )
    return preamble + (message or "(no question — please summarize the attached file(s))")

# Intent keywords — order-insensitive regex
_BUILD_VERBS = r"(create|build|make|generate|scaffold|write|implement|develop|set\s*up|bootstrap)"
_PROJECT_NOUNS = (
    r"(project|app|application|website|webapp|service|api|server|backend|"
    r"frontend|cli|tool|library|package|game|bot|script|module|microservice)"
)
_FILE_NOUNS = r"(file|class|function|component|endpoint|route|handler|test)"

_BUILD_RE = re.compile(rf"\b{_BUILD_VERBS}\b.*\b{_PROJECT_NOUNS}\b", re.IGNORECASE | re.DOTALL)
_FILE_RE = re.compile(rf"\b{_BUILD_VERBS}\b.*\b{_FILE_NOUNS}\b", re.IGNORECASE | re.DOTALL)


def _looks_like_build_intent(text: str) -> bool:
    if not text:
        return False
    return bool(_BUILD_RE.search(text) or _FILE_RE.search(text))


def _looks_like_full_project(text: str) -> bool:
    return bool(_BUILD_RE.search(text or ""))


def _derive_project_name(text: str) -> str:
    """Cheap heuristic — extract a slug-friendly name from the user message."""
    m = re.search(r"\b(?:called|named)\s+['\"]?([a-zA-Z0-9_\- ]{2,40})['\"]?", text)
    if m:
        raw = m.group(1)
    else:
        words = re.findall(r"[A-Za-z][A-Za-z0-9]+", text)[:4]
        raw = "_".join(words) or f"project_{uuid4().hex[:6]}"
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw.strip()).strip("_").lower()
    return slug or f"project_{uuid4().hex[:6]}"


class _StreamingJob(Job):
    """A Job that also pushes log lines into an asyncio.Queue for SSE."""

    def __init__(self, kind: str, meta: dict, queue: "asyncio.Queue") -> None:
        super().__init__(kind, meta)
        self._queue = queue

    def log(self, msg: str) -> None:  # type: ignore[override]
        super().log(msg)
        try:
            self._queue.put_nowait(msg)
        except asyncio.QueueFull:  # pragma: no cover
            pass

    def agent_event(
        self,
        name: str,
        model: str,
        status: str,
        message: str = "",
    ) -> None:
        """Push a structured 'agent activity' event onto the SSE queue."""
        super().log(f"[agent:{name} model:{model}] {status} {message}".strip())
        try:
            self._queue.put_nowait({
                "_evt": "agent",
                "name": name,
                "model": model,
                "status": status,
                "message": message,
            })
        except asyncio.QueueFull:  # pragma: no cover
            pass


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _agent_stream(req: ChatRequest, model: str, conv_id: str) -> StreamingResponse:
    """Run the orchestrator and stream real progress as SSE chunks."""
    full_project = bool(req.force_project) or _looks_like_full_project(req.message)
    project_name = req.project_name or _derive_project_name(req.message)
    # Fold any attached files into the user prompt so the agents see them.
    effective_prompt = _build_user_content(req.message, req.attachments)

    # Optional web search grounding for agent mode.
    web_results: list[dict] = []
    if req.web_search:
        q = (req.web_search_query or req.message or "").strip()
        try:
            results = await web_search_async(q, max_results=5)
            web_results = [r.to_dict() for r in results]
            block = format_results_block(results)
            if block:
                effective_prompt = (
                    block
                    + "\n---\nUse the web results above as up-to-date grounding.\n\n"
                    + effective_prompt
                )
        except Exception as e:  # pragma: no cover
            logger.warning(f"web search failed: {e}")

    # Build a ModelConfig. By default every agent uses the user-selected model
    # so the bubble shows a single consistent model. If `per_agent_models` is
    # set, leave per-role fields blank so each agent picks its configured
    # default (planner_model, coder_model, fix_model, refiner_model).
    per_agent = bool(getattr(req, "per_agent_models", False))
    cfg = ModelConfig(
        refiner_model=None if per_agent else model,
        coder_model=None if per_agent else model,
        planner_model=None if per_agent else model,
        fix_model=None if per_agent else model,
        temperature=req.temperature,
        top_p=req.top_p,
        num_ctx=req.num_ctx,
        max_tokens=req.max_tokens,
    )

    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
    job = _StreamingJob(
        kind="project" if full_project else "generate",
        meta={"prompt": req.message[:200], "project_name": project_name},
        queue=queue,
    )

    async def run_agent() -> None:
        orch = Orchestrator(cfg)
        try:
            if full_project:
                result = await orch.generate_project(
                    prompt=effective_prompt,
                    project_name=project_name,
                    output_path=req.output_path,
                    auto_test=req.auto_test,
                    max_loops=req.max_loops,
                    job=job,
                )
            else:
                result = await orch.generate_simple(
                    prompt=effective_prompt,
                    output_path=req.output_path,
                    project_name=project_name,
                    job=job,
                )
            job.complete(result.model_dump())
        except Exception as e:
            logger.exception("agent run failed")
            job.fail(str(e))
        finally:
            await queue.put("__DONE__")

    async def event_stream():
        yield _sse({
            "type": "start",
            "conversation_id": conv_id,
            "model": model,
            "mode": "agent",
            "project_name": project_name,
            "full_project": full_project,
            "per_agent_models": per_agent,
        })
        if web_results:
            yield _sse({"type": "web_search",
                        "query": (req.web_search_query or req.message),
                        "results": web_results})
        # Friendly opening line so the user sees something in the bubble immediately.
        opener = (
            f"**Agent mode** — building "
            f"{'full project' if full_project else 'code snippet'} "
            f"`{project_name}`…\n\n"
        )
        yield _sse({"type": "chunk", "content": opener})

        task = asyncio.create_task(run_agent())
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=60.0)
                except asyncio.TimeoutError:
                    yield _sse({"type": "chunk", "content": "_…still working…_\n"})
                    continue
                if msg == "__DONE__":
                    break
                if isinstance(msg, dict) and msg.get("_evt") == "agent":
                    payload = {k: v for k, v in msg.items() if k != "_evt"}
                    payload["type"] = "agent"
                    yield _sse(payload)
                    # Also surface as a human-readable chunk in the bubble.
                    yield _sse({
                        "type": "chunk",
                        "content": (
                            f"- **{payload.get('name','agent')}** "
                            f"(`{payload.get('model','')}`) "
                            f"— {payload.get('status','')} "
                            f"{payload.get('message','')}\n"
                        ).rstrip() + "\n",
                    })
                    continue
                yield _sse({"type": "chunk", "content": f"- {msg}\n"})

            # Summary
            if job.status == "completed" and isinstance(job.result, dict):
                files = job.result.get("files") or []
                out = job.result.get("output_path", "")
                summary = (
                    f"\n\n**Done.** Wrote {len(files)} file(s) to `{out}`.\n\n"
                )
                if files:
                    summary += "```\n" + "\n".join(files) + "\n```\n"
                if full_project:
                    summary += (
                        f"\nProject plan: [/plans/{project_name}](/plans/{project_name})\n"
                    )
                yield _sse({"type": "chunk", "content": summary})
                yield _sse({"type": "done", "job_id": job.id, "result": job.result})
            else:
                err = job.error or "agent failed"
                yield _sse({"type": "chunk", "content": f"\n\n**Error:** {err}\n"})
                yield _sse({"type": "error", "message": err})
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

"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.config import get_settings
from app.core.logging_config import logger, setup_logging
from app.routers import analyze, browse, chat, generate, status, test_fix


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info(f"Agent API v{__version__} starting")
    logger.info(f"Ollama backend: {settings.ollama_base_url}")
    logger.info(f"Output dir: {settings.output_dir.resolve()}")
    yield
    logger.info("Agent API shutting down")


app = FastAPI(
    title="AI Coding Agent API",
    description=(
        "Autonomous multi-agent AI coding platform powered by Ollama. "
        "Refines prompts, plans projects, generates code, runs tests, and self-fixes errors."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router)
app.include_router(test_fix.router)
app.include_router(status.router)
app.include_router(chat.router)
app.include_router(analyze.router)
app.include_router(browse.router)


@app.get("/")
async def root():
    return {
        "name": "AI Coding Agent API",
        "version": __version__,
        "docs": "/docs",
        "endpoints": [
            "POST /generate",
            "POST /generate/stream",
            "POST /generate/project",
            "POST /test",
            "POST /fix",
            "GET  /status",
            "GET  /status/{job_id}",
            "GET  /logs/{job_id}",
            "GET  /plans",
            "GET  /plans/{project}",
            "WS   /ws/logs/{job_id}",
            "GET  /api/models",
            "POST /api/chat",
            "POST /analyze",
            "POST /analyze/sync",
            "GET  /analyze/memory",
            "POST /analyze/ask",
        ],
    }


def run() -> None:
    import uvicorn

    s = get_settings()
    uvicorn.run("app.main:app", host=s.app_host, port=s.app_port, reload=False)


if __name__ == "__main__":
    run()

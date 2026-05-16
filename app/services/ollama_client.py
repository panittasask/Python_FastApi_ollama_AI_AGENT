"""Async Ollama HTTP client with retry, streaming, and cancellation support."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.exceptions import OllamaError
from app.core.logging_config import logger


class OllamaClient:
    """Thin async client wrapping the Ollama REST API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.timeout = timeout or settings.ollama_timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "OllamaClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout, connect=15.0),
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _ensure(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=15.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ---------- core ops ----------

    async def list_models(self) -> list[dict[str, Any]]:
        client = self._ensure()
        try:
            r = await client.get("/api/tags")
            r.raise_for_status()
            return r.json().get("models", [])
        except httpx.HTTPError as e:
            raise OllamaError(f"Failed to list models: {e}") from e

    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        top_p: float = 0.9,
        num_ctx: int = 8192,
        num_predict: int = 8192,
        stop: Optional[list[str]] = None,
        json_mode: bool = False,
        max_retries: int = 3,
    ) -> str:
        """Single-shot non-streaming generate. Returns the assembled response text."""
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
        }
        if system:
            payload["system"] = system
        if stop:
            payload["options"]["stop"] = stop
        if json_mode:
            payload["format"] = "json"

        client = self._ensure()
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_retries),
                wait=wait_exponential(multiplier=1, min=2, max=20),
                retry=retry_if_exception_type((httpx.HTTPError, OllamaError)),
                reraise=True,
            ):
                with attempt:
                    logger.debug(f"[ollama.generate] model={model} attempt={attempt.retry_state.attempt_number}")
                    r = await client.post("/api/generate", json=payload)
                    if r.status_code >= 500:
                        raise OllamaError(f"Ollama 5xx: {r.status_code} {r.text[:200]}")
                    r.raise_for_status()
                    data = r.json()
                    return data.get("response", "")
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama generate failed: {e}") from e
        return ""

    async def stream_generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        top_p: float = 0.9,
        num_ctx: int = 8192,
        num_predict: int = 8192,
    ) -> AsyncIterator[str]:
        """Stream tokens from Ollama as they arrive."""
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
        }
        if system:
            payload["system"] = system

        client = self._ensure()
        try:
            async with client.stream("POST", "/api/generate", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    chunk = obj.get("response", "")
                    if chunk:
                        yield chunk
                    if obj.get("done"):
                        break
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama stream failed: {e}") from e

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        top_p: float = 0.9,
        num_ctx: int = 8192,
        num_predict: int = 8192,
        json_mode: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
        }
        if json_mode:
            payload["format"] = "json"

        client = self._ensure()
        try:
            r = await client.post("/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content", "")
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama chat failed: {e}") from e

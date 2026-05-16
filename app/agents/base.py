"""Common prompt templates and base agent class."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.config import Settings, get_settings
from app.models.schemas import ModelConfig
from app.services.ollama_client import OllamaClient


@dataclass
class GenParams:
    model: str
    temperature: float
    top_p: float
    num_ctx: int
    num_predict: int


def resolve_params(
    role: str,
    cfg: Optional[ModelConfig],
    settings: Optional[Settings] = None,
) -> GenParams:
    s = settings or get_settings()
    model_map = {
        "refiner": s.refiner_model,
        "coder": s.coder_model,
        "fix": s.fix_model,
        "planner": s.planner_model,
    }
    model = model_map[role]
    temp, top_p, max_tok, ctx = s.temperature, s.top_p, s.max_tokens, s.num_ctx
    if cfg:
        override = {
            "refiner": cfg.refiner_model,
            "coder": cfg.coder_model,
            "fix": cfg.fix_model,
            "planner": cfg.planner_model,
        }[role]
        if override:
            model = override
        if cfg.temperature is not None:
            temp = cfg.temperature
        if cfg.top_p is not None:
            top_p = cfg.top_p
        if cfg.max_tokens is not None:
            max_tok = cfg.max_tokens
        if cfg.num_ctx is not None:
            ctx = cfg.num_ctx
    return GenParams(model=model, temperature=temp, top_p=top_p, num_ctx=ctx, num_predict=max_tok)


class BaseAgent:
    role: str = "base"
    system_prompt: str = ""

    def __init__(self, client: OllamaClient, config: Optional[ModelConfig] = None) -> None:
        self.client = client
        self.config = config
        self.params = resolve_params(self.role, config)

    async def _generate(self, user_prompt: str, json_mode: bool = False) -> str:
        return await self.client.generate(
            model=self.params.model,
            prompt=user_prompt,
            system=self.system_prompt or None,
            temperature=self.params.temperature,
            top_p=self.params.top_p,
            num_ctx=self.params.num_ctx,
            num_predict=self.params.num_predict,
            json_mode=json_mode,
        )

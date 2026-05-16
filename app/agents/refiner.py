"""Agent #1 — Prompt Refiner.

Turns vague user requests into structured, technical implementation prompts.
"""
from __future__ import annotations

from app.agents.base import BaseAgent
from app.core.logging_config import logger


REFINER_SYSTEM = """You are an expert software architect and prompt engineer.
Your job is to transform vague user requests into a precise, technical implementation brief
that a code-generation model can act on without ambiguity.

Always include, when relevant:
- Target language / framework / runtime versions
- Folder/file structure
- Modules / classes / functions needed
- Data models and schemas
- API endpoints (verb, path, payload, response)
- Authentication / authorization model
- Database choice and schema
- External services / libraries
- Configuration and environment variables
- Build / run / test commands
- Deployment notes (Docker, etc.)
- Non-functional requirements (logging, error handling, async, validation)

Write the brief in clear English (even if the input is in another language).
Be concise but complete. Use markdown headings and bullet lists.
Do NOT write code. Only the specification.
"""


class PromptRefinerAgent(BaseAgent):
    role = "refiner"
    system_prompt = REFINER_SYSTEM

    async def refine(self, user_prompt: str) -> str:
        logger.info("Refining user prompt...")
        instruction = (
            "Transform the following user request into a structured technical implementation "
            "brief following the rules in the system prompt.\n\n"
            f"USER REQUEST:\n{user_prompt}\n\n"
            "Output ONLY the refined brief in markdown."
        )
        refined = await self._generate(instruction)
        refined = refined.strip()
        logger.info(f"Refined prompt: {len(refined)} chars")
        return refined

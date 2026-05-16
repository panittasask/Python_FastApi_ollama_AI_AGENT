"""Planner Agent — produces a ProjectPlan from a refined brief."""
from __future__ import annotations

from app.agents.base import BaseAgent
from app.core.exceptions import GenerationError
from app.core.logging_config import logger
from app.models.schemas import PlanTask, ProjectPlan, TaskStatus
from app.utils.parsing import extract_json


PLANNER_SYSTEM = """You are a senior tech lead. Given a technical implementation brief,
produce a structured JSON project plan containing every file that must be generated,
in dependency order. Be exhaustive — include configs, tests, docs, Docker, CI, etc.

Output STRICT JSON only, no commentary, with this schema:
{
  "project_name": "string",
  "description": "string",
  "architecture": "markdown string",
  "dependencies": ["pkg==ver", ...],
  "tasks": [
    {
      "id": "T01",
      "title": "Create FastAPI entrypoint",
      "description": "what this task does",
      "file_path": "app/main.py",
      "depends_on": ["T00"]
    }
  ]
}
Rules:
- task IDs are zero-padded (T01, T02, ...)
- order tasks so dependencies come first
- every code/config file gets its own task with a file_path
- include README.md, requirements.txt, .env.example, Dockerfile, docker-compose.yml, tests
- between 8 and 40 tasks
"""


class PlannerAgent(BaseAgent):
    role = "planner"
    system_prompt = PLANNER_SYSTEM

    async def plan(self, refined_brief: str, project_name: str) -> ProjectPlan:
        logger.info(f"Planning project '{project_name}'...")
        prompt = (
            "Create the project plan JSON for the following brief.\n\n"
            f"PROJECT NAME: {project_name}\n\n"
            f"BRIEF:\n{refined_brief}\n\n"
            "Return ONLY valid JSON."
        )
        raw = await self._generate(prompt, json_mode=True)
        data = extract_json(raw)
        if not isinstance(data, dict):
            raise GenerationError("Planner did not return a JSON object")

        tasks_data = data.get("tasks") or []
        tasks: list[PlanTask] = []
        for i, t in enumerate(tasks_data, start=1):
            tid = str(t.get("id") or f"T{i:02d}")
            tasks.append(
                PlanTask(
                    id=tid,
                    title=str(t.get("title") or f"Task {tid}"),
                    description=str(t.get("description") or ""),
                    file_path=t.get("file_path"),
                    depends_on=[str(x) for x in (t.get("depends_on") or [])],
                    status=TaskStatus.PENDING,
                )
            )
        plan = ProjectPlan(
            project_name=str(data.get("project_name") or project_name),
            description=str(data.get("description") or ""),
            architecture=str(data.get("architecture") or ""),
            dependencies=[str(x) for x in (data.get("dependencies") or [])],
            tasks=tasks,
        )
        if not plan.tasks:
            raise GenerationError("Planner returned no tasks")
        logger.info(f"Plan created: {len(plan.tasks)} tasks")
        return plan

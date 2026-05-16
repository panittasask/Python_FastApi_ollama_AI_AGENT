"""Manages project_plan.md — a human-readable, machine-parseable plan file."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles

from app.core.exceptions import PlanError
from app.core.logging_config import logger
from app.models.schemas import PlanTask, ProjectPlan, TaskStatus

PLAN_FILE = "project_plan.md"

_STATUS_ICON = {
    TaskStatus.PENDING: "[ ]",
    TaskStatus.IN_PROGRESS: "[~]",
    TaskStatus.COMPLETED: "[x]",
    TaskStatus.FAILED: "[!]",
}


class PlanManager:
    """Read/write/update the markdown project plan."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.plan_path = self.project_dir / PLAN_FILE

    # --- IO ---

    async def save(self, plan: ProjectPlan) -> None:
        plan.updated_at = datetime.utcnow()
        md = self.render(plan)
        async with aiofiles.open(self.plan_path, "w", encoding="utf-8", newline="\n") as f:
            await f.write(md)
        logger.info(f"Plan saved: {self.plan_path}")

    async def load(self) -> Optional[ProjectPlan]:
        if not self.plan_path.exists():
            return None
        async with aiofiles.open(self.plan_path, "r", encoding="utf-8") as f:
            text = await f.read()
        try:
            return self.parse(text)
        except Exception as e:  # pragma: no cover - parser is best-effort
            raise PlanError(f"Failed to parse plan: {e}") from e

    # --- mutators ---

    async def mark_task(
        self,
        task_id: str,
        status: TaskStatus,
        notes: str = "",
    ) -> ProjectPlan:
        plan = await self.load()
        if not plan:
            raise PlanError("Plan not found")
        for t in plan.tasks:
            if t.id == task_id:
                t.status = status
                if notes:
                    t.notes = notes
                break
        else:
            raise PlanError(f"Task not found: {task_id}")
        await self.save(plan)
        return plan

    async def add_task(self, task: PlanTask) -> ProjectPlan:
        plan = await self.load()
        if not plan:
            raise PlanError("Plan not found")
        plan.tasks.append(task)
        await self.save(plan)
        return plan

    # --- rendering ---

    @staticmethod
    def render(plan: ProjectPlan) -> str:
        total = len(plan.tasks)
        done = sum(1 for t in plan.tasks if t.status == TaskStatus.COMPLETED)
        pct = int(100 * done / total) if total else 0

        lines: list[str] = []
        lines.append(f"# {plan.project_name}")
        lines.append("")
        lines.append(f"_Last updated: {plan.updated_at.isoformat()}_")
        lines.append("")
        if plan.description:
            lines.append("## Description")
            lines.append("")
            lines.append(plan.description.strip())
            lines.append("")
        if plan.architecture:
            lines.append("## Architecture")
            lines.append("")
            lines.append(plan.architecture.strip())
            lines.append("")
        if plan.dependencies:
            lines.append("## Dependencies")
            lines.append("")
            for d in plan.dependencies:
                lines.append(f"- {d}")
            lines.append("")
        lines.append(f"## Progress: {done}/{total} ({pct}%)")
        lines.append("")
        lines.append("## Tasks")
        lines.append("")
        for t in plan.tasks:
            icon = _STATUS_ICON[t.status]
            head = f"- {icon} **{t.id}** — {t.title}"
            if t.file_path:
                head += f"  _(file: `{t.file_path}`)_"
            lines.append(head)
            if t.description:
                lines.append(f"    - {t.description.strip()}")
            if t.depends_on:
                lines.append(f"    - depends on: {', '.join(t.depends_on)}")
            if t.notes:
                lines.append(f"    - notes: {t.notes.strip()}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def parse(text: str) -> ProjectPlan:
        """Lightweight parser — extracts project name + tasks from rendered output."""
        import re

        name_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        project_name = name_match.group(1).strip() if name_match else "project"

        plan = ProjectPlan(project_name=project_name)

        # Description / architecture (best effort)
        def grab(section: str) -> str:
            m = re.search(
                rf"^##\s+{section}\s*\n\n(.+?)(?=\n##\s|\Z)",
                text,
                re.MULTILINE | re.DOTALL | re.IGNORECASE,
            )
            return m.group(1).strip() if m else ""

        plan.description = grab("Description")
        plan.architecture = grab("Architecture")

        dep_block = grab("Dependencies")
        if dep_block:
            plan.dependencies = [
                line.lstrip("- ").strip()
                for line in dep_block.splitlines()
                if line.strip().startswith("-")
            ]

        # Tasks
        task_re = re.compile(
            r"^- \[(.)\]\s+\*\*(?P<id>[^*]+)\*\*\s+—\s+(?P<title>.+?)(?:\s+_\(file:\s*`(?P<file>[^`]+)`\)_)?\s*$",
            re.MULTILINE,
        )
        status_map = {
            " ": TaskStatus.PENDING,
            "~": TaskStatus.IN_PROGRESS,
            "x": TaskStatus.COMPLETED,
            "X": TaskStatus.COMPLETED,
            "!": TaskStatus.FAILED,
        }
        for m in task_re.finditer(text):
            plan.tasks.append(
                PlanTask(
                    id=m.group("id").strip(),
                    title=m.group("title").strip(),
                    file_path=m.group("file"),
                    status=status_map.get(m.group(1), TaskStatus.PENDING),
                )
            )
        return plan

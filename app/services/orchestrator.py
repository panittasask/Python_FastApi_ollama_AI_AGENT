"""High-level multi-agent orchestration.

Coordinates: refiner -> planner -> coder loop -> tester -> fixer loop.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from app.agents import (
    CodeGenerationAgent,
    FixAgent,
    PlannerAgent,
    PromptRefinerAgent,
)
from app.core.config import get_settings
from app.core.logging_config import logger
from app.models.schemas import (
    GenerateResponse,
    ModelConfig,
    PlanTask,
    ProjectPlan,
    TaskStatus,
    TestResult,
)
from app.services.file_manager import FileManager
from app.services.job_registry import Job
from app.services.ollama_client import OllamaClient
from app.services.plan_manager import PlanManager
from app.services.test_runner import TestRunner


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()).strip("_") or "project"


class Orchestrator:
    def __init__(self, config: Optional[ModelConfig] = None) -> None:
        self.config = config
        self.settings = get_settings()

    # ---------- single-shot generation ----------

    async def generate_simple(
        self,
        prompt: str,
        output_path: Optional[str] = None,
        project_name: Optional[str] = None,
        job: Optional[Job] = None,
    ) -> GenerateResponse:
        """Refine -> generate code (no plan, no test loop)."""
        name = _slug(project_name or "snippet")
        out_dir = Path(output_path) if output_path else self.settings.output_dir / name
        fm = FileManager(out_dir)

        async with OllamaClient() as client:
            refiner = PromptRefinerAgent(client, self.config)
            coder = CodeGenerationAgent(client, self.config)

            if job:
                job.log("refining prompt")
            refined = await refiner.refine(prompt)

            if job:
                job.log("generating code")
            fake_task = PlanTask(id="T01", title="Generate requested code", description=refined)
            fake_plan = ProjectPlan(project_name=name, description=refined)
            result = await coder.generate_file(fake_task, fake_plan, existing_files=[])

            written: list[str] = []
            for f in result.files:
                await fm.write_file(f.path, f.content)
                written.append(f.path)

        return GenerateResponse(
            project_name=name,
            output_path=str(fm.base_dir),
            files=written,
            refined_prompt=refined,
        )

    # ---------- full project ----------

    async def generate_project(
        self,
        prompt: str,
        project_name: str,
        output_path: Optional[str] = None,
        auto_test: Optional[bool] = None,
        max_loops: Optional[int] = None,
        job: Optional[Job] = None,
    ) -> GenerateResponse:
        name = _slug(project_name)
        out_dir = Path(output_path) if output_path else self.settings.output_dir / name
        fm = FileManager(out_dir)
        pm = PlanManager(out_dir)
        auto_test = self.settings.enable_auto_test if auto_test is None else auto_test
        max_loops = max_loops or self.settings.max_generation_loops

        async with OllamaClient() as client:
            refiner = PromptRefinerAgent(client, self.config)
            planner = PlannerAgent(client, self.config)
            coder = CodeGenerationAgent(client, self.config)
            fixer = FixAgent(client, self.config)

            # --- 1. Refine ---
            if job:
                job.log("refining prompt")
            refined = await refiner.refine(prompt)

            # --- 2. Plan ---
            if job:
                job.log("planning project")
            plan = await planner.plan(refined, name)
            await pm.save(plan)
            if job:
                job.log(f"plan ready: {len(plan.tasks)} tasks")

            # --- 3. Iterative generation ---
            loops = 0
            while loops < max_loops:
                pending = self._next_runnable(plan)
                if not pending:
                    break
                loops += 1
                task = pending
                task.status = TaskStatus.IN_PROGRESS
                await pm.save(plan)
                if job:
                    job.log(f"[{task.id}] {task.title}")
                try:
                    res = await coder.generate_file(
                        task=task,
                        plan=plan,
                        existing_files=fm.list_files(),
                    )
                    if not res.files:
                        raise RuntimeError("coder returned no files")
                    for f in res.files:
                        await fm.write_file(f.path, f.content)
                    task.status = TaskStatus.COMPLETED
                    task.notes = f"generated {len(res.files)} file(s)"
                except Exception as e:
                    logger.exception(f"Task {task.id} failed")
                    task.status = TaskStatus.FAILED
                    task.notes = f"error: {e}"
                    if job:
                        job.log(f"[{task.id}] FAILED: {e}")
                await pm.save(plan)

            # --- 4. Test + Fix loop ---
            if auto_test:
                if job:
                    job.log("running tests")
                await self._test_fix_loop(fm, fixer, job)

        return GenerateResponse(
            project_name=name,
            output_path=str(fm.base_dir),
            files=fm.list_files(),
            refined_prompt=refined,
            notes=f"loops={loops}",
        )

    def _next_runnable(self, plan: ProjectPlan) -> Optional[PlanTask]:
        done_ids = {t.id for t in plan.tasks if t.status == TaskStatus.COMPLETED}
        for t in plan.tasks:
            if t.status != TaskStatus.PENDING:
                continue
            if all(dep in done_ids for dep in t.depends_on):
                return t
        return None

    # ---------- test+fix loop ----------

    async def _test_fix_loop(
        self,
        fm: FileManager,
        fixer: FixAgent,
        job: Optional[Job],
    ) -> TestResult:
        runner = TestRunner(fm.base_dir)
        last: Optional[TestResult] = None
        for i in range(self.settings.max_fix_iterations + 1):
            last = await runner.run()
            if job:
                job.log(f"test iter {i}: rc={last.return_code} cmd={last.command!r}")
            if last.success:
                break
            error_blob = (last.stderr + "\n" + last.stdout)[-6000:]
            files_ctx = await self._collect_relevant_files(fm, error_blob)
            if job:
                job.log(f"asking fixer with {len(files_ctx)} file(s)")
            try:
                result = await fixer.fix(error_blob, files_ctx)
            except Exception as e:
                logger.exception("fixer crashed")
                if job:
                    job.log(f"fixer crashed: {e}")
                break
            if not result.files:
                if job:
                    job.log("fixer returned no files; stopping")
                break
            for f in result.files:
                await fm.write_file(f.path, f.content)
        return last  # type: ignore[return-value]

    async def _collect_relevant_files(
        self, fm: FileManager, error_text: str
    ) -> dict[str, str]:
        """Pick files mentioned in the error trace plus a couple of likely suspects."""
        all_files = fm.list_files()
        mentioned: list[str] = []
        for path in all_files:
            if path in error_text or Path(path).name in error_text:
                mentioned.append(path)
        if not mentioned:
            # fall back to small code files
            preferred = [p for p in all_files if p.endswith((".py", ".ts", ".js"))][:3]
            mentioned = preferred
        out: dict[str, str] = {}
        for p in mentioned[:6]:
            try:
                out[p] = await fm.read_file(p)
            except Exception:
                continue
        return out

    # ---------- direct fix ----------

    async def fix_project(
        self,
        project_path: str,
        error_log: str,
        file_path: Optional[str] = None,
        job: Optional[Job] = None,
    ) -> list[str]:
        fm = FileManager(Path(project_path))
        files_ctx: dict[str, str] = {}
        if file_path and fm.exists(file_path):
            files_ctx[file_path] = await fm.read_file(file_path)
        else:
            files_ctx = await self._collect_relevant_files(fm, error_log)

        async with OllamaClient() as client:
            fixer = FixAgent(client, self.config)
            res = await fixer.fix(error_log, files_ctx)

        written: list[str] = []
        for f in res.files:
            await fm.write_file(f.path, f.content)
            written.append(f.path)
        if job:
            job.log(f"fix wrote {len(written)} file(s)")
        return written

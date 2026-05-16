"""Code Generation Agent — produces complete file contents."""
from __future__ import annotations

from typing import Optional

from app.agents.base import BaseAgent
from app.core.logging_config import logger
from app.models.schemas import (
    CodeGenerationResult,
    GeneratedFile,
    PlanTask,
    ProjectPlan,
)
from app.utils.parsing import parse_file_blocks


CODER_SYSTEM = """You are an elite senior software engineer.
You write production-ready, modular, type-safe, well-documented code.

When asked to produce one or more files, ALWAYS use this exact format for each file:

File: <relative/path/to/file.ext>
```<language>
<full file content here>
```

Rules:
- Output complete file contents — never use placeholders like '...' or 'rest of code'.
- Prefer async I/O where it makes sense.
- Use the dependencies and architecture provided.
- Include docstrings and type hints in Python.
- Do not include explanations outside the code blocks.
"""


class CodeGenerationAgent(BaseAgent):
    role = "coder"
    system_prompt = CODER_SYSTEM

    async def generate_file(
        self,
        task: PlanTask,
        plan: ProjectPlan,
        existing_files: list[str],
        extra_context: Optional[str] = None,
        continuation_block: Optional[str] = None,
    ) -> CodeGenerationResult:
        deps_block = "\n".join(f"- {d}" for d in plan.dependencies) or "(none)"
        files_block = "\n".join(f"- {f}" for f in existing_files[:60]) or "(none yet)"
        prompt = (
            f"PROJECT: {plan.project_name}\n"
            f"DESCRIPTION: {plan.description}\n\n"
            f"ARCHITECTURE:\n{plan.architecture}\n\n"
            f"DEPENDENCIES:\n{deps_block}\n\n"
            f"FILES ALREADY GENERATED:\n{files_block}\n\n"
            f"CURRENT TASK ID: {task.id}\n"
            f"TITLE: {task.title}\n"
            f"DESCRIPTION: {task.description}\n"
            f"TARGET FILE: {task.file_path or '(decide based on task)'}\n"
        )
        if continuation_block:
            prompt = continuation_block + "\n---\n" + prompt
        if extra_context:
            prompt += f"\nADDITIONAL CONTEXT:\n{extra_context}\n"
        prompt += (
            "\nProduce the complete file content using the required "
            "'File: <path>' + fenced code block format. If the task naturally requires "
            "more than one file, output all of them in the same format. No prose."
        )

        raw = await self._generate(prompt)
        files = parse_file_blocks(raw)

        if not files and task.file_path:
            # Fallback: treat whole response as the file body
            logger.warning(f"Coder produced no parseable file blocks for {task.id}; using raw body")
            files = [{"path": task.file_path, "content": raw.strip()}]

        return CodeGenerationResult(
            files=[GeneratedFile(path=f["path"], content=f["content"]) for f in files],
            notes="",
        )

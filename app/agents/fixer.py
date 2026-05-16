"""Fix Agent — receives error logs and the offending file(s); returns fixed file(s)."""
from __future__ import annotations

from typing import Optional

from app.agents.base import BaseAgent
from app.core.logging_config import logger
from app.models.schemas import CodeGenerationResult, GeneratedFile
from app.utils.parsing import parse_file_blocks


FIX_SYSTEM = """You are an expert debugger and software engineer.
You are given an error log and the current contents of one or more source files.
Your job: produce CORRECTED full file contents that resolve the error.

Output rules (strict):
- For each file you change or create, use:

File: <relative/path/to/file.ext>
```<language>
<complete corrected file content>
```

- Output ONLY the files you are changing — complete contents, not diffs.
- No explanations outside code blocks.
"""


class FixAgent(BaseAgent):
    role = "fix"
    system_prompt = FIX_SYSTEM

    async def fix(
        self,
        error_log: str,
        files: dict[str, str],
        hint: Optional[str] = None,
    ) -> CodeGenerationResult:
        logger.info(f"Fixing with {len(files)} file(s) of context, error log {len(error_log)} chars")
        joined = []
        for path, content in files.items():
            joined.append(f"File: {path}\n```\n{content}\n```")
        files_block = "\n\n".join(joined) if joined else "(no files provided)"
        prompt = (
            f"ERROR LOG:\n```\n{error_log[:8000]}\n```\n\n"
            f"CURRENT FILES:\n{files_block}\n\n"
        )
        if hint:
            prompt += f"HINT: {hint}\n\n"
        prompt += "Return only the corrected file(s) in the required format."

        raw = await self._generate(prompt)
        parsed = parse_file_blocks(raw)
        return CodeGenerationResult(
            files=[GeneratedFile(path=p["path"], content=p["content"]) for p in parsed]
        )

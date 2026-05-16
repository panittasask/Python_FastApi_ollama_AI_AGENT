"""Run tests (or arbitrary commands) inside a generated project and capture output."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

from app.core.logging_config import logger
from app.models.schemas import TestResult


def _detect_command(project_dir: Path) -> Optional[str]:
    if (project_dir / "pytest.ini").exists() or (project_dir / "tests").is_dir():
        return f"{sys.executable} -m pytest -x -q"
    if (project_dir / "package.json").exists():
        return "npm test --silent"
    if (project_dir / "go.mod").exists():
        return "go test ./..."
    if (project_dir / "Cargo.toml").exists():
        return "cargo test --quiet"
    if (project_dir / "pyproject.toml").exists():
        return f"{sys.executable} -m pytest -x -q"
    return None


class TestRunner:
    def __init__(self, project_dir: Path, default_timeout: int = 300) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.default_timeout = default_timeout

    async def run(self, command: Optional[str] = None, timeout: Optional[int] = None) -> TestResult:
        cmd = command or _detect_command(self.project_dir)
        if not cmd:
            return TestResult(
                success=True,
                stdout="",
                stderr="no test command detected; skipping",
                return_code=0,
                command="",
            )
        logger.info(f"Running tests: {cmd} (cwd={self.project_dir})")
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=str(self.project_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout or self.default_timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return TestResult(
                    success=False,
                    stdout="",
                    stderr=f"timeout after {timeout or self.default_timeout}s",
                    return_code=-1,
                    command=cmd,
                )
        except FileNotFoundError as e:
            return TestResult(
                success=False, stdout="", stderr=str(e), return_code=-1, command=cmd
            )
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        rc = proc.returncode or 0
        return TestResult(
            success=rc == 0,
            stdout=stdout[-12000:],
            stderr=stderr[-12000:],
            return_code=rc,
            command=cmd,
        )

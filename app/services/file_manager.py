"""Safe file system operations confined to a base directory."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import aiofiles

from app.core.exceptions import FileOperationError
from app.core.logging_config import logger


class FileManager:
    """Filesystem helper that confines writes within a project root."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _safe(self, rel_path: str) -> Path:
        p = (self.base_dir / rel_path).resolve()
        try:
            p.relative_to(self.base_dir)
        except ValueError as e:
            raise FileOperationError(f"Path escapes project root: {rel_path}") from e
        return p

    async def write_file(self, rel_path: str, content: str, overwrite: bool = True) -> Path:
        target = self._safe(rel_path)
        if target.exists() and not overwrite:
            logger.info(f"Skip existing file: {target}")
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        # rollback protection: backup existing
        backup: Optional[Path] = None
        if target.exists():
            backup = target.with_suffix(target.suffix + ".bak")
            try:
                shutil.copy2(target, backup)
            except OSError:
                backup = None
        try:
            async with aiofiles.open(target, "w", encoding="utf-8", newline="\n") as f:
                await f.write(content)
            if backup and backup.exists():
                backup.unlink(missing_ok=True)
            logger.info(f"Wrote file: {target.relative_to(self.base_dir)} ({len(content)} chars)")
            return target
        except OSError as e:
            if backup and backup.exists():
                shutil.move(str(backup), str(target))
            raise FileOperationError(f"Failed to write {rel_path}: {e}") from e

    async def read_file(self, rel_path: str) -> str:
        target = self._safe(rel_path)
        if not target.exists():
            raise FileOperationError(f"File not found: {rel_path}")
        async with aiofiles.open(target, "r", encoding="utf-8") as f:
            return await f.read()

    async def append_file(self, rel_path: str, content: str) -> Path:
        target = self._safe(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(target, "a", encoding="utf-8") as f:
            await f.write(content)
        return target

    def exists(self, rel_path: str) -> bool:
        return self._safe(rel_path).exists()

    def list_files(self, pattern: str = "**/*") -> list[str]:
        return [
            str(p.relative_to(self.base_dir)).replace("\\", "/")
            for p in self.base_dir.glob(pattern)
            if p.is_file()
        ]

    def ensure_dir(self, rel_path: str) -> Path:
        d = self._safe(rel_path)
        d.mkdir(parents=True, exist_ok=True)
        return d

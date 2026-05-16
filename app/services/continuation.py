"""Helpers for "continuation mode" — editing an existing project safely.

The orchestrator uses these helpers when the user points the agent at a folder
that already contains source code (or has a `.agent/` memory from a previous
analyze run). The goal is to prefer modifying existing files over creating
duplicates.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from app.services.file_manager import FileManager
from app.services.project_memory import MEMORY_DIRNAME, ProjectMemory


# ---------------------------------------------------------------- detection

# Files/dirs that should be ignored when judging "is this an existing project".
_NOISE_DIRS = {
    ".git", ".agent", ".vscode", ".idea", "node_modules", "__pycache__",
    "dist", "build", ".next", ".angular", "venv", ".venv", "env",
    "generated_projects", ".pytest_cache", ".mypy_cache",
}
_NOISE_FILES = {".gitignore", ".gitkeep", "README.md", "LICENSE"}


def is_existing_project(root: Path) -> bool:
    """Return True if the folder appears to already contain a real codebase."""
    if not root.exists() or not root.is_dir():
        return False
    # Strong signal: previous analyze run.
    if (root / MEMORY_DIRNAME).exists():
        return True
    count = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        parts = set(rel.parts)
        if parts & _NOISE_DIRS:
            continue
        if p.name in _NOISE_FILES:
            continue
        count += 1
        if count >= 3:
            return True
    return False


# ------------------------------------------------------------- file picking

# Common code extensions we'll consider for content injection.
_CODE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte",
    ".go", ".rs", ".java", ".kt", ".cs", ".cpp", ".c", ".h", ".hpp",
    ".rb", ".php", ".scala", ".swift", ".sql",
    ".html", ".css", ".scss", ".sass",
    ".json", ".yaml", ".yml", ".toml", ".env",
}

_KEYWORD_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{2,}")


def _keywords(text: str, limit: int = 25) -> set[str]:
    words = [w.lower() for w in _KEYWORD_RE.findall(text or "")]
    unique: list[str] = []
    seen: set[str] = set()
    for w in words:
        if w in seen:
            continue
        seen.add(w)
        unique.append(w)
        if len(unique) >= limit:
            break
    return set(unique)


def pick_relevant_files(
    fm: FileManager,
    task_text: str,
    target_path: Optional[str],
    max_files: int = 6,
    max_chars_per_file: int = 2500,
) -> list[str]:
    """Pick existing project files most likely to be relevant to `task_text`.

    Scoring is dumb-but-effective:
      * target_path exact match: highest
      * filename appears in task text
      * keyword overlap between task and filename/path
      * same extension as target_path
    Returns up to `max_files` relative paths, capped by per-file size.
    """
    all_paths = [
        p for p in fm.list_files()
        if not any(part in _NOISE_DIRS for part in Path(p).parts)
        and Path(p).suffix.lower() in _CODE_EXTS
    ]
    if not all_paths:
        return []

    kws = _keywords(task_text)
    target_ext = Path(target_path).suffix.lower() if target_path else ""
    target_name = Path(target_path).name.lower() if target_path else ""

    scored: list[tuple[float, str]] = []
    for path in all_paths:
        score = 0.0
        p = Path(path)
        name = p.name.lower()
        if target_path and path == target_path:
            score += 100
        if target_name and target_name == name:
            score += 50
        if target_ext and p.suffix.lower() == target_ext:
            score += 5
        path_kws = _keywords(path)
        score += 3 * len(kws & path_kws)
        try:
            if (fm.base_dir / path).stat().st_size > max_chars_per_file * 4:
                score -= 2  # de-prioritize very large files
        except OSError:
            pass
        if score > 0:
            scored.append((score, path))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:max_files]]


async def load_files_content(
    fm: FileManager,
    paths: Iterable[str],
    max_chars_per_file: int = 2500,
) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in paths:
        try:
            content = await fm.read_file(rel)
        except Exception:
            continue
        if len(content) > max_chars_per_file:
            head = content[: max_chars_per_file - 200]
            out[rel] = head + f"\n\n# … truncated ({len(content) - len(head)} chars omitted) …\n"
        else:
            out[rel] = content
    return out


def load_memory_excerpt(root: Path, max_chars: int = 1500) -> str:
    """Return a compact excerpt from .agent/memory.json overview/architecture."""
    mem = ProjectMemory(root).load()
    if not mem:
        return ""
    analysis = mem.get("analysis") or {}
    parts = []
    if analysis.get("overview"):
        parts.append("OVERVIEW:\n" + str(analysis["overview"]))
    if analysis.get("architecture"):
        parts.append("ARCHITECTURE:\n" + str(analysis["architecture"]))
    patterns = analysis.get("patterns") or []
    if patterns:
        parts.append("PATTERNS:\n- " + "\n- ".join(str(p) for p in patterns[:10]))
    text = "\n\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n… (truncated)"
    return text


# --------------------------------------------------------------- changelog


def classify_writes(
    base_dir: Path,
    writes: list[tuple[str, str]],
) -> tuple[list[str], list[tuple[str, int, int]]]:
    """Split writes into (created, modified). `modified` carries size delta.

    `writes` is a list of (rel_path, new_content) BEFORE writing.
    """
    created: list[str] = []
    modified: list[tuple[str, int, int]] = []
    for rel, new_content in writes:
        target = base_dir / rel
        if target.exists():
            try:
                old = target.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                old = ""
            if old != new_content:
                modified.append((rel, len(old), len(new_content)))
        else:
            created.append(rel)
    return created, modified


def append_changelog(
    base_dir: Path,
    created: list[str],
    modified: list[tuple[str, int, int]],
    reason: str = "",
) -> None:
    if not created and not modified:
        return
    path = base_dir / "CHANGELOG_AGENT.md"
    header_needed = not path.exists()
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    lines: list[str] = []
    if header_needed:
        lines.append("# Agent change log\n")
        lines.append("_Automatically generated by the AI agent in continuation mode._\n")
    lines.append(f"\n## {ts}")
    if reason:
        lines.append(f"_Reason: {reason}_")
    if modified:
        lines.append("\n### Modified")
        for rel, old_n, new_n in modified:
            delta = new_n - old_n
            sign = "+" if delta >= 0 else ""
            lines.append(f"- `{rel}` ({sign}{delta} chars)")
    if created:
        lines.append("\n### Created")
        for rel in created:
            lines.append(f"- `{rel}`")
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ------------------------------------------------------------- prompt block


def build_continuation_block(
    files: dict[str, str],
    memory_excerpt: str = "",
) -> str:
    """Render existing-file context + 'modify-first' rules as a prompt block."""
    lines: list[str] = ["### EXISTING PROJECT CONTEXT", ""]
    if memory_excerpt:
        lines.append("#### Project memory")
        lines.append(memory_excerpt)
        lines.append("")
    if files:
        lines.append("#### Existing files (read these BEFORE deciding what to write)")
        for path, content in files.items():
            lines.append(f"\nFile: {path}")
            lang = (Path(path).suffix or "").lstrip(".")
            lines.append(f"```{lang}")
            lines.append(content)
            lines.append("```")
    lines.append("")
    lines.append(
        "### MODIFY-FIRST RULES (STRICT)\n"
        "You are editing an EXISTING codebase. Behave like a senior engineer "
        "joining an in-flight project:\n"
        "1. Prefer MODIFYING an existing file over creating a new one.\n"
        "2. Preserve the project's structure, naming conventions, style, "
        "imports and existing patterns.\n"
        "3. If an existing file already implements similar logic, EXTEND it. "
        "Do NOT create duplicates such as `*_v2`, `*_new`, `*_copy`, "
        "`*-final`, alternate components/services, or parallel modules.\n"
        "4. When you modify a file, output its COMPLETE new content (full "
        "file body) using the standard `File: <path>` + fenced code block "
        "format, reusing the EXACT same relative path as the existing file.\n"
        "5. Only create a brand-new file when the feature genuinely does not "
        "exist anywhere in the existing context above.\n"
        "6. Never delete unrelated code, comments, or imports from the "
        "existing files. Keep formatting consistent with what is already "
        "there (indentation, quote style, trailing newline).\n"
    )
    return "\n".join(lines)

"""Analyzer Agent — given a project scan, produce architectural understanding."""
from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.core.logging_config import logger
from app.utils.parsing import extract_json


ANALYZER_SYSTEM = """You are a senior software engineer joining an unfamiliar
codebase. You will receive a structured scan of a project (file tree, detected
frameworks, dependencies, sampled file contents). Produce a JSON understanding
of the project that another agent can use to safely continue development.

Rules:
- Be concrete and reference real files from the scan.
- Do not invent files, frameworks, or APIs that are not in the scan.
- If the scan is incomplete, say so in the "risks" array.
- Output STRICT JSON only, no commentary, matching this schema:

{
  "overview":        "2-4 paragraph plain-language summary of what the project is",
  "architecture":    "Markdown describing the architecture, layering, and data flow",
  "patterns":        ["short bullet about coding patterns / conventions", ...],
  "modules": [
    {"name": "module/feature name", "purpose": "what it does",
     "files": ["relative/path.ext", ...]}
  ],
  "todos": [
    {"priority": "high|med|low",
     "title": "actionable task",
     "why": "one-line justification",
     "files": ["relative/path.ext", ...]}
  ],
  "tech_debt": [
    {"title": "short", "detail": "what is wrong and why it matters"}
  ],
  "risks": ["assumption or unknown that should be verified", ...]
}
"""


# Trim helpers — keep prompt small enough for typical local models.
_MAX_TREE_CHARS = 6_000
_MAX_SAMPLES = 18
_MAX_SAMPLE_CHARS = 4_500


def _shorten(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + "\n…(truncated)"


def _format_scan_for_prompt(scan: dict[str, Any]) -> str:
    parts: list[str] = []
    parts.append(f"# Project: {scan.get('name')}")
    parts.append(f"Root: `{scan.get('root')}`")
    parts.append(
        f"Files: {scan.get('total_files', 0)} · "
        f"Dirs: {scan.get('total_dirs', 0)} · "
        f"Lines: {scan.get('total_lines', 0):,}"
    )

    fw = scan.get("frameworks") or []
    pm = scan.get("package_managers") or []
    parts.append(f"Frameworks: {', '.join(fw) or '(none detected)'}")
    parts.append(f"Package managers: {', '.join(pm) or '(none)'}")

    langs = scan.get("languages") or {}
    if langs:
        top = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:8]
        parts.append("Languages: " + ", ".join(f"{k}({v})" for k, v in top))

    entries = scan.get("entry_points") or []
    if entries:
        parts.append("Entry points: " + ", ".join(f"`{e}`" for e in entries[:10]))

    configs = scan.get("config_files") or []
    if configs:
        parts.append("Config files: " + ", ".join(f"`{c}`" for c in configs[:20]))

    deps = scan.get("dependencies") or {}
    if deps:
        parts.append("\n## Dependencies (sample)")
        for k, v in list(deps.items())[:6]:
            parts.append(f"- {k}: {', '.join(v[:25])}")

    tree = scan.get("tree") or ""
    if tree:
        parts.append("\n## Tree")
        parts.append("```")
        parts.append(_shorten(tree, _MAX_TREE_CHARS))
        parts.append("```")

    todos = scan.get("todo_comments") or []
    if todos:
        parts.append("\n## TODO/FIXME comments found")
        for c in todos[:20]:
            parts.append(f"- {c.get('path')}:{c.get('line')} [{c.get('tag')}] {c.get('text')}")

    readme = scan.get("readme_excerpt")
    if readme:
        parts.append("\n## README excerpt")
        parts.append("```markdown")
        parts.append(_shorten(readme, 3_000))
        parts.append("```")

    samples = (scan.get("sample_files") or [])[:_MAX_SAMPLES]
    if samples:
        parts.append("\n## Sampled file contents")
        for s in samples:
            lang = s.get("language") or ""
            path = s.get("path", "?")
            body = _shorten(s.get("content") or "", _MAX_SAMPLE_CHARS)
            trunc = " (truncated)" if s.get("truncated") else ""
            parts.append(f"\n### `{path}`{trunc}")
            parts.append(f"```{lang}")
            parts.append(body)
            parts.append("```")

    return "\n".join(parts)


class AnalyzerAgent(BaseAgent):
    """Uses the planner model to analyze an existing codebase scan."""
    role = "planner"  # reuse planner model — it's tuned for structured JSON
    system_prompt = ANALYZER_SYSTEM

    async def analyze(self, scan: dict[str, Any]) -> dict[str, Any]:
        logger.info(f"AnalyzerAgent analysing project '{scan.get('name')}'")
        prompt = (
            "Analyze the following project scan and return the JSON described "
            "by the system prompt. Return ONLY JSON.\n\n"
            + _format_scan_for_prompt(scan)
        )
        raw = await self._generate(prompt, json_mode=True)
        data = extract_json(raw)
        if not isinstance(data, dict):
            logger.warning("Analyzer returned non-object; falling back")
            return {
                "overview": (raw or "").strip()[:2000]
                or "_(model returned no analysis)_",
                "architecture": "",
                "patterns": [],
                "modules": [],
                "todos": [],
                "tech_debt": [],
                "risks": ["Analyzer model returned non-JSON output."],
            }
        # Defensive defaults
        for key, default in (
            ("overview", ""), ("architecture", ""),
            ("patterns", []), ("modules", []),
            ("todos", []), ("tech_debt", []), ("risks", []),
        ):
            data.setdefault(key, default)
        return data

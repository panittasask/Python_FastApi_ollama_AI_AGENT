"""Persistent per-project memory.

Stored under `<project_root>/.agent/`:
    * memory.json          — raw scan + analyzer output + history
    * PROJECT_ANALYSIS.md  — high-level overview
    * ARCHITECTURE.md      — detected architecture / patterns
    * CODEBASE_MAP.md      — file tree + dependency overview
    * TODO_PLAN.md         — actionable items detected/suggested

The folder is intentionally placed inside the analysed project so the
information travels with the codebase (just like .vscode/).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


MEMORY_DIRNAME = ".agent"
MEMORY_FILE = "memory.json"


class ProjectMemory:
    def __init__(self, project_root: str | Path) -> None:
        self.root = Path(project_root).expanduser().resolve()
        self.dir = self.root / MEMORY_DIRNAME

    # ---------------------------------------------------------------- io

    def ensure(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)

    def memory_path(self) -> Path:
        return self.dir / MEMORY_FILE

    def load(self) -> Optional[dict[str, Any]]:
        p = self.memory_path()
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def save(self, scan: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
        self.ensure()
        existing = self.load() or {}
        history = list(existing.get("history") or [])
        # Keep last 10 analyses
        if existing.get("analysis"):
            history.append({
                "at": existing.get("updated_at"),
                "analysis": existing.get("analysis"),
            })
            history = history[-10:]
        payload = {
            "root": str(self.root),
            "name": self.root.name,
            "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "scan": scan,
            "analysis": analysis,
            "history": history,
        }
        self.memory_path().write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._write_markdown(scan, analysis)
        return payload

    # ----------------------------------------------------------- markdown

    def _write_markdown(self, scan: dict[str, Any], analysis: dict[str, Any]) -> None:
        self.ensure()
        name = self.root.name
        overview = analysis.get("overview") or "_(no overview generated)_"
        architecture = analysis.get("architecture") or "_(no architecture summary)_"
        patterns = analysis.get("patterns") or []
        modules = analysis.get("modules") or []
        tech_debt = analysis.get("tech_debt") or []
        todos = analysis.get("todos") or []
        risks = analysis.get("risks") or []

        # ---- PROJECT_ANALYSIS.md
        langs = scan.get("languages") or {}
        frameworks = scan.get("frameworks") or []
        pms = scan.get("package_managers") or []
        analysis_md = [
            f"# Project Analysis — `{name}`",
            "",
            f"_Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z_",
            "",
            "## Overview",
            overview,
            "",
            "## Detected Stack",
            f"- **Frameworks:** {', '.join(frameworks) or '_none detected_'}",
            f"- **Package managers:** {', '.join(pms) or '_none_'}",
            f"- **Languages:** {self._fmt_lang_table(langs)}",
            "",
            "## Stats",
            f"- Files: **{scan.get('total_files', 0)}**",
            f"- Directories: **{scan.get('total_dirs', 0)}**",
            f"- Lines of code: **{scan.get('total_lines', 0):,}**",
            f"- Total bytes: **{scan.get('total_bytes', 0):,}**",
            "",
        ]
        if risks:
            analysis_md += ["## Risks / Open Questions", *[f"- {r}" for r in risks], ""]
        notes = scan.get("notes") or []
        if notes:
            analysis_md += ["## Scanner Notes", *[f"- {n}" for n in notes], ""]
        (self.dir / "PROJECT_ANALYSIS.md").write_text(
            "\n".join(analysis_md), encoding="utf-8")

        # ---- ARCHITECTURE.md
        arch_md = [
            f"# Architecture — `{name}`",
            "",
            architecture,
            "",
        ]
        if patterns:
            arch_md += ["## Coding Patterns", *[f"- {p}" for p in patterns], ""]
        if modules:
            arch_md += ["## Modules"]
            for m in modules:
                if isinstance(m, dict):
                    arch_md.append(
                        f"- **{m.get('name', '?')}** — {m.get('purpose', '')}"
                        + (f"  \n  _files:_ `{', '.join(m.get('files', []))}`"
                           if m.get("files") else "")
                    )
                else:
                    arch_md.append(f"- {m}")
            arch_md.append("")
        (self.dir / "ARCHITECTURE.md").write_text(
            "\n".join(arch_md), encoding="utf-8")

        # ---- CODEBASE_MAP.md
        tree = scan.get("tree") or ""
        configs = scan.get("config_files") or []
        entries = scan.get("entry_points") or []
        deps = scan.get("dependencies") or {}
        map_md = [
            f"# Codebase Map — `{name}`",
            "",
            "## Folder tree",
            "```",
            tree,
            "```",
            "",
            "## Entry points",
            *([f"- `{e}`" for e in entries] or ["_(none detected)_"]),
            "",
            "## Config files",
            *([f"- `{c}`" for c in configs] or ["_(none detected)_"]),
            "",
            "## Dependencies",
        ]
        if deps:
            for k, v in deps.items():
                map_md += [f"### `{k}`", "```", *v[:80], "```", ""]
        else:
            map_md.append("_(none parsed)_")
        (self.dir / "CODEBASE_MAP.md").write_text(
            "\n".join(map_md), encoding="utf-8")

        # ---- TODO_PLAN.md
        comments = scan.get("todo_comments") or []
        todo_md = [
            f"# TODO Plan — `{name}`",
            "",
            "## Suggested tasks",
        ]
        if todos:
            for t in todos:
                if isinstance(t, dict):
                    pri = t.get("priority", "med")
                    title = t.get("title", "(no title)")
                    why = t.get("why", "")
                    files = t.get("files") or []
                    line = f"- [ ] **[{pri.upper()}]** {title}"
                    if why:
                        line += f" — {why}"
                    if files:
                        line += f"  \n  _files:_ `{', '.join(files)}`"
                    todo_md.append(line)
                else:
                    todo_md.append(f"- [ ] {t}")
        else:
            todo_md.append("_(none suggested)_")

        if tech_debt:
            todo_md += ["", "## Technical debt"]
            for d in tech_debt:
                if isinstance(d, dict):
                    todo_md.append(
                        f"- {d.get('title', '?')} — {d.get('detail', '')}"
                    )
                else:
                    todo_md.append(f"- {d}")
        if comments:
            todo_md += ["", "## TODO/FIXME comments found in source"]
            for c in comments[:30]:
                todo_md.append(
                    f"- `{c.get('path', '?')}:{c.get('line', '?')}` "
                    f"**{c.get('tag', '')}** — {c.get('text', '')}"
                )
        (self.dir / "TODO_PLAN.md").write_text(
            "\n".join(todo_md), encoding="utf-8")

    # ----------------------------------------------------------- utils

    @staticmethod
    def _fmt_lang_table(langs: dict[str, int]) -> str:
        if not langs:
            return "_(none)_"
        items = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)
        return ", ".join(f"{k} ({n})" for k, n in items[:10])

    def read_markdown(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for name in ("PROJECT_ANALYSIS.md", "ARCHITECTURE.md",
                     "CODEBASE_MAP.md", "TODO_PLAN.md"):
            p = self.dir / name
            if p.exists():
                try:
                    out[name] = p.read_text(encoding="utf-8")
                except Exception:
                    pass
        return out

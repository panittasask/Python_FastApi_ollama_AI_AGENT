"""Recursive scanner for existing projects.

Produces a structured `ScanResult` that the LLM analyzer can reason about
without needing to read the entire codebase.

Highlights:
    * Skips noise dirs (node_modules, .git, dist, build, __pycache__, venvs, ...).
    * Detects languages from extensions.
    * Detects frameworks/build tools from marker files
      (package.json, pyproject.toml, angular.json, Dockerfile, ...).
    * Parses dependencies from package.json / requirements.txt / pyproject.toml.
    * Builds a depth-capped tree string.
    * Picks "important" sample files (entry points, configs, READMEs)
      whose content is small enough to embed in an LLM prompt.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional


# --------------------------------------------------------------------- config

IGNORE_DIRS: set[str] = {
    "node_modules", ".git", ".hg", ".svn", ".idea", ".vscode",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", "out", ".next", ".nuxt", ".angular", ".cache",
    "venv", ".venv", "env", ".env.d", "site-packages", "target",
    "coverage", ".coverage", ".tox", ".gradle", ".terraform",
    "vendor", "bin", "obj",
}

IGNORE_FILE_SUFFIXES: set[str] = {
    ".pyc", ".pyo", ".class", ".o", ".obj", ".dll", ".so", ".dylib",
    ".exe", ".bin", ".dat", ".db", ".sqlite", ".sqlite3",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".mp3", ".mp4", ".wav", ".mov", ".avi",
    ".ttf", ".otf", ".woff", ".woff2",
    ".lock",  # package-lock.json handled by name
}

LANG_BY_EXT: dict[str, str] = {
    ".py": "python", ".pyi": "python",
    ".ts": "typescript", ".tsx": "tsx",
    ".js": "javascript", ".jsx": "jsx", ".mjs": "javascript", ".cjs": "javascript",
    ".java": "java", ".kt": "kotlin", ".scala": "scala",
    ".cs": "csharp", ".fs": "fsharp", ".vb": "vbnet",
    ".go": "go", ".rs": "rust",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".cc": "cpp",
    ".rb": "ruby", ".php": "php", ".swift": "swift",
    ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss", ".sass": "sass",
    ".vue": "vue", ".svelte": "svelte",
    ".json": "json", ".yml": "yaml", ".yaml": "yaml", ".toml": "toml",
    ".xml": "xml", ".sql": "sql", ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".ps1": "powershell", ".bat": "batch",
    ".md": "markdown", ".rst": "rst",
    ".dockerfile": "dockerfile",
}

# (display_name, kind, marker filename or directory)
FRAMEWORK_MARKERS: list[tuple[str, str, str]] = [
    ("Angular", "frontend", "angular.json"),
    ("Next.js", "frontend", "next.config.js"),
    ("Next.js", "frontend", "next.config.mjs"),
    ("Nuxt", "frontend", "nuxt.config.ts"),
    ("Vite", "build", "vite.config.ts"),
    ("Vite", "build", "vite.config.js"),
    ("React (CRA)", "frontend", "react-scripts"),  # checked in deps
    ("Svelte", "frontend", "svelte.config.js"),
    ("Astro", "frontend", "astro.config.mjs"),
    ("Express", "backend", "express"),
    ("NestJS", "backend", "nest-cli.json"),
    ("FastAPI", "backend", "fastapi"),
    ("Flask", "backend", "flask"),
    ("Django", "backend", "manage.py"),
    ("Spring Boot", "backend", "pom.xml"),
    ("Rails", "backend", "Gemfile"),
    (".NET", "backend", ".csproj"),
    ("Go module", "backend", "go.mod"),
    ("Rust (Cargo)", "backend", "Cargo.toml"),
    ("Docker", "infra", "Dockerfile"),
    ("docker-compose", "infra", "docker-compose.yml"),
    ("docker-compose", "infra", "docker-compose.yaml"),
    ("Kubernetes", "infra", "k8s"),
    ("Terraform", "infra", "main.tf"),
    ("GitHub Actions", "ci", ".github/workflows"),
    ("Nx monorepo", "monorepo", "nx.json"),
    ("Turborepo", "monorepo", "turbo.json"),
    ("pnpm workspace", "monorepo", "pnpm-workspace.yaml"),
]

# Files we always want to capture content from when they exist (capped by size).
PRIORITY_FILENAMES: list[str] = [
    "README.md", "README.rst", "readme.md",
    "package.json", "pnpm-workspace.yaml", "turbo.json", "nx.json",
    "tsconfig.json", "angular.json", "vite.config.ts", "vite.config.js",
    "next.config.js", "next.config.mjs", "nuxt.config.ts",
    "pyproject.toml", "requirements.txt", "Pipfile", "setup.cfg", "setup.py",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
    "composer.json", "Gemfile",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".env.example", "Makefile",
]

PER_FILE_MAX_BYTES = 12_000   # cap each sampled file
TOTAL_SAMPLE_MAX_BYTES = 90_000   # total bytes of sampled content sent to LLM
TREE_MAX_ENTRIES = 600        # safety cap on tree size
TREE_MAX_DEPTH = 6


# --------------------------------------------------------------------- types

@dataclass
class FileSummary:
    path: str            # relative path with forward slashes
    size: int
    lines: int
    language: Optional[str]


@dataclass
class ScanResult:
    root: str
    name: str
    total_files: int
    total_dirs: int
    total_bytes: int
    total_lines: int
    languages: dict[str, int] = field(default_factory=dict)        # lang -> file count
    language_lines: dict[str, int] = field(default_factory=dict)   # lang -> line count
    frameworks: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    todo_comments: list[dict[str, str]] = field(default_factory=list)
    largest_files: list[FileSummary] = field(default_factory=list)
    tree: str = ""
    sample_files: list[dict[str, Any]] = field(default_factory=list)  # {path, content, truncated}
    readme_excerpt: Optional[str] = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "name": self.name,
            "total_files": self.total_files,
            "total_dirs": self.total_dirs,
            "total_bytes": self.total_bytes,
            "total_lines": self.total_lines,
            "languages": self.languages,
            "language_lines": self.language_lines,
            "frameworks": self.frameworks,
            "package_managers": self.package_managers,
            "entry_points": self.entry_points,
            "config_files": self.config_files,
            "dependencies": self.dependencies,
            "todo_comments": self.todo_comments,
            "largest_files": [f.__dict__ for f in self.largest_files],
            "tree": self.tree,
            "sample_files": self.sample_files,
            "readme_excerpt": self.readme_excerpt,
            "notes": self.notes,
        }


# --------------------------------------------------------------------- helpers

def _rel(p: Path, root: Path) -> str:
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.as_posix()


def _detect_lang(p: Path) -> Optional[str]:
    name = p.name.lower()
    if name == "dockerfile" or name.endswith(".dockerfile"):
        return "dockerfile"
    if name == "makefile":
        return "makefile"
    return LANG_BY_EXT.get(p.suffix.lower())


def _is_text(p: Path) -> bool:
    if p.suffix.lower() in IGNORE_FILE_SUFFIXES:
        return False
    if p.name.lower() in {"package-lock.json", "yarn.lock", "poetry.lock", "pnpm-lock.yaml"}:
        return False
    return True


def _read_text_safe(p: Path, max_bytes: int = PER_FILE_MAX_BYTES) -> tuple[str, bool]:
    """Read file as UTF-8, returning (content, truncated). Empty + False on error."""
    try:
        data = p.read_bytes()
    except OSError:
        return "", False
    truncated = False
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated = True
    try:
        return data.decode("utf-8", errors="replace"), truncated
    except Exception:
        return "", False


def _count_lines(p: Path) -> int:
    try:
        with p.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _walk(root: Path) -> Iterable[Path]:
    """Yield every file under root, skipping ignored directories."""
    stack: list[Path] = [root]
    while stack:
        cur = stack.pop()
        try:
            entries = list(cur.iterdir())
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_symlink():
                    continue
                if e.is_dir():
                    if e.name in IGNORE_DIRS or e.name.startswith("."):
                        # allow .github specifically
                        if e.name not in {".github"}:
                            continue
                    stack.append(e)
                elif e.is_file():
                    yield e
            except OSError:
                continue


# -------------------------------------------------------------- dependency parsers

def _parse_package_json(p: Path) -> dict[str, list[str]]:
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    out: dict[str, list[str]] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        block = data.get(key) or {}
        if isinstance(block, dict):
            out[key] = [f"{k}@{v}" for k, v in block.items()]
    if "scripts" in data and isinstance(data["scripts"], dict):
        out["scripts"] = [f"{k}: {v}" for k, v in data["scripts"].items()]
    return out


def _parse_requirements(p: Path) -> list[str]:
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    out: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith("-"):
            continue
        out.append(s)
    return out


def _parse_pyproject(p: Path) -> dict[str, list[str]]:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    # very light TOML-ish parse: pull dependency arrays as raw lines
    out: dict[str, list[str]] = {}
    blocks = re.findall(
        r"(?:dependencies|optional-dependencies\.\w+)\s*=\s*\[(.*?)\]",
        text,
        re.DOTALL,
    )
    deps: list[str] = []
    for blk in blocks:
        for m in re.finditer(r'"([^"]+)"', blk):
            deps.append(m.group(1))
    if deps:
        out["pyproject"] = deps
    return out


# -------------------------------------------------------------- tree builder

def _build_tree(
    root: Path,
    max_entries: int = TREE_MAX_ENTRIES,
    max_depth: int = TREE_MAX_DEPTH,
) -> str:
    lines: list[str] = [f"{root.name}/"]
    count = [0]

    def walk(dir_: Path, prefix: str, depth: int) -> None:
        if depth > max_depth or count[0] >= max_entries:
            return
        try:
            entries = sorted(
                [e for e in dir_.iterdir() if not (e.name in IGNORE_DIRS)],
                key=lambda e: (e.is_file(), e.name.lower()),
            )
        except OSError:
            return
        # filter hidden except .github / .env*
        entries = [
            e for e in entries
            if (not e.name.startswith("."))
            or e.name in {".github", ".env", ".env.example", ".gitignore"}
        ]
        for i, e in enumerate(entries):
            if count[0] >= max_entries:
                lines.append(prefix + "└── … (truncated)")
                return
            last = i == len(entries) - 1
            branch = "└── " if last else "├── "
            lines.append(prefix + branch + e.name + ("/" if e.is_dir() else ""))
            count[0] += 1
            if e.is_dir():
                walk(e, prefix + ("    " if last else "│   "), depth + 1)

    walk(root, "", 1)
    return "\n".join(lines)


# -------------------------------------------------------------- TODO comment scan

_TODO_RE = re.compile(
    r"(?:#|//|/\*|\*|<!--)\s*(TODO|FIXME|HACK|XXX|BUG)\b[: ]?\s*(.{0,160})",
    re.IGNORECASE,
)


def _scan_todos_in(p: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    text, _ = _read_text_safe(p, max_bytes=40_000)
    if not text:
        return out
    for i, ln in enumerate(text.splitlines(), start=1):
        m = _TODO_RE.search(ln)
        if m:
            out.append({"tag": m.group(1).upper(), "text": m.group(2).strip(), "line": str(i)})
            if len(out) >= 5:
                break
    return out


# -------------------------------------------------------------- main

def scan_project(
    root: str | Path,
    *,
    on_progress: Optional[Any] = None,
) -> ScanResult:
    """Walk `root` and produce a `ScanResult`.

    `on_progress(msg: str)` is called occasionally so callers can stream status.
    """
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"not a directory: {root_path}")

    def emit(msg: str) -> None:
        if callable(on_progress):
            try:
                on_progress(msg)
            except Exception:
                pass

    emit(f"scanning {root_path}")

    res = ScanResult(root=str(root_path), name=root_path.name,
                     total_files=0, total_dirs=0, total_bytes=0, total_lines=0)

    all_files: list[Path] = list(_walk(root_path))
    res.total_files = len(all_files)
    emit(f"found {res.total_files} files")

    # Count dirs as a bonus
    seen_dirs: set[Path] = set()
    for f in all_files:
        for parent in f.parents:
            if parent == root_path:
                break
            seen_dirs.add(parent)
    res.total_dirs = len(seen_dirs)

    largest: list[FileSummary] = []
    framework_hits: set[str] = set()
    pms: set[str] = set()
    config_files: list[str] = []
    entry_points: list[str] = []

    for p in all_files:
        try:
            size = p.stat().st_size
        except OSError:
            continue
        res.total_bytes += size
        lang = _detect_lang(p)
        rel = _rel(p, root_path)

        if not _is_text(p):
            continue

        lines = _count_lines(p)
        res.total_lines += lines
        if lang:
            res.languages[lang] = res.languages.get(lang, 0) + 1
            res.language_lines[lang] = res.language_lines.get(lang, 0) + lines

        # framework / build markers
        name_lower = p.name.lower()
        for display, _kind, marker in FRAMEWORK_MARKERS:
            m = marker.lower()
            if name_lower == m or rel.endswith("/" + m) or rel == m:
                framework_hits.add(display)
            elif m.endswith(".csproj") and name_lower.endswith(".csproj"):
                framework_hits.add(display)

        if name_lower in {"package.json"}:
            pms.add("npm/pnpm/yarn")
        elif name_lower in {"requirements.txt", "pyproject.toml", "pipfile", "setup.py"}:
            pms.add("pip/poetry")
        elif name_lower == "cargo.toml":
            pms.add("cargo")
        elif name_lower == "go.mod":
            pms.add("go modules")
        elif name_lower == "pom.xml":
            pms.add("maven")
        elif name_lower in {"build.gradle", "build.gradle.kts"}:
            pms.add("gradle")
        elif name_lower == "composer.json":
            pms.add("composer")
        elif name_lower == "gemfile":
            pms.add("bundler")

        # configs / entry points (heuristic)
        if p.name in PRIORITY_FILENAMES or p.name.lower() in {
            "dockerfile", "makefile",
        }:
            config_files.append(rel)
        if p.name in {"main.py", "app.py", "manage.py", "index.ts", "index.js",
                      "server.ts", "server.js", "main.go", "Program.cs"}:
            entry_points.append(rel)

        # track largest
        if lang:
            largest.append(FileSummary(path=rel, size=size, lines=lines, language=lang))

        # TODO scan (only for source files, capped)
        if lang and lang not in {"json", "yaml", "toml", "markdown", "rst"} and len(res.todo_comments) < 40:
            for t in _scan_todos_in(p):
                t["path"] = rel
                res.todo_comments.append(t)
                if len(res.todo_comments) >= 40:
                    break

    largest.sort(key=lambda f: f.size, reverse=True)
    res.largest_files = largest[:15]
    res.frameworks = sorted(framework_hits)
    res.package_managers = sorted(pms)
    res.config_files = sorted(set(config_files))[:50]
    res.entry_points = sorted(set(entry_points))[:20]

    emit("parsing dependencies")
    deps: dict[str, list[str]] = {}
    for rel in res.config_files:
        p = root_path / rel
        if p.name == "package.json":
            for k, v in _parse_package_json(p).items():
                deps[f"{rel}::{k}"] = v
        elif p.name == "requirements.txt":
            v = _parse_requirements(p)
            if v:
                deps[rel] = v
        elif p.name == "pyproject.toml":
            for k, v in _parse_pyproject(p).items():
                deps[f"{rel}::{k}"] = v
    res.dependencies = deps

    # Detect React via package.json deps even if no react-scripts file.
    for k, v in deps.items():
        if "package.json" in k:
            joined = " ".join(v).lower()
            if "react" in joined and "React" not in res.frameworks:
                res.frameworks.append("React")
            if "next" in joined and "Next.js" not in res.frameworks:
                res.frameworks.append("Next.js")
            if "express" in joined and "Express" not in res.frameworks:
                res.frameworks.append("Express")
            if "fastify" in joined and "Fastify" not in res.frameworks:
                res.frameworks.append("Fastify")

    res.frameworks = sorted(set(res.frameworks))

    emit("building tree")
    res.tree = _build_tree(root_path)

    emit("collecting sample files")
    used = 0
    # priority files first
    priority_paths: list[Path] = []
    for rel in res.config_files + res.entry_points:
        priority_paths.append(root_path / rel)
    # then a few largest source files
    for f in res.largest_files[:8]:
        priority_paths.append(root_path / f.path)

    seen_samples: set[str] = set()
    for p in priority_paths:
        if used >= TOTAL_SAMPLE_MAX_BYTES:
            break
        rel = _rel(p, root_path)
        if rel in seen_samples or not p.exists() or not p.is_file():
            continue
        seen_samples.add(rel)
        remaining = TOTAL_SAMPLE_MAX_BYTES - used
        cap = min(PER_FILE_MAX_BYTES, remaining)
        text, truncated = _read_text_safe(p, max_bytes=cap)
        if not text.strip():
            continue
        used += len(text)
        res.sample_files.append({
            "path": rel,
            "language": _detect_lang(p) or "",
            "content": text,
            "truncated": truncated,
        })

    # README excerpt
    for cand in ("README.md", "readme.md", "README.rst"):
        rp = root_path / cand
        if rp.exists():
            txt, _ = _read_text_safe(rp, max_bytes=8_000)
            if txt.strip():
                res.readme_excerpt = txt
            break

    if not res.frameworks:
        res.notes.append("No common framework markers detected.")
    if res.total_files > 5_000:
        res.notes.append("Large codebase — analysis is based on a sampled subset.")
    if not res.readme_excerpt:
        res.notes.append("No README found at project root.")

    emit("scan complete")
    return res

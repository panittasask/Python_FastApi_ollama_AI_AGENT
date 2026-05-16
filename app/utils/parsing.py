"""Helpers for parsing LLM output: JSON repair and code-block extraction."""
from __future__ import annotations

import json
import re
from typing import Any, Optional


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL | re.IGNORECASE)
_BRACE_OBJ = re.compile(r"\{.*\}", re.DOTALL)
_BRACK_ARR = re.compile(r"\[.*\]", re.DOTALL)


def extract_json(text: str) -> Optional[Any]:
    """Best-effort extract a JSON object/array from an LLM response."""
    if not text:
        return None
    candidates: list[str] = []

    m = _JSON_FENCE.search(text)
    if m:
        candidates.append(m.group(1))

    candidates.append(text)
    obj_m = _BRACE_OBJ.search(text)
    if obj_m:
        candidates.append(obj_m.group(0))
    arr_m = _BRACK_ARR.search(text)
    if arr_m:
        candidates.append(arr_m.group(0))

    for c in candidates:
        c = c.strip()
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            repaired = _repair_json(c)
            if repaired is not None:
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    continue
    return None


def _repair_json(s: str) -> Optional[str]:
    """Apply small fixes commonly seen in LLM JSON output."""
    if not s:
        return None
    fixed = s
    # remove trailing commas before } or ]
    fixed = re.sub(r",(\s*[}\]])", r"\1", fixed)
    # smart quotes -> straight
    fixed = fixed.replace("“", '"').replace("”", '"').replace("’", "'")
    # balance braces minimally
    open_b = fixed.count("{")
    close_b = fixed.count("}")
    if open_b > close_b:
        fixed += "}" * (open_b - close_b)
    open_s = fixed.count("[")
    close_s = fixed.count("]")
    if open_s > close_s:
        fixed += "]" * (open_s - close_s)
    return fixed


_CODE_FENCE = re.compile(
    r"```([\w+.\-/]*)?\s*\n(.*?)```",
    re.DOTALL,
)

_FILE_HEADER = re.compile(
    r"(?:^|\n)(?:#+\s*)?(?:File|Path|FILE|PATH)\s*[:=]\s*[`\"']?([^\n`\"']+)[`\"']?",
    re.IGNORECASE,
)


def extract_code_blocks(text: str) -> list[tuple[str, str, str]]:
    """Return list of (language_or_path_hint, code, preceding_context)."""
    blocks: list[tuple[str, str, str]] = []
    last_end = 0
    for m in _CODE_FENCE.finditer(text):
        hint = (m.group(1) or "").strip()
        code = m.group(2)
        context = text[last_end : m.start()]
        blocks.append((hint, code, context))
        last_end = m.end()
    return blocks


def parse_file_blocks(text: str) -> list[dict[str, str]]:
    """Parse LLM output containing multiple files.

    Recognized formats:
      - "File: path/to/file.py" followed by a fenced code block.
      - Fence info string is treated as the file path if it contains '/' or '.'.

    Returns a list of dicts: {"path": str, "content": str}.
    """
    results: list[dict[str, str]] = []
    for hint, code, context in extract_code_blocks(text):
        path: Optional[str] = None
        if hint and ("/" in hint or "." in hint) and " " not in hint:
            path = hint
        if not path:
            # search the context just above for a File: marker
            tail = context[-400:]
            matches = list(_FILE_HEADER.finditer(tail))
            if matches:
                path = matches[-1].group(1).strip().strip("`\"'")
        if not path:
            continue
        path = path.lstrip("/").replace("\\", "/")
        results.append({"path": path, "content": code})
    return results

"""Native file/folder picker for the local agent UI.

Browsers cannot return absolute filesystem paths (security), so when the user
clicks "Pick folder" in the UI we open a native OS dialog **on the server**
(which, for this dev tool, is the same machine). Implemented with tkinter
from the standard library — no extra deps.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.logging_config import logger


router = APIRouter(prefix="/api/browse", tags=["browse"])


class BrowseRequest(BaseModel):
    kind: Literal["folder", "file"] = "folder"
    title: Optional[str] = None
    initial_dir: Optional[str] = Field(default=None, alias="initialDir")

    class Config:
        populate_by_name = True


class BrowseResponse(BaseModel):
    path: Optional[str] = None
    name: Optional[str] = None
    is_dir: bool = Field(default=False, alias="isDir")
    cancelled: bool = False

    class Config:
        populate_by_name = True


def _pick_blocking(kind: str, title: str, initial_dir: Optional[str]) -> str:
    # Imported lazily so the rest of the app works on systems without tk.
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        # Bring the dialog to the front on Windows/macOS.
        root.attributes("-topmost", True)
    except Exception:  # pragma: no cover
        pass
    try:
        if kind == "folder":
            return filedialog.askdirectory(
                title=title or "Select project folder",
                initialdir=initial_dir or "",
                mustexist=True,
            ) or ""
        return filedialog.askopenfilename(
            title=title or "Select file",
            initialdir=initial_dir or "",
        ) or ""
    finally:
        try:
            root.destroy()
        except Exception:  # pragma: no cover
            pass


@router.post("", response_model=BrowseResponse)
async def browse(req: BrowseRequest) -> BrowseResponse:
    try:
        raw = await asyncio.to_thread(
            _pick_blocking, req.kind, req.title or "", req.initial_dir
        )
    except Exception as e:
        logger.exception("native picker failed")
        raise HTTPException(
            status_code=500,
            detail=(
                "Native file picker unavailable on this server "
                f"({type(e).__name__}: {e}). Please paste the path manually."
            ),
        ) from e

    if not raw:
        return BrowseResponse(cancelled=True)
    p = Path(raw).resolve()
    return BrowseResponse(
        path=str(p),
        name=p.name,
        is_dir=p.is_dir(),
        cancelled=False,
    )

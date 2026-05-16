"""Lightweight DuckDuckGo web search (HTML scrape, no API key, no extra deps).

This is intentionally minimal — we just need top-N {title, url, snippet}
triples to inject as grounding context when the user toggles "web search"
in the chat UI.

If DuckDuckGo changes its HTML layout this scraper may need updating; the
helper degrades gracefully (returns []) on parse failure.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.core.logging_config import logger


DDG_HTML_URL = "https://duckduckgo.com/html/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# DDG result anchor + snippet patterns
_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
    r'.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

    def to_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}


def _clean(text: str) -> str:
    text = _TAG_RE.sub("", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_url(raw: str) -> str:
    """DDG wraps real urls behind /l/?uddg=<encoded>."""
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = "https:" + raw
    try:
        parsed = urlparse(raw)
        if parsed.path.startswith("/l/") or parsed.netloc.endswith("duckduckgo.com"):
            qs = parse_qs(parsed.query)
            for key in ("uddg", "u"):
                if key in qs and qs[key]:
                    return unquote(qs[key][0])
    except Exception:
        pass
    return raw


async def search(query: str, max_results: int = 5,
                 timeout: float = 15.0) -> list[SearchResult]:
    """Return up to `max_results` web results for `query`."""
    q = (query or "").strip()
    if not q:
        return []
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=8.0),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        ) as client:
            resp = await client.post(DDG_HTML_URL, data={"q": q, "kl": "wt-wt"})
            resp.raise_for_status()
            html_text = resp.text
    except httpx.HTTPError as e:
        logger.warning(f"web_search failed: {e}")
        return []

    out: list[SearchResult] = []
    for m in _RESULT_RE.finditer(html_text):
        href = _normalize_url(html.unescape(m.group(1) or ""))
        title = _clean(m.group(2))
        snippet = _clean(m.group(3))
        if not href or not title:
            continue
        out.append(SearchResult(title=title, url=href, snippet=snippet))
        if len(out) >= max_results:
            break
    if not out:
        logger.info("web_search returned no parseable results")
    return out


async def fetch_page_text(url: str, max_chars: int = 4_000,
                          timeout: float = 12.0) -> Optional[str]:
    """Fetch a URL and return a stripped text excerpt (best-effort)."""
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=6.0),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text
    except httpx.HTTPError:
        return None
    # crude HTML -> text
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars] if text else None


def format_results_block(results: list[SearchResult]) -> str:
    """Render search results as a markdown block that can be prepended to a prompt."""
    if not results:
        return ""
    lines = ["### Web search results", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r.title}** — <{r.url}>")
        if r.snippet:
            lines.append(f"   {r.snippet}")
    lines.append("")
    return "\n".join(lines)

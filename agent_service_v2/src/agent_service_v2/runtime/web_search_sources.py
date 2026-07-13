from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def normalize_web_search_sources(value: Any) -> list[dict[str, str]]:
    candidates = value.get("results", []) if isinstance(value, dict) else value
    if not isinstance(candidates, list):
        return []

    sources: list[dict[str, str]] = []
    for item in candidates:
        source = _normalize_source(item)
        if source is None:
            continue
        sources.append(source)
        if len(sources) == 5:
            break
    return sources


def _normalize_source(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    url = str(value.get("url") or "").strip()
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return None
    source = str(value.get("source") or parsed_url.netloc).strip()
    return {
        "title": str(value.get("title") or source).strip(),
        "url": url,
        "snippet": str(
            value.get("snippet") or value.get("description") or ""
        ).strip(),
        "source": source,
        "engine": str(value.get("engine") or "").strip(),
    }

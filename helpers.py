"""
Helper utilities for the Struggle Dynamics module.
"""
import asyncio
import json
import os
import requests
from pathlib import Path
from typing import List, Optional


def save_to_json(data: dict, filepath: str, indent: int = 2) -> None:
    """Save data to a JSON file, creating parent directories as needed."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


async def validate_urls_async(urls: List[str], timeout: int = 5) -> List[str]:
    """Validate all URLs concurrently; return only accessible ones."""
    if not urls:
        return []
    _headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }

    def _check(url: str) -> Optional[str]:
        try:
            r = requests.head(url, timeout=timeout, allow_redirects=True, headers=_headers)
            if r.status_code == 405 or r.status_code >= 400:
                r = requests.get(url, timeout=timeout, allow_redirects=True, headers=_headers, stream=True)
                r.close()
            return url if r.status_code < 400 else None
        except Exception:
            return None

    results = await asyncio.gather(*[asyncio.to_thread(_check, url) for url in urls])
    return [u for u in results if u]


async def sanitize_urls_in_output(data):
    """
    Recursively walk a dict/list structure, find ALL URLs, validate them
    in one batch, then:
      - URL strings → blank ("") if invalid
      - URL lists   → filter out invalid entries

    Call this on final corrected output to guarantee no unvalidated URLs.
    """
    if not data:
        return data

    # Phase 1: Collect every unique URL
    all_urls = set()

    def _collect(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                if isinstance(v, str) and v.startswith(("http://", "https://")):
                    all_urls.add(v)
                elif isinstance(v, (dict, list)):
                    _collect(v)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, str) and item.startswith(("http://", "https://")):
                    all_urls.add(item)
                elif isinstance(item, (dict, list)):
                    _collect(item)

    if isinstance(data, list):
        for item in data:
            _collect(item)
    else:
        _collect(data)

    if not all_urls:
        return data

    # Phase 2: Validate in one batch
    valid_urls = set(await validate_urls_async(list(all_urls)))

    # Phase 3: Walk again — blank invalid strings, filter invalid list entries
    def _sanitize(obj):
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if isinstance(v, str) and v.startswith(("http://", "https://")):
                    if v not in valid_urls:
                        obj[k] = ""
                elif isinstance(v, list):
                    obj[k] = [
                        item for item in v
                        if not (
                            isinstance(item, str)
                            and item.startswith(("http://", "https://"))
                            and item not in valid_urls
                        )
                    ]
                    for item in obj[k]:
                        if isinstance(item, (dict, list)):
                            _sanitize(item)
                elif isinstance(v, dict):
                    _sanitize(v)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    _sanitize(item)

    if isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                _sanitize(item)
    else:
        _sanitize(data)

    return data

from __future__ import annotations

import time
from urllib.parse import urlsplit

import requests


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session


def fetch_html(session: requests.Session, url: str, *, timeout: float, max_retries: int, backoff: float) -> str:
    for attempt in range(max_retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            if (urlsplit(response.url).netloc, urlsplit(response.url).path.rstrip("/")) != (urlsplit(url).netloc, urlsplit(url).path.rstrip("/")):
                raise RuntimeError(f"Redirecionamento inesperado: {url} -> {response.url}")
            response.encoding = "utf-8"
            return response.text
        except requests.RequestException:
            if attempt == max_retries:
                raise
            time.sleep(backoff * (attempt + 1))
    raise AssertionError("Tentativas esgotadas")

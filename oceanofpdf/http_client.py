from __future__ import annotations

import random
import time

import requests


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/143.0.0.0 Safari/537.36"
)


def create_session(user_agent: str = DEFAULT_USER_AGENT) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
            "Connection": "keep-alive",
        }
    )
    return session


def fetch_html(
    session: requests.Session,
    url: str,
    *,
    timeout: float,
    max_retries: int,
    retry_backoff: float,
) -> str:
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(retry_backoff * (attempt + 1))

    raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error


def polite_sleep(min_seconds: float, max_seconds: float) -> None:
    if min_seconds < 0 or max_seconds < 0:
        raise ValueError("sleep interval cannot be negative")
    if max_seconds < min_seconds:
        raise ValueError("max_seconds must be >= min_seconds")
    if max_seconds == 0:
        return
    time.sleep(random.uniform(min_seconds, max_seconds))

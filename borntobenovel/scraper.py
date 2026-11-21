from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .http_client import create_session, fetch_html
from .parser import ParseError, chapter_number, parse_chapter_page


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config_mind_the_gap.json"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict) or int(config["first_chapter"]) > int(config["last_chapter"]):
        raise ValueError("Intervalo de capítulos inválido")
    return config


def configured_urls(config: dict[str, Any]) -> list[str]:
    base = str(config["chapter_base"])
    return [f"{base}{number}" for number in range(int(config["first_chapter"]), int(config["last_chapter"]) + 1)]


def output_path(config: dict[str, Any], key: str) -> Path:
    path = Path(str(config[key]))
    return path if path.is_absolute() else ROOT / path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def validate(config: dict[str, Any], chapters: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    urls = configured_urls(config)
    if chapters is None:
        chapters = _read_json(output_path(config, "output_json"), [])
    if not isinstance(chapters, list):
        raise ValueError("JSON de capítulos inválido")
    collected = [item for item in chapters if isinstance(item, dict)]
    seen: set[str] = set()
    duplicate: list[str] = []
    invalid: list[str] = []
    for item in collected:
        url = str(item.get("url", ""))
        if url in seen:
            duplicate.append(url)
        seen.add(url)
        try:
            number = chapter_number(url)
        except ParseError:
            invalid.append(url)
            continue
        title = str(item.get("title", ""))
        paragraphs = item.get("paragraphs")
        if title.lower() != f"chapter {number}".lower() or not isinstance(paragraphs, list) or not paragraphs or any(not isinstance(p, str) or not p.strip() for p in paragraphs):
            invalid.append(url)
    actual_urls = [item.get("url") for item in collected]
    missing = [url for url in urls if url not in seen]
    unexpected = [url for url in actual_urls if url not in urls]
    order_issue = [url for url, expected in zip(actual_urls, [url for url in urls if url in seen]) if url != expected]
    fingerprints: dict[str, list[str]] = {}
    for item in collected:
        paragraphs = item.get("paragraphs")
        if isinstance(paragraphs, list) and all(isinstance(p, str) for p in paragraphs):
            fingerprint = "\n".join(paragraphs)
            fingerprints.setdefault(fingerprint, []).append(str(item.get("url", "")))
    repeated_content = [group for group in fingerprints.values() if len(group) > 1]
    return {
        "is_valid": not any((missing, unexpected, duplicate, invalid, order_issue, repeated_content)),
        "expected_total": len(urls), "collected_total": len(collected),
        "missing_urls": missing, "unexpected_urls": unexpected,
        "duplicate_urls": duplicate, "invalid_urls": invalid,
        "order_issue_urls": order_issue, "repeated_content": repeated_content,
    }


def collect(config: dict[str, Any]) -> dict[str, Any]:
    urls = configured_urls(config)
    cache_path = output_path(config, "cache_file")
    json_path = output_path(config, "output_json")
    cache = _read_json(cache_path, {"chapters": [], "failed_urls": []})
    if not isinstance(cache, dict):
        raise ValueError("Cache inválido")
    previous = cache.get("chapters") or _read_json(json_path, [])
    chapters = {item["url"]: item for item in previous if isinstance(item, dict) and item.get("url") in urls and item.get("paragraphs")}
    failed = set(cache.get("failed_urls", []))
    session = create_session()
    http = config.get("http", {})
    pending = [url for url in urls if url not in chapters]
    for index, url in enumerate(pending, 1):
        print(f"[BornToBeNovel] {index}/{len(pending)}: {url}", flush=True)
        try:
            html = fetch_html(session, url, timeout=float(http.get("timeout", 30)), max_retries=int(http.get("max_retries", 2)), backoff=float(http.get("retry_backoff_seconds", 2)))
            chapter = parse_chapter_page(html, url)
            chapters[url] = chapter
            failed.discard(url)
        except (Exception) as exc:
            print(f"[BornToBeNovel] Falha: {exc}", flush=True)
            failed.add(url)
        ordered = [chapters[item] for item in urls if item in chapters]
        _write_json(cache_path, {"chapters": ordered, "failed_urls": [item for item in urls if item in failed]})
        _write_json(json_path, ordered)
        if index < len(pending):
            time.sleep(float(config.get("chapter_delay_seconds", 1)))
    report = validate(config, [chapters[item] for item in urls if item in chapters])
    print(f"[BornToBeNovel] Coletados: {report['collected_total']}/{report['expected_total']}", flush=True)
    return report

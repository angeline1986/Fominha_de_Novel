from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .http_client import create_session, fetch_html, polite_sleep
from .models import ChapterRecord, ScrapeSummary
from .parser import build_book_urls, parse_chapter_page
from .storage import atomic_write_json, load_json, write_lines

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config_nocfsb.json"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG
    config = json.loads(config_path.read_text(encoding="utf-8"))

    if not isinstance(config, dict):
        raise ValueError("Config file must contain a JSON object")
    if "volumes" not in config:
        raise ValueError("Config must include a 'volumes' list")
    return config


def filter_uncollected_urls(urls: list[str], cache: dict[str, Any]) -> list[str]:
    completed_urls = set(cache.get("completed_urls", []))
    return [url for url in urls if url not in completed_urls]


def build_pending_urls(urls: list[str], completed_urls: set[str], failed_urls: list[str] | None = None) -> list[str]:
    valid_failed = [url for url in (failed_urls or []) if url in set(urls) and url not in completed_urls]
    remaining = [url for url in urls if url not in completed_urls and url not in set(valid_failed)]
    return valid_failed + remaining


def normalize_chapters(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_numbers: set[int] = set()

    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue

        url = str(chapter.get("url", "")).strip()
        if not url or url in seen_urls:
            continue

        chapter_number = extract_chapter_number(url)
        if chapter_number is not None and chapter_number in seen_numbers:
            continue

        paragraphs = chapter.get("paragraphs", [])
        if not isinstance(paragraphs, list):
            paragraphs = []

        cleaned_paragraphs = [str(p) for p in paragraphs if isinstance(p, str) and str(p).strip()]
        if not cleaned_paragraphs:
            continue

        title = str(chapter.get("title", "")).strip()
        if title in {"", "Salt Society (Novel)", "Capítulo"}:
            continue

        seen_urls.add(url)
        if chapter_number is not None:
            seen_numbers.add(chapter_number)
        valid.append({
            "url": url,
            "title": title,
            "paragraphs": cleaned_paragraphs,
            "source_page": int(chapter.get("source_page", 0) or 0),
            "file_name": str(chapter.get("file_name", "")),
        })

    return valid


def rebuild_cache_from_output(cache_file: str | Path, output_json: str | Path) -> dict[str, list[Any]]:
    default = {"completed_urls": [], "chapters": []}
    cache_path = Path(cache_file)
    output_path = Path(output_json)

    if cache_path.exists() and cache_path.stat().st_size > 0:
        try:
            loaded = load_json(cache_path, default)
            if isinstance(loaded, dict):
                return loaded
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    if not output_path.exists():
        return default

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return default

    if not isinstance(payload, list):
        return default

    chapters = normalize_chapters(payload)
    completed_urls: list[str] = [chapter["url"] for chapter in chapters]
    return {"completed_urls": completed_urls, "chapters": chapters}


def extract_chapter_number(url: str) -> int | None:
    match = re.search(r"/capitulo-([^/]+)/?$", str(url).strip())
    if match is None:
        return None

    token = match.group(1).strip()
    numeric_part = token.split("_", 1)[0]
    if not numeric_part:
        return None

    try:
        return int(numeric_part)
    except ValueError:
        return None


def validate_chapter_collection(config: dict[str, Any], chapters: list[dict[str, Any]] | list[str] | None = None) -> dict[str, Any]:
    expected_urls = build_book_urls(config)
    expected_numbers = []
    seen_expected: set[int] = set()
    for url in expected_urls:
        number = extract_chapter_number(url)
        if number is None or number in seen_expected:
            continue
        expected_numbers.append(number)
        seen_expected.add(number)

    collected_urls: list[str] = []
    if chapters is not None:
        for chapter in chapters:
            if isinstance(chapter, dict):
                url = chapter.get("url")
            elif isinstance(chapter, str):
                url = chapter
            else:
                continue
            if isinstance(url, str) and url.strip():
                collected_urls.append(url.strip())

    if not chapters:
        output_json = resolve_path(Path(__file__).resolve().parents[1], config.get("output_json", "salt-society.json"), "salt-society.json")
        payload = load_json(output_json, [])
        if isinstance(payload, list):
            for chapter in payload:
                if isinstance(chapter, dict) and isinstance(chapter.get("url"), str):
                    collected_urls.append(chapter["url"].strip())

    collected_numbers: list[int] = []
    seen_collected: set[int] = set()
    for url in collected_urls:
        number = extract_chapter_number(url)
        if number is None or number in seen_collected:
            continue
        collected_numbers.append(number)
        seen_collected.add(number)

    missing_numbers = [number for number in expected_numbers if number not in seen_collected]
    extra_numbers = [number for number in collected_numbers if number not in seen_expected]

    ordered_expected_for_collected = [number for number in expected_numbers if number in seen_collected]
    order_issues: list[int] = []
    if collected_numbers != ordered_expected_for_collected:
        for index, number in enumerate(collected_numbers):
            if index >= len(ordered_expected_for_collected):
                order_issues.append(number)
                continue
            expected_number = ordered_expected_for_collected[index]
            if number != expected_number:
                order_issues.append(number)

    sequence_order = not order_issues
    is_valid = not missing_numbers and not extra_numbers and sequence_order
    return {
        "is_valid": is_valid,
        "expected_total": len(expected_numbers),
        "collected_total": len(collected_numbers),
        "missing_numbers": missing_numbers,
        "extra_numbers": extra_numbers,
        "order_issues": order_issues,
        "sequence_order": sequence_order,
        "expected_numbers": expected_numbers,
        "collected_numbers": collected_numbers,
    }


def resolve_path(base_dir: Path, config_value: str, fallback: str) -> Path:
    raw_value = config_value or fallback
    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate
    if str(raw_value).startswith("output/") or str(raw_value).startswith("output\\"):
        return base_dir / candidate
    return base_dir / "output" / candidate


def run_scrape(config: dict[str, Any]) -> ScrapeSummary:
    base_dir = Path(__file__).resolve().parents[1]
    output_dir = base_dir / config.get("output_dir", "output")
    output_json = resolve_path(base_dir, config.get("output_json", "salt-society.json"), "salt-society.json")
    cache_file = resolve_path(base_dir, config.get("cache_file", "output/salt-society_cache.json"), "output/salt-society_cache.json")
    log_file = output_dir / "nocfsb_exec.log"

    if output_dir.exists() is False:
        output_dir.mkdir(parents=True, exist_ok=True)

    cache = load_json(cache_file, {"completed_urls": [], "chapters": [], "failed_urls": []})
    if not isinstance(cache, dict):
        cache = {"completed_urls": [], "chapters": [], "failed_urls": []}

    if not cache.get("completed_urls") and not cache.get("chapters"):
        rebuilt_cache = rebuild_cache_from_output(cache_file, output_json)
        if rebuilt_cache.get("completed_urls") or rebuilt_cache.get("chapters"):
            cache = rebuilt_cache

    cache.setdefault("failed_urls", [])
    cache["chapters"] = normalize_chapters(cache.get("chapters", []))
    cache["completed_urls"] = [chapter["url"] for chapter in cache["chapters"]]

    urls = build_book_urls(config)
    completed_urls = set(cache.get("completed_urls", []))
    failed_urls = list(dict.fromkeys(cache.get("failed_urls", [])))
    chapter_map: dict[str, dict[str, Any]] = {}
    for chapter in cache.get("chapters", []):
        if isinstance(chapter, dict) and isinstance(chapter.get("url"), str):
            chapter_map[chapter["url"]] = chapter
            completed_urls.add(chapter["url"])

    pending_urls = build_pending_urls(urls, completed_urls, failed_urls)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_lines = [f"{timestamp} - [NOCFSB] lendo cache..."]
    if failed_urls:
        log_lines.append(f"{timestamp} - [NOCFSB] {len(failed_urls)} URLs falharam antes e serão reprocessadas primeiro.")
    if completed_urls:
        log_lines.append(f"{timestamp} - [NOCFSB] {len(completed_urls)} capítulos já baixados serão ignorados.")
        log_lines.append(f"{timestamp} - [NOCFSB] {len(pending_urls)} capítulos restantes serão baixados.")
    else:
        log_lines.append(f"{timestamp} - [NOCFSB] nenhum capítulo encontrado em cache; coleta completa iniciada.")

    for url in sorted(completed_urls):
        line = f"{timestamp} - [NOCFSB] ignorado (cache): {url}"
        log_lines.append(line)
        print(line)

    for line in log_lines:
        print(line)

    session = create_session(config.get("http", {}).get("user_agent") or None)
    http_cfg = config.get("http", {})
    timeout = float(http_cfg.get("timeout", 30))
    max_retries = int(http_cfg.get("max_retries", 2))
    retry_backoff = float(http_cfg.get("retry_backoff", 2))
    min_delay = float(config.get("chapter_delay_min_ms", 4000)) / 1000.0
    max_delay = float(config.get("chapter_delay_max_ms", 7000)) / 1000.0

    chapters: list[ChapterRecord] = [
        ChapterRecord(
            url=existing["url"],
            title=existing.get("title", ""),
            paragraphs=existing.get("paragraphs", []),
            source_page=int(existing.get("source_page", 0)),
            file_name=existing.get("file_name", ""),
        )
        for existing in normalize_chapters(list(chapter_map.values()))
    ]

    pending_total = len(pending_urls)
    for index, url in enumerate(pending_urls):
        print(f"[NOCFSB] processando {index + 1}/{pending_total} pendentes -> {url}")
        try:
            html = fetch_html(
                session,
                url,
                timeout=timeout,
                max_retries=max_retries,
                retry_backoff=retry_backoff,
            )
            payload = parse_chapter_page(html, url, source_page=len(chapters) + index)
            chapter = ChapterRecord(
                url=payload["url"],
                title=payload["title"],
                paragraphs=payload["paragraphs"],
                source_page=payload["source_page"],
            )
            if not chapter.paragraphs:
                print(f"[NOCFSB] descartando capítulo sem conteúdo: {url}")
                continue
            chapters.append(chapter)
            chapter_map[url] = chapter.to_dict()
            completed_urls.add(url)
        except Exception as exc:
            print(f"[NOCFSB] falha em {url}: {exc}")
            if url not in failed_urls:
                failed_urls.append(url)
            if url in completed_urls:
                completed_urls.discard(url)

        if index < len(pending_urls) - 1:
            polite_sleep(min_delay, max_delay)

    failed_urls = [url for url in dict.fromkeys(failed_urls) if url not in completed_urls]
    valid_chapters = normalize_chapters([chapter.to_dict() for chapter in chapters])
    for chapter in valid_chapters:
        if chapter["url"] in failed_urls:
            failed_urls.remove(chapter["url"])
    cache_payload = {
        "completed_urls": [chapter["url"] for chapter in valid_chapters],
        "chapters": valid_chapters,
        "failed_urls": failed_urls,
    }
    atomic_write_json(cache_file, cache_payload)
    atomic_write_json(output_json, valid_chapters)
    summary = ScrapeSummary(
        source="nocfsb",
        items_found=len(valid_chapters),
        urls_total=len(urls),
        chapters=[ChapterRecord(**chapter) for chapter in valid_chapters],
    )
    atomic_write_json(output_dir / "salt-society-summary.json", summary.to_dict())

    final_message = (
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - [NOCFSB] extração concluída: {len(valid_chapters)} novos capítulos salvos, "
        f"{len(completed_urls) - len(valid_chapters)} ignorados do cache, total={len(urls)}."
    )
    print(final_message)
    write_lines(log_file, log_lines + [final_message])
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coleta capítulos do site NOCFSB.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Caminho do arquivo JSON de configuração.")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    config = load_config(args.config)
    summary = run_scrape(config)
    print(f"[NOCFSB] extração concluída: {summary.items_found}/{summary.urls_total} capítulos salvos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

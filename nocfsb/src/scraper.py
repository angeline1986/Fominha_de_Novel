from __future__ import annotations

import argparse
import hashlib
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

    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue

        url = str(chapter.get("url", "")).strip()
        if not url or url in seen_urls:
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
    match = re.search(
        r"/(?:capitulo|chapter|spin-off|spin_off|spinoff)[-_]?(\d+)(?:[_\-\.]\d+)?/?$",
        str(url).strip(),
        flags=re.IGNORECASE,
    )
    if match is None:
        return None

    token = match.group(1).strip()
    if not token:
        return None

    try:
        return int(token)
    except ValueError:
        return None


def chapter_key(url: str) -> str:
    """Keep volume identity while treating padded chapter numbers as equivalent."""
    normalized = str(url).strip().rstrip("/")
    match = re.fullmatch(
        r"(.*/)(capitulo|chapter|spin-off|spin_off|spinoff)[-_]?0*(\d+)([_\-.]\d+)?",
        normalized,
        flags=re.IGNORECASE,
    )
    if match is None:
        return normalized
    return f"{match.group(1)}{match.group(2).lower()}-{int(match.group(3))}{match.group(4) or ''}"


def validate_chapter_collection(config: dict[str, Any], chapters: list[dict[str, Any]] | list[str] | None = None) -> dict[str, Any]:
    expected_urls = build_book_urls(config)
    expected_keys = [chapter_key(url) for url in expected_urls]
    expected_set = set(expected_keys)
    expected_numbers = [number for url in expected_urls if (number := extract_chapter_number(url)) is not None]

    collected_urls: list[str] = []
    content_chapters: list[dict[str, Any]] = []
    if chapters is not None:
        for chapter in chapters:
            if isinstance(chapter, dict):
                url = chapter.get("url")
                content_chapters.append(chapter)
            elif isinstance(chapter, str):
                url = chapter
            else:
                continue
            if isinstance(url, str) and url.strip():
                collected_urls.append(url.strip())

    if chapters is None:
        output_json = resolve_path(Path(__file__).resolve().parents[1], config.get("output_json", "salt-society.json"), "salt-society.json")
        payload = load_json(output_json, [])
        if isinstance(payload, list):
            for chapter in payload:
                if isinstance(chapter, dict) and isinstance(chapter.get("url"), str):
                    collected_urls.append(chapter["url"].strip())
                    content_chapters.append(chapter)

    collected_keys = [chapter_key(url) for url in collected_urls]
    collected_set = set(collected_keys)
    missing_urls = [url for url, key in zip(expected_urls, expected_keys) if key not in collected_set]
    extra_urls = [url for url, key in zip(collected_urls, collected_keys) if key not in expected_set]
    seen_collected: set[str] = set()
    duplicate_urls: list[str] = []
    for url, key in zip(collected_urls, collected_keys):
        if key in seen_collected:
            duplicate_urls.append(url)
        seen_collected.add(key)

    recognized = [(url, key) for url, key in zip(collected_urls, collected_keys) if key in expected_set]
    ordered_collected = [key for _, key in recognized]
    ordered_expected = [key for key in expected_keys if key in collected_set]
    order_issue_urls = [
        url for index, (url, key) in enumerate(recognized)
        if index >= len(ordered_expected) or key != ordered_expected[index]
    ] if ordered_collected != ordered_expected else []
    missing_numbers = [number for url in missing_urls if (number := extract_chapter_number(url)) is not None]
    extra_numbers = [number for url in extra_urls if (number := extract_chapter_number(url)) is not None]
    order_issues = [number for url in order_issue_urls if (number := extract_chapter_number(url)) is not None]

    invalid_title_urls: list[str] = []
    invalid_paragraph_urls: list[str] = []
    empty_content_urls: list[str] = []
    content_fingerprints: dict[str, list[str]] = {}
    text_lengths: list[int] = []
    for chapter in content_chapters:
        url = str(chapter.get("url", "")).strip()
        title = chapter.get("title")
        if not isinstance(title, str) or title.strip() in {"", "Capítulo", "Salt Society (Novel)"}:
            invalid_title_urls.append(url)
        paragraphs = chapter.get("paragraphs")
        if not isinstance(paragraphs, list) or any(not isinstance(item, str) for item in paragraphs):
            invalid_paragraph_urls.append(url)
            continue
        cleaned = [" ".join(item.split()) for item in paragraphs if item.strip()]
        if not cleaned:
            empty_content_urls.append(url)
            continue
        text_lengths.append(sum(len(item) for item in cleaned))
        fingerprint = hashlib.sha256("\n".join(cleaned).encode("utf-8")).hexdigest()
        content_fingerprints.setdefault(fingerprint, []).append(url)
    duplicate_content_groups = [group for group in content_fingerprints.values() if len(group) > 1]

    sequence_order = not order_issue_urls
    is_valid = not any((
        missing_urls, extra_urls, duplicate_urls, order_issue_urls,
        invalid_title_urls, invalid_paragraph_urls, empty_content_urls, duplicate_content_groups,
    ))
    return {
        "is_valid": is_valid,
        "expected_total": len(expected_urls),
        "collected_total": len(collected_urls),
        "missing_urls": missing_urls,
        "extra_urls": extra_urls,
        "duplicate_urls": duplicate_urls,
        "order_issue_urls": order_issue_urls,
        "invalid_title_urls": invalid_title_urls,
        "invalid_paragraph_urls": invalid_paragraph_urls,
        "empty_content_urls": empty_content_urls,
        "duplicate_content_groups": duplicate_content_groups,
        "content_checked_total": len(content_chapters),
        "text_length_min": min(text_lengths, default=0),
        "text_length_max": max(text_lengths, default=0),
        "missing_numbers": missing_numbers,
        "extra_numbers": extra_numbers,
        "order_issues": order_issues,
        "sequence_order": sequence_order,
        "expected_numbers": expected_numbers,
        "collected_numbers": [number for url in collected_urls if (number := extract_chapter_number(url)) is not None],
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
    urls = build_book_urls(config)
    expected_urls = set(urls)
    stale_chapters = [chapter for chapter in cache["chapters"] if chapter["url"] not in expected_urls]
    cache["chapters"] = [chapter for chapter in cache["chapters"] if chapter["url"] in expected_urls]
    cache["failed_urls"] = [url for url in cache["failed_urls"] if url in expected_urls]
    cache["completed_urls"] = [chapter["url"] for chapter in cache["chapters"]]

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
    if stale_chapters:
        log_lines.append(f"{timestamp} - [NOCFSB] {len(stale_chapters)} capítulos de URLs fora da configuração atual serão retirados do cache.")
    if failed_urls:
        log_lines.append(f"{timestamp} - [NOCFSB] {len(failed_urls)} URLs falharam antes e serão reprocessadas primeiro.")
    if completed_urls:
        log_lines.append(f"{timestamp} - [NOCFSB] {len(completed_urls)} capítulos já baixados serão ignorados.")
        log_lines.append(f"{timestamp} - [NOCFSB] {len(pending_urls)} capítulos restantes serão baixados.")
    else:
        log_lines.append(f"{timestamp} - [NOCFSB] nenhum capítulo encontrado em cache; coleta completa iniciada.")

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
    initial_count = len(chapters)
    url_order = {url: index for index, url in enumerate(urls)}

    def save_progress() -> list[dict[str, Any]]:
        valid_chapters = normalize_chapters([chapter.to_dict() for chapter in chapters])
        valid_chapters.sort(key=lambda chapter: url_order.get(chapter["url"], len(url_order)))
        unresolved = [url for url in dict.fromkeys(failed_urls) if url not in completed_urls]
        atomic_write_json(cache_file, {
            "completed_urls": [chapter["url"] for chapter in valid_chapters],
            "chapters": valid_chapters,
            "failed_urls": unresolved,
        })
        atomic_write_json(output_json, valid_chapters)
        return valid_chapters

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
            if not normalize_chapters([chapter.to_dict()]):
                print(f"[NOCFSB] descartando capítulo sem conteúdo válido: {url}")
                if url not in failed_urls:
                    failed_urls.append(url)
            else:
                chapters.append(chapter)
                completed_urls.add(url)
        except Exception as exc:
            print(f"[NOCFSB] falha em {url}: {exc}")
            if url not in failed_urls:
                failed_urls.append(url)
            if url in completed_urls:
                completed_urls.discard(url)

        save_progress()
        if index < len(pending_urls) - 1:
            polite_sleep(min_delay, max_delay)

    valid_chapters = save_progress()
    summary = ScrapeSummary(
        source="nocfsb",
        items_found=len(valid_chapters),
        urls_total=len(urls),
        chapters=[ChapterRecord(**chapter) for chapter in valid_chapters],
    )
    atomic_write_json(output_dir / f"{output_json.stem}-summary.json", summary.to_dict())

    final_message = (
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - [NOCFSB] extração concluída: "
        f"{len(valid_chapters) - initial_count} novos capítulos salvos, "
        f"{initial_count} carregados do cache, total={len(valid_chapters)}/{len(urls)}."
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

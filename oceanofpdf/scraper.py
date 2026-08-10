from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .http_client import create_session, fetch_html, polite_sleep
from .models import BookRecord, ScrapeSummary
from .pagination import iter_page_urls
from .parser import parse_category_page
from .storage import atomic_write_json, load_json, write_csv


DEFAULT_CONFIG = Path(__file__).with_name("config_oceanofpdf.json")


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = ["base_url", "category", "start_page", "end_page", "output_json"]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")
    return config


def _record_key(item: BookRecord) -> tuple[str, str, str]:
    return (item.title.casefold(), item.author.casefold(), item.source_url.casefold())


def run_scrape(config: dict[str, Any]) -> ScrapeSummary:
    base_dir = Path(__file__).parent
    start_page = int(config["start_page"])
    end_page = int(config["end_page"])
    timeout = float(config.get("timeout", 30))
    max_retries = int(config.get("max_retries", 2))
    retry_backoff = float(config.get("retry_backoff", 2))
    sleep_min = float(config.get("sleep_min", 1.5))
    sleep_max = float(config.get("sleep_max", 3.5))
    batch_size = int(config.get("batch_size", 25))
    batch_sleep_min = float(config.get("batch_sleep_min", 10))
    batch_sleep_max = float(config.get("batch_sleep_max", 20))
    max_consecutive_errors = int(config.get("max_consecutive_errors", 5))

    if batch_size < 0:
        raise ValueError("batch_size cannot be negative")
    if max_consecutive_errors < 1:
        raise ValueError("max_consecutive_errors must be >= 1")

    output_json = base_dir / config["output_json"]
    output_csv = base_dir / config.get("output_csv", "output/omegaverse.csv")
    cache_file = base_dir / config.get("cache_file", "output/omegaverse_cache.json")

    cache = load_json(cache_file, {"completed_pages": [], "items": []})
    if not isinstance(cache, dict):
        cache = {"completed_pages": [], "items": []}

    completed_pages = {int(p) for p in cache.get("completed_pages", [])}
    existing_items = [BookRecord(**item) for item in cache.get("items", [])]
    items_by_key = {_record_key(item): item for item in existing_items}
    pages_with_errors: list[int] = []
    consecutive_errors = 0
    requests_in_run = 0

    session = create_session(config.get("user_agent") or None) if config.get("user_agent") else create_session()

    for page_number, page_url in iter_page_urls(config["base_url"], start_page, end_page):
        if page_number in completed_pages:
            continue

        requests_in_run += 1

        try:
            html = fetch_html(
                session,
                page_url,
                timeout=timeout,
                max_retries=max_retries,
                retry_backoff=retry_backoff,
            )
            result = parse_category_page(html, page_number=page_number, page_url=page_url)
            if not result.items:
                raise RuntimeError("Page returned no parseable book records")

            for item in result.items:
                items_by_key[_record_key(item)] = item
            completed_pages.add(page_number)
            consecutive_errors = 0

            atomic_write_json(
                cache_file,
                {
                    "completed_pages": sorted(completed_pages),
                    "items": [item.to_dict() for item in items_by_key.values()],
                },
            )
        except Exception as exc:  # keep remaining pages available for a later resume
            pages_with_errors.append(page_number)
            consecutive_errors += 1
            print(f"[ERROR] page={page_number} url={page_url} error={exc}")

            if consecutive_errors >= max_consecutive_errors:
                print(
                    f"[ABORT] reached {consecutive_errors} consecutive errors; "
                    "stopping to avoid repeated requests against a failing endpoint."
                )
                break

        if page_number < end_page:
            polite_sleep(sleep_min, sleep_max)
            if batch_size > 0 and requests_in_run % batch_size == 0:
                print(
                    f"[PAUSE] processed batch of {batch_size} requests; "
                    f"waiting {batch_sleep_min:g}-{batch_sleep_max:g}s."
                )
                polite_sleep(batch_sleep_min, batch_sleep_max)

    items = sorted(
        items_by_key.values(),
        key=lambda item: (item.source_page, item.title.casefold(), item.author.casefold()),
    )
    processed_in_range = len([p for p in completed_pages if start_page <= p <= end_page])
    summary = ScrapeSummary(
        source="oceanofpdf",
        category=str(config["category"]),
        start_page=start_page,
        end_page=end_page,
        pages_processed=processed_in_range,
        items_found=len(items),
        pages_with_errors=sorted(set(pages_with_errors)),
        items=items,
    )

    atomic_write_json(output_json, summary.to_dict())
    write_csv(output_csv, items)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract title, author and genres from OceanOfPDF category pages."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to JSON configuration file.",
    )
    parser.add_argument("--start-page", type=int, help="Override configured first page.")
    parser.add_argument("--end-page", type=int, help="Override configured last page.")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    config = load_config(args.config)
    if args.start_page is not None:
        config["start_page"] = args.start_page
    if args.end_page is not None:
        config["end_page"] = args.end_page

    summary = run_scrape(config)
    print(
        f"Finished: pages={summary.pages_processed} items={summary.items_found} "
        f"errors={len(summary.pages_with_errors)}"
    )
    return 0 if not summary.pages_with_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())

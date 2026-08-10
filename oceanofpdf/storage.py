from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Iterable

from .models import BookRecord


def atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, items: Iterable[BookRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["title", "author", "genres", "source_url", "source_page", "title_raw"],
        )
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "title": item.title,
                    "author": item.author,
                    "genres": ", ".join(item.genres),
                    "source_url": item.source_url,
                    "source_page": item.source_page,
                    "title_raw": item.title_raw or "",
                }
            )
    os.replace(temp_path, path)

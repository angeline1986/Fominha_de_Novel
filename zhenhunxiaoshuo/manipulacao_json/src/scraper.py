import argparse
import csv
import json
from pathlib import Path

from .http_client import HttpClient
from .parser import parse_chapter
from .storage import save_book

MODULE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = MODULE_ROOT.parent / "config_zhenhunxiaoshuo.json"
INPUT_DIR = MODULE_ROOT / "input" / "capitulos"
OUTPUT_DIR = MODULE_ROOT / "output" / "1_extracao"


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _input_csv(config):
    configured = config.get("input_csv")
    if configured:
        candidate = MODULE_ROOT.parent / configured
        if candidate.is_file():
            return candidate
    candidates = sorted(INPUT_DIR.glob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"Nenhum CSV de capítulos encontrado em {INPUT_DIR}")
    preferred = INPUT_DIR / "chapters.csv"
    return preferred if preferred.is_file() else candidates[0]


def load_chapter_rows(csv_path):
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "Título" not in reader.fieldnames or "Link" not in reader.fieldnames:
            raise ValueError("CSV deve conter as colunas 'Título' e 'Link'.")

        rows = []
        for row in reader:
            title = row.get("Título", "").strip()
            url = row.get("Link", "").strip()
            if not url:
                continue
            if "简介" in title:
                print(f"[SKIP] Introdução: {title} -> {url}")
                continue
            rows.append({"title": title, "url": url})
        return rows


def run(limit=None):
    config = load_config()
    rows = load_chapter_rows(_input_csv(config))
    if limit is not None:
        rows = rows[:limit]

    http = config["http"]
    client = HttpClient(
        timeout=http["timeout_seconds"],
        retries=http["retries"],
        delay=http["delay_seconds"],
        user_agent=http["user_agent"],
    )

    chapters = []
    for index, row in enumerate(rows, start=1):
        print(f"[{index}/{len(rows)}] {row['title']} -> {row['url']}")
        page = client.get_text(row["url"])
        chapter = parse_chapter(page, row["url"], row["title"])
        chapters.append(chapter)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    book_id = config["book"]["id"]
    output = OUTPUT_DIR / f"{book_id}.json"
    save_book(chapters, output)
    print(f"\nOK: {len(chapters)} capítulos salvos em {output}")
    return output


def main():
    parser = argparse.ArgumentParser(description="Extrator independente zhenhunxiaoshuo")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run(limit=args.limit)


if __name__ == "__main__":
    main()

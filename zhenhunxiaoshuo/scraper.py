import argparse
import csv
import json
from pathlib import Path

from .http_client import HttpClient
from .parser import parse_chapter
from .storage import save_book

ROOT = Path(__file__).resolve().parent

def load_config():
    return json.loads((ROOT / "config_zhenhunxiaoshuo.json").read_text(encoding="utf-8"))

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
    rows = load_chapter_rows(ROOT / config["input_csv"])
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
        html = client.get_text(row["url"])
        chapter = parse_chapter(html, row["url"], row["title"])
        chapters.append(chapter)
        print(
            f"  título={chapter.chapter_title!r} | "
            f"lead={chapter.chapter_lead!r} | "
            f"parágrafos={chapter.paragraph_count} | "
            f"csv_match={chapter.title_matches_csv}"
        )

    output = ROOT / config["output_dir"] / "di_wang_gong_lue.json"
    save_book(chapters, output)
    print(f"\nOK: {len(chapters)} capítulos salvos em {output}")
    return output

def main():
    parser = argparse.ArgumentParser(description="Extrator independente zhenhunxiaoshuo")
    parser.add_argument("--limit", type=int, default=None, help="Extrair somente os N primeiros registros")
    args = parser.parse_args()
    run(limit=args.limit)

if __name__ == "__main__":
    main()

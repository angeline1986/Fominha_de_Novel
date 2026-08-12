import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .epub.builder import build_epub
from .epub.loader import load_book_from_json
from .epub.validator import validate_epub

ROOT = Path(__file__).resolve().parent


def load_config():
    return json.loads(
        (ROOT / "config_zhenhunxiaoshuo.json").read_text(encoding="utf-8")
    )

def run(*, json_path, title, author="", language="pt-BR",
        cover=None, output=None, identifier=None):
    source = Path(json_path).resolve()

    if cover is None:
        config = load_config()
        candidate = ROOT / config.get("cover_path", "input/assets/cover.jpg")
        if candidate.is_file():
            cover = candidate

    book = load_book_from_json(
        source, title=title, author=author, language=language,
        cover_path=cover, identifier=identifier,
    )

    output_path = (
        Path(output).resolve()
        if output else ROOT / load_config().get("epub_output_dir", "output/epub") / f"{_slugify(title)}.epub"
    )

    build_result = build_epub(book, output_path)
    validation = validate_epub(output_path, len(book.chapters))

    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = reports / f"epub_build_{run_id}.json"
    report_path.write_text(
        json.dumps({
            "run_id": run_id,
            "source_json": str(source),
            "output_epub": str(output_path),
            "book": {
                "title": book.title,
                "author": book.author,
                "language": book.language,
                "chapter_count": len(book.chapters),
                "cover": str(book.cover_path) if book.cover_path else None,
            },
            "build": build_result,
            "validation": validation,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"EPUB: {output_path}")
    print(f"Capítulos: {len(book.chapters)}")
    print(f"Capa: {'sim' if book.cover_path else 'não'}")
    print(f"Validação: {'OK' if validation['valid'] else 'FALHOU'}")
    print(f"Errors: {len(validation['errors'])}")
    print(f"Relatório: {report_path}")

    for error in validation["errors"]:
        print(f"[ERROR] {error}")

    if not validation["valid"]:
        raise SystemExit(2)
    return output_path

def _slugify(value):
    out = []
    for char in value.strip().lower():
        if char.isalnum():
            out.append(char)
        elif char in {" ", "-", "_"}:
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "book"

def main():
    p = argparse.ArgumentParser(
        description="Gera EPUB 3 a partir de um JSON explicitamente informado."
    )
    p.add_argument("--json", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--author", default="")
    p.add_argument("--language", default="pt-BR")
    p.add_argument("--cover", default=None)
    p.add_argument("--output", default=None)
    p.add_argument("--identifier", default=None)
    args = p.parse_args()
    run(
        json_path=args.json, title=args.title, author=args.author,
        language=args.language, cover=args.cover, output=args.output,
        identifier=args.identifier,
    )

if __name__ == "__main__":
    main()

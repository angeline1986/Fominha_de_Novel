from __future__ import annotations

import argparse
import json
from pathlib import Path

from .epub_builder import build_epub
from .scraper import DEFAULT_CONFIG, collect, load_config, output_path, validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coleta capítulos do Born to Be Novel e gera EPUB.")
    parser.add_argument("action", choices=["collect", "validate", "epub", "all"])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.action in {"collect", "all"}:
        report = collect(config)
        if args.action == "collect":
            return 0 if report["is_valid"] else 1
    else:
        report = validate(config)
    if args.action in {"validate", "epub", "all"}:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not report["is_valid"]:
            return 1
    if args.action in {"epub", "all"}:
        chapters = json.loads(output_path(config, "output_json").read_text(encoding="utf-8"))
        print(f"EPUB gerado: {build_epub(config, chapters)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

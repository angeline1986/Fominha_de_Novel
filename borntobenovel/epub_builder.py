from __future__ import annotations

import html
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ebooklib import epub

from .scraper import output_path, validate


def _format_paragraph(text: str) -> str:
    if re.fullmatch(r"\s*\*\s*\*\s*\*\s*", text):
        return "<hr/>"
    safe = html.escape(text, quote=False)
    safe = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", safe)
    return f"<p>{safe}</p>"


def build_epub(config: dict, chapters: list[dict]) -> Path:
    report = validate(config, chapters)
    if not report["is_valid"]:
        raise ValueError(f"Coleta incompleta ou inválida: {report}")
    book_meta = config["book"]
    book = epub.EpubBook()
    book.set_identifier(str(book_meta["id"]))
    book.set_title(str(book_meta["title"]))
    book.set_language(str(book_meta.get("language", "en")))
    if book_meta.get("author"):
        book.add_author(str(book_meta["author"]))
    book.add_metadata("DC", "date", datetime.now(timezone.utc).date().isoformat())
    style = epub.EpubItem(uid="style", file_name="style/book.css", media_type="text/css", content="body { font-family: serif; line-height: 1.5; } h1 { text-align: center; } p { margin: 0.7em 0; text-indent: 1.2em; }")
    book.add_item(style)
    items = []
    for chapter in chapters:
        number = int(re.search(r"/ch-(\d+)/?$", chapter["url"]).group(1))
        item = epub.EpubHtml(title=chapter["title"], file_name=f"chapter-{number}.xhtml", lang=book_meta.get("language", "en"))
        item.add_item(style)
        paragraphs = "\n".join(_format_paragraph(text) for text in chapter["paragraphs"])
        item.content = f"<h1>{html.escape(chapter['title'])}</h1>\n{paragraphs}"
        book.add_item(item)
        items.append(item)
    book.toc = tuple(items)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *items]
    destination = output_path(config, "output_epub")
    destination.parent.mkdir(parents=True, exist_ok=True)
    candidate = destination.with_name(destination.stem + ".candidate.epub")
    epub.write_epub(str(candidate), book)
    with zipfile.ZipFile(candidate) as archive:
        if archive.testzip() is not None or len([name for name in archive.namelist() if re.fullmatch(r"EPUB/chapter-\d+\.xhtml", name)]) != len(chapters):
            raise ValueError("EPUB gerado não passou na verificação de integridade")
    candidate.replace(destination)
    return destination

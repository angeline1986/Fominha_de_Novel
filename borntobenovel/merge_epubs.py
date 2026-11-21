"""Monta um EPUB único com os capítulos 1–76 do EPUB antigo e 77–140 do JSON."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from bs4 import BeautifulSoup
from ebooklib import epub

from .epub_builder import _format_paragraph
from .scraper import load_config, output_path, validate


DEFAULT_OUTPUT = Path(__file__).resolve().parent / "output" / "mind-the-gap-1-140.epub"


def _body(item: epub.EpubHtml, *, remove_ads: bool = False) -> str:
    soup = BeautifulSoup(item.get_content(), "html.parser")
    body = soup.body
    if body is None:
        raise ValueError(f"Arquivo XHTML sem body: {item.file_name}")
    if remove_ads:
        for ad in body.select("div.ad-corner"):
            ad.decompose()
    return "".join(str(child) for child in body.contents)


def merge(first_epub: Path, second_json: Path, output: Path) -> Path:
    config = load_config()
    chapters = json.loads(second_json.read_text(encoding="utf-8"))
    report = validate(config, chapters)
    if not report["is_valid"]:
        raise ValueError(f"Capítulos 77–140 inválidos: {report}")

    source = epub.read_epub(str(first_epub))
    source_title = source.get_metadata("DC", "title")
    title = source_title[0][0] if source_title else "Mind the Gap"
    book = epub.EpubBook()
    book.set_identifier("mind-the-gap-complete-1-140")
    book.set_title(title)
    book.set_language("en")  # O EPUB antigo traz 'ru', mas os 140 capítulos estão em inglês.

    cover = source.get_item_with_href("cover.jpg")
    if cover is not None:
        book.set_cover("cover.jpg", cover.get_content())

    style = source.get_item_with_href("style/nav.css")
    style_text = style.get_content().decode("utf-8") if style else "body { font-family: serif; line-height: 1.5; } h1 { text-align: center; } p { margin: 0.7em 0; }"
    stylesheet = epub.EpubItem(uid="style", file_name="style/book.css", media_type="text/css", content=style_text)
    book.add_item(stylesheet)

    spine = []
    info = source.get_item_with_href("info.xhtml")
    if info is not None:
        info_page = epub.EpubHtml(title="Sobre a obra", file_name="info.xhtml", lang="en")
        info_page.add_item(stylesheet)
        info_page.content = _body(info)
        book.add_item(info_page)
        spine.append(info_page)

    chapter_items = []
    for number in range(1, 77):
        original = source.get_item_with_href(f"chapter_{number:03d}.xhtml")
        if original is None:
            raise ValueError(f"Capítulo {number} ausente no EPUB antigo")
        soup = BeautifulSoup(original.get_content(), "html.parser")
        heading = soup.body.find("h1") if soup.body else None
        if heading is None or heading.get_text(" ", strip=True) != f"Chapter {number}":
            raise ValueError(f"Título inesperado no capítulo {number} do EPUB antigo")
        item = epub.EpubHtml(title=f"Chapter {number}", file_name=f"chapter-{number:03d}.xhtml", lang="en")
        item.add_item(stylesheet)
        item.content = _body(original, remove_ads=True)
        book.add_item(item)
        chapter_items.append(item)

    for chapter in chapters:
        number = int(re.search(r"/ch-(\d+)/?$", chapter["url"]).group(1))
        item = epub.EpubHtml(title=chapter["title"], file_name=f"chapter-{number:03d}.xhtml", lang="en")
        item.add_item(stylesheet)
        body = "\n".join(_format_paragraph(text) for text in chapter["paragraphs"])
        item.content = f"<h1>{chapter['title']}</h1>\n{body}"
        book.add_item(item)
        chapter_items.append(item)

    book.toc = tuple(chapter_items)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *spine, *chapter_items]

    output.parent.mkdir(parents=True, exist_ok=True)
    candidate = output.with_name(output.stem + ".candidate.epub")
    epub.write_epub(str(candidate), book)
    with zipfile.ZipFile(candidate) as archive:
        if archive.testzip() is not None:
            raise ValueError("Falha de integridade no ZIP do EPUB")
        names = archive.namelist()
        actual = {int(match.group(1)) for name in names if (match := re.fullmatch(r"EPUB/chapter-(\d{3})\.xhtml", name))}
        if actual != set(range(1, 141)):
            raise ValueError("Capítulos ausentes ou fora do intervalo no EPUB")
        for name in names:
            if name.endswith(".xhtml"):
                ElementTree.fromstring(archive.read(name))
        if not {"EPUB/nav.xhtml", "EPUB/toc.ncx", "EPUB/cover.jpg"}.issubset(names):
            raise ValueError("Índice ou capa ausente no EPUB")
    candidate.replace(output)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Junta os capítulos 1–76 e 77–140 em um EPUB.")
    parser.add_argument("first_epub", type=Path, help="EPUB original com os capítulos 1–76")
    parser.add_argument("--json", type=Path, default=output_path(load_config(), "output_json"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    print(merge(args.first_epub, args.json, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import html
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from .storage import ensure_dir, write_text


def _safe_title(value: str) -> str:
    return html.escape(value, quote=False)


def chapter_volume_number(chapter: dict[str, Any]) -> int | None:
    url = chapter.get("url") if isinstance(chapter, dict) else ""
    if not isinstance(url, str):
        return None
    match = re.search(r"/volume[-_]?0?(\d+)", url, flags=re.IGNORECASE)
    if match is None:
        return None
    return int(match.group(1))


def chapter_display_title(chapter: dict[str, Any]) -> str:
    title = str(chapter.get("title") or "Capítulo").strip() or "Capítulo"
    title = re.sub(r"^(?:[—\-–:]+\s*)+", "", title)
    volume_number = chapter_volume_number(chapter)

    if volume_number is None:
        return title

    volume_label = f"Volume {volume_number}"
    if title.lower().startswith(volume_label.lower()):
        return title
    return f"{volume_label} — {title}"


def build_volume_sections(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for chapter in chapters:
        chapter_data = chapter.to_dict() if hasattr(chapter, "to_dict") else dict(chapter)
        volume_number = chapter_data.get("volume_number")
        if volume_number is None:
            volume_number = chapter_volume_number(chapter_data)
        if volume_number is None:
            volume_number = 0
        grouped.setdefault(int(volume_number), []).append(chapter_data)

    sections: list[dict[str, Any]] = []
    for volume_number in sorted(grouped.keys()):
        sections.append({
            "volume_number": volume_number,
            "title": f"Volume {volume_number}" if volume_number else "Capítulos avulsos",
            "chapters": grouped[volume_number],
        })
    return sections


def generate_cover_xhtml(oebps_dir: Path) -> None:
    content = '''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
  <head>
    <title>Cover</title>
    <style type="text/css">
      @page { margin: 0; padding: 0; }
      body { margin: 0; padding: 0; text-align: center; }
      img { max-width: 100%; height: auto; }
    </style>
  </head>
  <body>
    <img src="images/cover.jpg" alt="cover"/>
  </body>
</html>
'''
    write_text(oebps_dir / "cover.xhtml", content)


def generate_title_page(oebps_dir: Path, config: dict[str, Any]) -> None:
    book = config.get("book", {})
    title = book.get("title", "Salt Society")
    author = book.get("author", "Salt Society")
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title>{_safe_title(title)}</title>
    <link href="stylesheet.css" rel="stylesheet" type="text/css"/>
  </head>
  <body class="titlepage">
    <h1>{_safe_title(title)}</h1>
    <h2>por { _safe_title(author) }</h2>
  </body>
</html>
'''
    write_text(oebps_dir / "title_page.xhtml", content)


def generate_stylesheet(oebps_dir: Path) -> None:
    css = '''body { font-family: serif; line-height: 1.6; margin: 1.5em; }
h1, h2, h3 { text-align: center; }
p { text-indent: 1.5em; margin: 0.5em 0; }
.separator { text-align: center; text-indent: 0; }
'''
    write_text(oebps_dir / "stylesheet.css", css)


def _is_redundant_chapter_heading(paragraph: str, title: str) -> bool:
    """Detect a standalone copy of the chapter number, never narrative text."""
    title_match = re.search(r"\bcap[ií]tulo\s*0*(\d+)\b", title, re.IGNORECASE)
    if title_match is None:
        return False

    # Source pages sometimes prefix the heading with arrows or dashes.
    heading_match = re.fullmatch(
        r"[\s\ufeff\u200b-\u200d\u2060\u2190-\u21ff\u2500-\u257f\u27f0-\u27ff—–\-:]*"
        r"cap[ií]tulo\s*0*(\d+)"
        r"[\s\ufeff\u200b-\u200d\u2060\u2190-\u21ff\u2500-\u257f\u27f0-\u27ff—–\-:]*",
        str(paragraph),
        re.IGNORECASE,
    )
    return heading_match is not None and int(heading_match.group(1)) == int(title_match.group(1))


def generate_chapter_xhtml(oebps_dir: Path, chapter: dict[str, Any], index: int) -> str:
    filename = f"file{index + 1:04d}.xhtml"
    title = chapter_display_title(chapter)
    safe_title = _safe_title(title)
    source_paragraphs = list(chapter.get("paragraphs", []))
    # Remove only the first nonempty paragraph when it repeats this chapter's
    # number exactly. Do not edit the source dictionary, JSON, or cache.
    first_content_index = next(
        (i for i, value in enumerate(source_paragraphs) if str(value).strip()), None
    )
    if first_content_index is not None and _is_redundant_chapter_heading(
        str(source_paragraphs[first_content_index]), title
    ):
        source_paragraphs.pop(first_content_index)

    paragraphs = []
    for paragraph in source_paragraphs:
        text = html.escape(str(paragraph), quote=False)
        paragraphs.append(f"<p>{text}</p>")
    body = "\n".join(paragraphs) if paragraphs else "<p>Capítulo sem conteúdo.</p>"
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title>{safe_title}</title>
    <link href="stylesheet.css" rel="stylesheet" type="text/css"/>
  </head>
  <body>
    <h3>{safe_title}</h3>
    {body}
  </body>
</html>
'''
    write_text(oebps_dir / filename, content)
    return filename


def _toc_chapter_title(chapter: dict[str, Any]) -> str:
    """Remove the redundant volume prefix only from navigation labels."""
    title = str(chapter["title"])
    number = chapter.get("volume_number")
    if number:
        title = re.sub(rf"^Volume\s+0?{int(number)}\s+[—–-]\s*", "", title, flags=re.IGNORECASE)
    return title


def generate_nav(oebps_dir: Path, sections: list[dict[str, Any]]) -> None:
    items = []
    for section in sections:
        chapters = section["chapters"]
        if not chapters:
            continue
        first_file = chapters[0]["file_name"]
        chapter_items = "\n".join(
            f'<li><a href="{chapter["file_name"]}">{_safe_title(_toc_chapter_title(chapter))}</a></li>'
            for chapter in chapters
        )
        items.append(
            f'<li><a href="{first_file}">{_safe_title(section["title"])}</a>\n'
            f'<ol>\n{chapter_items}\n</ol></li>'
        )
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <head>
    <title>Índice</title>
    <link href="stylesheet.css" rel="stylesheet" type="text/css"/>
  </head>
  <body>
    <nav epub:type="toc" id="toc">
      <h2>Índice</h2>
      <ol>
        <li><a href="title_page.xhtml">Página de Título</a></li>
        {"".join(items)}
      </ol>
    </nav>
  </body>
</html>
'''
    write_text(oebps_dir / "nav.xhtml", content)


def generate_ncx(oebps_dir: Path, sections: list[dict[str, Any]], config: dict[str, Any]) -> None:
    book = config.get("book", {})
    title = book.get("title", "Salt Society")
    book_id = book.get("id", "salt-society")
    items = []
    play_order = 2  # title page is first
    for index, section in enumerate(sections, start=1):
        chapters = section["chapters"]
        if not chapters:
            continue
        first_file = chapters[0]["file_name"]
        children = []
        section_order = play_order
        play_order += 1
        for chapter_index, chapter in enumerate(chapters, start=1):
            children.append(
                f'<navPoint id="vol{index}-chap{chapter_index}" playOrder="{play_order}">'
                f'<navLabel><text>{_safe_title(_toc_chapter_title(chapter))}</text></navLabel>'
                f'<content src="{chapter["file_name"]}"/></navPoint>'
            )
            play_order += 1
        items.append(
            f'<navPoint id="vol{index}" playOrder="{section_order}">'
            f'<navLabel><text>{_safe_title(section["title"])}</text></navLabel>'
            f'<content src="{first_file}"/>{"".join(children)}</navPoint>'
        )
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{book_id}"/>
    <meta name="dtb:depth" content="2"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{_safe_title(title)}</text></docTitle>
  <navMap>
    <navPoint id="title" playOrder="1">
      <navLabel><text>Página de Título</text></navLabel>
      <content src="title_page.xhtml"/>
    </navPoint>
    {"".join(items)}
  </navMap>
</ncx>
'''
    write_text(oebps_dir / "toc.ncx", content)


def generate_opf(oebps_dir: Path, chapters: list[dict[str, Any]], config: dict[str, Any], has_cover: bool) -> None:
    book = config.get("book", {})
    items = "\n".join(
        f'<item id="chap{index + 1}" href="{chapter["file_name"]}" media-type="application/xhtml+xml"/>'
        for index, chapter in enumerate(chapters)
    )
    spine = "\n".join(
        f'<itemref idref="chap{index + 1}"/>'
        for index in range(len(chapters))
    )
    cover_item = '<item id="cover-image" href="images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>' if has_cover else ""
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">
    <dc:identifier id="bookid">{book.get("id", "salt-society")}</dc:identifier>
    <dc:title>{_safe_title(book.get("title", "Salt Society"))}</dc:title>
    <dc:creator>{_safe_title(book.get("author", "Salt Society"))}</dc:creator>
    <dc:language>{book.get("language", "pt-BR")}</dc:language>
    <meta property="dcterms:modified">{__import__('datetime').datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}</meta>
  </metadata>
  <manifest>
    <item id="title_page" href="title_page.xhtml" media-type="application/xhtml+xml"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="css" href="stylesheet.css" media-type="text/css"/>
    {cover_item}
    {items}
  </manifest>
  <spine toc="ncx">
    <itemref idref="title_page"/>
    {spine}
  </spine>
</package>
'''
    write_text(oebps_dir / "content.opf", content)


def generate_container(meta_dir: Path) -> None:
    content = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
'''
    write_text(meta_dir / "container.xml", content)


def build_epub(chapters: list[dict[str, Any]], config: dict[str, Any]) -> Path:
    base_dir = Path(__file__).resolve().parents[1]
    work_dir = base_dir / "build_epub"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    meta_dir = ensure_dir(work_dir / "META-INF")
    oebps_dir = ensure_dir(work_dir / "OEBPS")
    images_dir = ensure_dir(oebps_dir / "images")

    cover_file = base_dir / config.get("cover_source", "cover.jpg")
    has_cover = cover_file.exists()
    if has_cover:
        shutil.copy2(cover_file, images_dir / "cover.jpg")
        generate_cover_xhtml(oebps_dir)

    generate_title_page(oebps_dir, config)
    generate_stylesheet(oebps_dir)
    generate_container(meta_dir)

    chapter_entries: list[dict[str, Any]] = []
    for index, chapter in enumerate(chapters):
        chapter_dict = chapter.to_dict() if hasattr(chapter, "to_dict") else chapter
        chapter_dict["title"] = chapter_display_title(chapter_dict)
        file_name = generate_chapter_xhtml(oebps_dir, chapter_dict, index)
        chapter_entries.append({
            "title": chapter_dict.get("title", f"Capítulo {index + 1}"),
            "file_name": file_name,
            "url": chapter_dict.get("url", ""),
            "volume_number": chapter_dict.get("volume_number") if chapter_dict.get("volume_number") is not None else chapter_volume_number(chapter_dict),
        })

    sections = build_volume_sections(chapter_entries)
    generate_nav(oebps_dir, sections)
    generate_ncx(oebps_dir, sections, config)
    generate_opf(oebps_dir, chapter_entries, config, has_cover)

    output_path = base_dir / config.get("output_epub", "output/salt-society.epub")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for path in sorted(work_dir.rglob("*")):
            if path.is_file() and path.name != "mimetype":
                arcname = path.relative_to(work_dir)
                zf.write(path, arcname.as_posix())

    return output_path

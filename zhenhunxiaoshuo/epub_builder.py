import html
import json
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_config():
    return json.loads((ROOT / "config_zhenhunxiaoshuo.json").read_text(encoding="utf-8"))


def chapter_xhtml(chapter, index, language):
    title = html.escape(chapter.get("chapter_title") or chapter.get("csv_title") or f"Capítulo {index}")
    lead = html.escape(chapter.get("chapter_lead") or "")
    paragraphs = chapter.get("paragraphs") or []

    body = []
    if lead:
        body.append(f'<p class="chapter-lead">{lead}</p>')
    for paragraph in paragraphs:
        body.append(f"<p>{html.escape(str(paragraph))}</p>")

    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{html.escape(language)}">\n'
        '<head>\n'
        '  <meta charset="utf-8"/>\n'
        f'  <title>{title}</title>\n'
        '  <link rel="stylesheet" type="text/css" href="../Styles/book.css"/>\n'
        '</head>\n'
        '<body>\n'
        f'  <h1>{title}</h1>\n'
        f'  {"".join(body)}\n'
        '</body>\n'
        '</html>'
    )


def nav_xhtml(book_title, chapters, language):
    links = []
    for i, chapter in enumerate(chapters, start=1):
        title = html.escape(chapter.get("chapter_title") or chapter.get("csv_title") or f"Capítulo {i}")
        links.append(f'<li><a href="Text/chapter_{i:03d}.xhtml">{title}</a></li>')

    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops" '
        f'xml:lang="{html.escape(language)}">\n'
        '<head><meta charset="utf-8"/><title>Sumário</title></head>\n'
        '<body><nav epub:type="toc" id="toc">\n'
        f'<h1>{html.escape(book_title)}</h1><ol>{"".join(links)}</ol>\n'
        '</nav></body></html>'
    )


def toc_ncx(book_title, uid, chapters):
    points = []
    for i, chapter in enumerate(chapters, start=1):
        title = html.escape(chapter.get("chapter_title") or chapter.get("csv_title") or f"Capítulo {i}")
        points.append(
            f'<navPoint id="navPoint-{i}" playOrder="{i}">'
            f'<navLabel><text>{title}</text></navLabel>'
            f'<content src="Text/chapter_{i:03d}.xhtml"/>'
            f'</navPoint>'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
        f'<head><meta name="dtb:uid" content="{uid}"/></head>\n'
        f'<docTitle><text>{html.escape(book_title)}</text></docTitle>\n'
        f'<navMap>{"".join(points)}</navMap>\n'
        '</ncx>'
    )


def content_opf(book_title, author, language, uid, chapters):
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="css" href="Styles/book.css" media-type="text/css"/>',
    ]
    spine = []

    for i in range(1, len(chapters) + 1):
        manifest.append(
            f'<item id="chapter_{i:03d}" href="Text/chapter_{i:03d}.xhtml" '
            'media-type="application/xhtml+xml"/>'
        )
        spine.append(f'<itemref idref="chapter_{i:03d}"/>')

    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'<dc:identifier id="bookid">{uid}</dc:identifier>\n'
        f'<dc:title>{html.escape(book_title)}</dc:title>\n'
        f'<dc:creator>{html.escape(author)}</dc:creator>\n'
        f'<dc:language>{html.escape(language)}</dc:language>\n'
        f'<meta property="dcterms:modified">{modified}</meta>\n'
        '</metadata>\n'
        f'<manifest>{"".join(manifest)}</manifest>\n'
        f'<spine toc="ncx">{"".join(spine)}</spine>\n'
        '</package>'
    )


def build_epub(json_path, output_path=None):
    config = load_config()
    book = config["book"]

    json_path = Path(json_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    chapters = data.get("chapters") or []

    if not chapters:
        raise ValueError("O JSON não contém capítulos.")

    output_path = Path(output_path) if output_path else (
        ROOT / config["output_dir"] / "epub" / f"{book['id']}.epub"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    uid = f"urn:uuid:{uuid.uuid4()}"
    container_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles>\n'
        '</container>'
    )
    css = (
        'body { font-family: serif; line-height: 1.6; margin: 5%; }\n'
        'h1 { text-align: center; margin-bottom: 1.5em; }\n'
        'p { text-indent: 2em; margin: 0.7em 0; }\n'
        '.chapter-lead { text-indent: 0; font-weight: bold; }\n'
    )

    with zipfile.ZipFile(output_path, "w") as zf:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, "application/epub+zip")

        zf.writestr("META-INF/container.xml", container_xml, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr(
            "OEBPS/content.opf",
            content_opf(book["title"], book["author"], book["language"], uid, chapters),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        zf.writestr(
            "OEBPS/nav.xhtml",
            nav_xhtml(book["title"], chapters, book["language"]),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        zf.writestr(
            "OEBPS/toc.ncx",
            toc_ncx(book["title"], uid, chapters),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        zf.writestr("OEBPS/Styles/book.css", css, compress_type=zipfile.ZIP_DEFLATED)

        for i, chapter in enumerate(chapters, start=1):
            zf.writestr(
                f"OEBPS/Text/chapter_{i:03d}.xhtml",
                chapter_xhtml(chapter, i, book["language"]),
                compress_type=zipfile.ZIP_DEFLATED,
            )

    return output_path

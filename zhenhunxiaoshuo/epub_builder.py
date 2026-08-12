import html
import json
import mimetypes
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODE_STANDARD = "standard"
MODE_NO_REDUNDANCY = "no_redundancy"


def load_config():
    return json.loads(
        (ROOT / "config_zhenhunxiaoshuo.json").read_text(encoding="utf-8")
    )


def _cover_candidates(config):
    candidates = []

    book_cover = config.get("book", {}).get("cover")
    if isinstance(book_cover, str) and book_cover.strip():
        candidates.append(ROOT / book_cover.strip())

    top_cover = config.get("cover_image")
    if isinstance(top_cover, str) and top_cover.strip():
        candidates.append(ROOT / top_cover.strip())

    cover_cfg = config.get("cover")
    if isinstance(cover_cfg, dict):
        path = cover_cfg.get("path")
        if isinstance(path, str) and path.strip():
            candidates.append(ROOT / path.strip())

    for name in (
        "cover.jpg", "cover.jpeg", "cover.png",
        "capa.jpg", "capa.jpeg", "capa.png",
    ):
        candidates.append(ROOT / "input" / name)

    for folder in ("input", "input/assets"):
        for name in (
            "cover.jpg",
            "cover.jpeg",
            "cover.png",
            "capa.jpg",
            "capa.jpeg",
            "capa.png",
        ):
            candidates.append(ROOT / folder / name)

    seen = set()
    unique = []
    for path in candidates:
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def find_cover(config):
    for path in _cover_candidates(config):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            return path
    return None


def _cover_media_type(path):
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _split_lead(lead):
    """Retorna (titulo, frase) somente para formatos reconhecidos com segurança."""
    text = (lead or "").strip()
    patterns = (
        r"^【\s*(?P<title>[^】]+?)\s*】\s*(?P<phrase>.+?)\s*$",
        r"^\[\s*(?P<title>[^\]]+?)\s*\]\s*(?P<phrase>.+?)\s*$",
    )
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.DOTALL)
        if match:
            title = match.group("title").strip()
            phrase = match.group("phrase").strip()
            if title and phrase:
                return title, phrase
    return None, None


def _chapter_presentation(chapter, index, mode):
    chapter_title = (
        chapter.get("chapter_title")
        or chapter.get("csv_title")
        or f"Capítulo {index}"
    )
    lead = (chapter.get("chapter_lead") or "").strip()

    if mode == MODE_NO_REDUNDANCY:
        lead_title, phrase = _split_lead(lead)
        if lead_title and phrase:
            return lead_title, phrase, True

    return chapter_title, lead, False


def _chapter_xhtml(chapter, index, language, mode):
    visual_title, epigraph, transformed = _chapter_presentation(chapter, index, mode)
    title = html.escape(str(visual_title))
    paragraphs = chapter.get("paragraphs") or []

    body = []
    if epigraph:
        if mode == MODE_NO_REDUNDANCY and transformed:
            body.append(
                '<p class="chapter-epigraph">“'
                + html.escape(str(epigraph))
                + '”</p>'
            )
        else:
            body.append(
                '<p class="chapter-lead">'
                + html.escape(str(epigraph))
                + '</p>'
            )

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


def _cover_xhtml(book_title, cover_filename, language):
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{html.escape(language)}">\n'
        '<head><meta charset="utf-8"/><title>Capa</title>'
        '<link rel="stylesheet" type="text/css" href="Styles/book.css"/></head>\n'
        '<body class="cover-page">\n'
        f'<div class="cover"><img src="Images/{html.escape(cover_filename)}" '
        f'alt="{html.escape(book_title)}"/></div>\n'
        '</body></html>'
    )


def _nav_xhtml(book_title, chapters, language, mode):
    links = []
    for i, chapter in enumerate(chapters, start=1):
        visual_title, _, _ = _chapter_presentation(chapter, i, mode)
        links.append(
            f'<li><a href="Text/chapter_{i:03d}.xhtml">'
            f'{html.escape(str(visual_title))}</a></li>'
        )

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


def _toc_ncx(book_title, uid, chapters, mode):
    points = []
    for i, chapter in enumerate(chapters, start=1):
        visual_title, _, _ = _chapter_presentation(chapter, i, mode)
        points.append(
            f'<navPoint id="navPoint-{i}" playOrder="{i}">'
            f'<navLabel><text>{html.escape(str(visual_title))}</text></navLabel>'
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


def _content_opf(book_title, author, language, uid, chapters, cover_info=None):
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="css" href="Styles/book.css" media-type="text/css"/>',
    ]
    spine = []
    metadata_extra = []

    if cover_info:
        cover_filename, cover_media = cover_info
        manifest.extend([
            f'<item id="cover-image" href="Images/{html.escape(cover_filename)}" '
            f'media-type="{html.escape(cover_media)}" properties="cover-image"/>',
            '<item id="cover-page" href="cover.xhtml" media-type="application/xhtml+xml"/>',
        ])
        metadata_extra.append('<meta name="cover" content="cover-image"/>')
        spine.append('<itemref idref="cover-page"/>')

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
        f'{"".join(metadata_extra)}\n'
        '</metadata>\n'
        f'<manifest>{"".join(manifest)}</manifest>\n'
        f'<spine toc="ncx">{"".join(spine)}</spine>\n'
        '</package>'
    )


def _output_path(config, mode):
    book_id = str(config["book"].get("id", "book")).strip() or "book"
    filename = (
        f"{book_id}.epub"
        if mode == MODE_STANDARD
        else f"{book_id}_sem_redundancia.epub"
    )
    return ROOT / config["output_dir"] / "epub" / filename


def build_epub(json_path, output_path=None, mode=MODE_STANDARD):
    if mode not in {MODE_STANDARD, MODE_NO_REDUNDANCY}:
        raise ValueError(f"Modo de EPUB inválido: {mode}")

    config = load_config()
    book = config["book"]
    book_title = str(book.get("title", "Sem título")).strip()
    author = str(book.get("author", "")).strip()
    language = str(book.get("language", "zh-CN")).strip() or "zh-CN"

    json_path = Path(json_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    chapters = data.get("chapters") or []
    if not chapters:
        raise ValueError("O JSON não contém capítulos.")

    output_path = Path(output_path) if output_path else _output_path(config, mode)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cover_path = find_cover(config)
    cover_info = None
    cover_filename = None
    if cover_path:
        suffix = ".jpg" if cover_path.suffix.lower() in {".jpg", ".jpeg"} else ".png"
        cover_filename = f"cover{suffix}"
        cover_info = (cover_filename, _cover_media_type(cover_path))

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
        'h1 { text-align: center; margin: 0 0 1.5em 0; }\n'
        'p { text-indent: 2em; margin: 0.7em 0; }\n'
        '.chapter-lead { text-indent: 0; font-weight: bold; margin-bottom: 2em; }\n'
        '.chapter-epigraph { text-indent: 0; font-style: italic; text-align: center; '
        'margin: 1em 8% 3em 8%; }\n'
        '.cover-page { margin: 0; padding: 0; text-align: center; }\n'
        '.cover { margin: 0; padding: 0; text-align: center; }\n'
        '.cover img { display: block; max-width: 100%; max-height: 100vh; margin: 0 auto; }\n'
    )

    with zipfile.ZipFile(output_path, "w") as zf:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, "application/epub+zip")

        zf.writestr("META-INF/container.xml", container_xml, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr(
            "OEBPS/content.opf",
            _content_opf(book_title, author, language, uid, chapters, cover_info),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        zf.writestr(
            "OEBPS/nav.xhtml",
            _nav_xhtml(book_title, chapters, language, mode),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        zf.writestr(
            "OEBPS/toc.ncx",
            _toc_ncx(book_title, uid, chapters, mode),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        zf.writestr("OEBPS/Styles/book.css", css, compress_type=zipfile.ZIP_DEFLATED)

        if cover_path:
            zf.writestr(
                f"OEBPS/Images/{cover_filename}",
                cover_path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
            )
            zf.writestr(
                "OEBPS/cover.xhtml",
                _cover_xhtml(book_title, cover_filename, language),
                compress_type=zipfile.ZIP_DEFLATED,
            )

        for i, chapter in enumerate(chapters, start=1):
            zf.writestr(
                f"OEBPS/Text/chapter_{i:03d}.xhtml",
                _chapter_xhtml(chapter, i, language, mode),
                compress_type=zipfile.ZIP_DEFLATED,
            )

    return output_path

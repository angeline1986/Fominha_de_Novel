import html
import mimetypes
import uuid
import zipfile
from pathlib import Path

def build_epub(book, output_path):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    identifier = book.identifier or f"urn:uuid:{uuid.uuid4()}"
    cover = _cover_info(book.cover_path)

    with zipfile.ZipFile(output, "w") as epub:
        epub.writestr("mimetype", "application/epub+zip",
                      compress_type=zipfile.ZIP_STORED)
        _write(epub, "META-INF/container.xml", _container())
        _write(epub, "OEBPS/styles/book.css", _css())
        _write(epub, "OEBPS/nav.xhtml", _nav(book))
        _write(epub, "OEBPS/toc.ncx", _ncx(book, identifier))

        if cover:
            epub.writestr(
                f"OEBPS/images/{cover['filename']}",
                book.cover_path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
            )
            _write(epub, "OEBPS/cover.xhtml", _cover_xhtml(book, cover))

        for chapter in book.chapters:
            _write(epub, f"OEBPS/text/{chapter.filename}",
                   _chapter_xhtml(book, chapter))

        _write(epub, "OEBPS/content.opf", _opf(book, identifier, cover))

    return {
        "output": str(output),
        "identifier": identifier,
        "chapter_count": len(book.chapters),
        "cover_included": bool(cover),
    }

def _write(epub, name, text):
    epub.writestr(name, text.encode("utf-8"),
                  compress_type=zipfile.ZIP_DEFLATED)

def _chapter_xhtml(book, chapter):
    title = html.escape(chapter.title)
    intro = (
        f'    <p class="chapter-intro">{html.escape(chapter.intro)}</p>\n'
        if chapter.intro else ""
    )
    body = "\n".join(
        f"    <p>{html.escape(p)}</p>" for p in chapter.paragraphs
    )
    lang = html.escape(book.language)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}">
<head><meta charset="UTF-8"/><title>{title}</title>
<link rel="stylesheet" type="text/css" href="../styles/book.css"/></head>
<body><section class="chapter">
    <h1>{title}</h1>
{intro}{body}
</section></body></html>
'''

def _nav(book):
    lis = "\n".join(
        f'      <li><a href="text/{c.filename}">{html.escape(c.title)}</a></li>'
        for c in book.chapters
    )
    cover = '      <li><a href="cover.xhtml">Capa</a></li>\n' if book.cover_path else ""
    lang = html.escape(book.language)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
 xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}">
<head><meta charset="UTF-8"/><title>Sumário</title></head>
<body><nav epub:type="toc" id="toc"><h1>Sumário</h1><ol>
{cover}{lis}
</ol></nav></body></html>
'''

def _ncx(book, identifier):
    points = []
    order = 1
    if book.cover_path:
        points.append(
            f'<navPoint id="cover" playOrder="{order}"><navLabel><text>Capa</text></navLabel>'
            '<content src="cover.xhtml"/></navPoint>'
        )
        order += 1
    for c in book.chapters:
        points.append(
            f'<navPoint id="chapter_{c.index:03d}" playOrder="{order}">'
            f'<navLabel><text>{html.escape(c.title)}</text></navLabel>'
            f'<content src="text/{c.filename}"/></navPoint>'
        )
        order += 1
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head><meta name="dtb:uid" content="{html.escape(identifier)}"/></head>
<docTitle><text>{html.escape(book.title)}</text></docTitle>
<navMap>{''.join(points)}</navMap></ncx>
'''

def _opf(book, identifier, cover):
    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="css" href="styles/book.css" media-type="text/css"/>',
    ]
    spine = []
    if cover:
        manifest += [
            f'<item id="cover-image" href="images/{html.escape(cover["filename"])}" '
            f'media-type="{html.escape(cover["media_type"])}" properties="cover-image"/>',
            '<item id="cover-page" href="cover.xhtml" media-type="application/xhtml+xml"/>',
        ]
        spine.append('<itemref idref="cover-page"/>')

    for c in book.chapters:
        cid = f"chapter_{c.index:03d}"
        manifest.append(
            f'<item id="{cid}" href="text/{c.filename}" media-type="application/xhtml+xml"/>'
        )
        spine.append(f'<itemref idref="{cid}"/>')

    creator = (
        f"<dc:creator>{html.escape(book.author)}</dc:creator>"
        if book.author else ""
    )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
 unique-identifier="book-id" xml:lang="{html.escape(book.language)}">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="book-id">{html.escape(identifier)}</dc:identifier>
<dc:title>{html.escape(book.title)}</dc:title>{creator}
<dc:language>{html.escape(book.language)}</dc:language>
<meta property="dcterms:modified">2026-08-12T00:00:00Z</meta>
</metadata>
<manifest>{''.join(manifest)}</manifest>
<spine toc="ncx">{''.join(spine)}</spine>
</package>
'''

def _cover_info(path):
    if path is None:
        return None
    media, _ = mimetypes.guess_type(path.name)
    if media not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        raise ValueError(f"Formato de capa não suportado: {path.name}")
    return {"filename": path.name, "media_type": media}

def _cover_xhtml(book, cover):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
 xmlns:epub="http://www.idpf.org/2007/ops">
<head><meta charset="UTF-8"/><title>Capa</title>
<link rel="stylesheet" type="text/css" href="styles/book.css"/></head>
<body><section epub:type="cover" class="cover">
<img src="images/{html.escape(cover["filename"])}"
 alt="Capa de {html.escape(book.title)}"/></section></body></html>
'''

def _container():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf"
 media-type="application/oebps-package+xml"/></rootfiles></container>
'''

def _css():
    return '''body{font-family:serif;line-height:1.55;margin:5%}
h1{font-size:1.45em;margin:0 0 1em}
.chapter-intro{font-style:italic;margin:0 0 1.5em}
p{margin:0 0 .85em;text-align:justify}
.cover{text-align:center;margin:0;padding:0}
.cover img{max-width:100%;max-height:100%}
'''

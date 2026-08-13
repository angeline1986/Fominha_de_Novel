import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

def validate_epub(epub_path, expected_chapters):
    path = Path(epub_path)
    errors = []
    if not path.is_file():
        return {"valid": False, "errors": [f"EPUB não encontrado: {path}"], "warnings": []}

    try:
        with zipfile.ZipFile(path) as epub:
            infos = epub.infolist()
            names = [x.filename for x in infos]

            if not infos or infos[0].filename != "mimetype":
                errors.append("mimetype não é a primeira entrada.")
            elif infos[0].compress_type != zipfile.ZIP_STORED:
                errors.append("mimetype está comprimido.")

            for name in [
                "mimetype", "META-INF/container.xml", "OEBPS/content.opf",
                "OEBPS/nav.xhtml", "OEBPS/toc.ncx", "OEBPS/styles/book.css"
            ]:
                if name not in names:
                    errors.append(f"Arquivo obrigatório ausente: {name}")

            chapters = sorted(
                n for n in names
                if re.fullmatch(r"OEBPS/text/chapter_\d{3}\.xhtml", n)
            )
            if len(chapters) != expected_chapters:
                errors.append(f"XHTMLs={len(chapters)}; esperado={expected_chapters}.")

            for name in [
                "META-INF/container.xml", "OEBPS/content.opf",
                "OEBPS/nav.xhtml", "OEBPS/toc.ncx", *chapters
            ]:
                if name in names:
                    try:
                        ET.fromstring(epub.read(name))
                    except ET.ParseError as exc:
                        errors.append(f"XML inválido em {name}: {exc}")

            if "OEBPS/content.opf" in names:
                opf = epub.read("OEBPS/content.opf").decode("utf-8")
                manifest = len(re.findall(r'id="chapter_\d{3}"[^>]+application/xhtml\+xml', opf))
                spine = len(re.findall(r'<itemref idref="chapter_\d{3}"', opf))
                if manifest != expected_chapters:
                    errors.append(f"Manifest={manifest}; esperado={expected_chapters}.")
                if spine != expected_chapters:
                    errors.append(f"Spine={spine}; esperado={expected_chapters}.")

            if "OEBPS/nav.xhtml" in names:
                nav = epub.read("OEBPS/nav.xhtml").decode("utf-8")
                count = len(re.findall(r'href="text/chapter_\d{3}\.xhtml"', nav))
                if count != expected_chapters:
                    errors.append(f"NAV={count}; esperado={expected_chapters}.")

            if "OEBPS/toc.ncx" in names:
                ncx = epub.read("OEBPS/toc.ncx").decode("utf-8")
                count = len(re.findall(r'src="text/chapter_\d{3}\.xhtml"', ncx))
                if count != expected_chapters:
                    errors.append(f"NCX={count}; esperado={expected_chapters}.")

    except zipfile.BadZipFile:
        errors.append("Arquivo não é ZIP/EPUB válido.")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": [],
        "chapter_count": expected_chapters,
    }

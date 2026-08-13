import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from zhenhunxiaoshuo.producao_epub.src.title_corrector import (
    StructuralMatchError,
    _read_title_csv,
    correct_epub_titles,
    validate_structural_match,
)


def _chapter_xhtml(title, text):
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n'
        f"<head><title>{title}</title></head>\n"
        f"<body><h1>{title}</h1><p>{text}</p></body>\n"
        "</html>"
    )


def _write_epub(path, chapters):
    manifest_items = []
    spine_items = []
    nav_items = []
    ncx_items = []

    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles>'
            "</container>",
        )

        for index, (filename, title) in enumerate(chapters, start=1):
            item_id = f"chapter_{index:03d}"
            href = f"text/{filename}"
            manifest_items.append(
                f'<item id="{item_id}" href="{href}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{item_id}"/>')
            nav_items.append(f'<li><a href="{href}">{title}</a></li>')
            ncx_items.append(
                f'<navPoint id="navPoint-{index}" playOrder="{index}">'
                f"<navLabel><text>{title}</text></navLabel>"
                f'<content src="{href}"/></navPoint>'
            )
            archive.writestr(
                f"OEBPS/{href}",
                _chapter_xhtml(title, f"Texto {index}"),
            )

        archive.writestr(
            "OEBPS/nav.xhtml",
            '<html xmlns="http://www.w3.org/1999/xhtml">'
            '<body><nav><ol>'
            + "".join(nav_items)
            + "</ol></nav></body></html>",
        )
        archive.writestr(
            "OEBPS/toc.ncx",
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/">'
            "<navMap>"
            + "".join(ncx_items)
            + "</navMap></ncx>",
        )
        archive.writestr(
            "OEBPS/content.opf",
            '<package xmlns="http://www.idpf.org/2007/opf">'
            "<manifest>"
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
            + "".join(manifest_items)
            + "</manifest><spine>"
            + "".join(spine_items)
            + "</spine></package>",
        )


class TitleCorrectorTests(unittest.TestCase):

    def test_semicolon_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "titles.csv"
            path.write_text(
                "Capítulo;Título no DOCX;Título no EPUB;Comparação\n"
                "151;Som maligno;Som Demoníaco;DIFERENTE\n",
                encoding="utf-8",
            )

            data = _read_title_csv(path)

        self.assertEqual(data["delimiter"], ";")
        self.assertEqual(
            data["chapter_titles"][151],
            "Som maligno",
        )

    def test_validates_one_to_one_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.epub"
            translated = root / "translated.epub"
            chapters = [
                ("chapter_001.xhtml", "第一章-王城命案"),
                ("chapter_002.xhtml", "第二章-九玄机"),
            ]
            _write_epub(original, chapters)
            _write_epub(translated, chapters)

            result = validate_structural_match(original, translated)

        self.assertEqual(result["chapter_count"], 2)

    def test_aborts_when_translated_structure_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.epub"
            translated = root / "translated.epub"
            _write_epub(original, [
                ("chapter_001.xhtml", "第一章-王城命案"),
                ("chapter_002.xhtml", "第二章-九玄机"),
            ])
            _write_epub(translated, [
                ("chapter_001.xhtml", "Capítulo 1"),
            ])

            with self.assertRaises(StructuralMatchError):
                validate_structural_match(original, translated)

    def test_corrects_titles_without_reordering_spine(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.epub"
            translated = root / "translated.epub"
            csv_path = root / "comparacao_capitulos.csv"
            _write_epub(original, [
                ("chapter_001.xhtml", "第一章-王城命案"),
                ("chapter_002.xhtml", "第二章-九玄机"),
            ])
            _write_epub(translated, [
                ("chapter_001.xhtml", "Old 1"),
                ("chapter_002.xhtml", "Old 2"),
            ])
            csv_path.write_text(
                "Capítulo;Título no DOCX;Título no EPUB;Comparação\n"
                "1;O assassinato na Cidade Imperial;Old 1;DIFERENTE\n"
                "2;Torre Nove Mistérios;Old 2;DIFERENTE\n",
                encoding="utf-8",
            )

            result = correct_epub_titles(original, translated, csv_path)

            with zipfile.ZipFile(result["output"]) as archive:
                chapter = archive.read(
                    "OEBPS/text/chapter_001.xhtml"
                ).decode("utf-8")
                opf = archive.read("OEBPS/content.opf").decode("utf-8")
                nav = archive.read("OEBPS/nav.xhtml").decode("utf-8")

        self.assertIn(
            "<h1>Capítulo 1 - O assassinato na Cidade Imperial</h1>",
            chapter,
        )
        self.assertIn(
            '<itemref idref="chapter_001"/><itemref idref="chapter_002"/>',
            opf,
        )
        self.assertIn("Capítulo 1 - O assassinato na Cidade Imperial", nav)
        self.assertTrue(result["spine_preserved"])


if __name__ == "__main__":
    unittest.main()

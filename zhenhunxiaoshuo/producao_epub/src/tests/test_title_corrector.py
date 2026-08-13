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

    def test_uses_csv_order_instead_of_original_chapter_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.epub"
            translated = root / "translated.epub"
            csv_path = root / "comparacao_capitulos.csv"
            _write_epub(original, [
                ("chapter_024.xhtml", "第二十五章魏紫衣"),
                ("chapter_025.xhtml", "第二十五章-归来庄"),
            ])
            _write_epub(translated, [
                ("chapter_024.xhtml", "Capítulo Vinte e Cinco: Wei Ziyi"),
                ("chapter_025.xhtml", "Capítulo Vinte e Cinco - Retorno à Vila"),
            ])
            csv_path.write_text(
                "Capítulo;Título no DOCX;Título no EPUB;Comparação\n"
                "24;Wei Ziyi;Wei Ziyi;IGUAL\n"
                "25;Gui Lai;Retorno à Vila;DIFERENTE\n",
                encoding="utf-8",
            )

            result = correct_epub_titles(original, translated, csv_path)

            with zipfile.ZipFile(result["output"]) as archive:
                chapter_24 = archive.read(
                    "OEBPS/text/chapter_024.xhtml"
                ).decode("utf-8")
                chapter_25 = archive.read(
                    "OEBPS/text/chapter_025.xhtml"
                ).decode("utf-8")

        self.assertIn("<h1>Capítulo 24 - Wei Ziyi</h1>", chapter_24)
        self.assertIn("<h1>Capítulo 25 - Gui Lai</h1>", chapter_25)

    def test_accepts_complete_csv_catalog_for_partial_epub(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.epub"
            translated = root / "translated.epub"
            csv_path = root / "comparacao_capitulos.csv"
            selected = {
                24: ("Wei Ziyi", "Wei Ziyi"),
                25: ("Gui Lai", "Retorno à Vila"),
                129: ("Expedição", "Um Encontro Fortuito"),
                144: ("Miragem", "Miragem"),
                151: ("Som maligno", "Som Demoníaco"),
            }
            rows = ["Capítulo;Título no DOCX;Título no EPUB;Comparação\n"]
            for number in range(1, 202):
                docx_title, epub_title = selected.get(
                    number,
                    ("", f"Catálogo {number}"),
                )
                rows.append(f"{number};{docx_title};{epub_title};DIFERENTE\n")
            csv_path.write_text("".join(rows), encoding="utf-8")
            _write_epub(original, [
                ("chapter_001.xhtml", "第二十五章魏紫衣"),
                ("chapter_002.xhtml", "第二十五章-归来庄"),
                ("chapter_003.xhtml", "第一百二十九章-出征"),
                ("chapter_004.xhtml", "第一百四十四章-蜃影"),
                ("chapter_005.xhtml", "第一百五十一章-魔音"),
            ])
            _write_epub(translated, [
                ("chapter_001.xhtml", "Capítulo Vinte e Quatro: Wei Ziyi"),
                ("chapter_002.xhtml", "Capítulo Vinte e Cinco - Retorno à Vila"),
                ("chapter_003.xhtml", "Capítulo 128 - Um Encontro Fortuito"),
                ("chapter_004.xhtml", "Capítulo 144 - Miragem"),
                ("chapter_005.xhtml", "Capítulo 151 - Som Demoníaco"),
            ])

            result = correct_epub_titles(original, translated, csv_path)

            with zipfile.ZipFile(result["output"]) as archive:
                titles = [
                    archive.read(f"OEBPS/text/chapter_{index:03d}.xhtml").decode(
                        "utf-8"
                    )
                    for index in range(1, 6)
                ]

        self.assertEqual(result["titles_in_csv"], 201)
        self.assertEqual(result["mapped_entries"], 5)
        self.assertIn("<h1>Capítulo 24 - Wei Ziyi</h1>", titles[0])
        self.assertIn("<h1>Capítulo 25 - Gui Lai</h1>", titles[1])
        self.assertIn("<h1>Capítulo 129 - Expedição</h1>", titles[2])
        self.assertIn("<h1>Capítulo 144 - Miragem</h1>", titles[3])
        self.assertIn("<h1>Capítulo 151 - Som maligno</h1>", titles[4])

    def test_aborts_on_gross_csv_anchor_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.epub"
            translated = root / "translated.epub"
            csv_path = root / "comparacao_capitulos.csv"
            _write_epub(original, [
                ("chapter_001.xhtml", "第一章-王城命案"),
            ])
            _write_epub(translated, [
                ("chapter_001.xhtml", "Capítulo 1 - Retorno à Vila"),
            ])
            csv_path.write_text(
                "Capítulo;Título no DOCX;Título no EPUB;Comparação\n"
                "1;Wei Ziyi;Wei Ziyi;IGUAL\n",
                encoding="utf-8",
            )

            with self.assertRaises(StructuralMatchError):
                correct_epub_titles(original, translated, csv_path)

    def test_allows_minor_csv_anchor_variation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.epub"
            translated = root / "translated.epub"
            csv_path = root / "comparacao_capitulos.csv"
            _write_epub(original, [
                ("chapter_001.xhtml", "第九十六章-大战前夕"),
            ])
            _write_epub(translated, [
                ("chapter_001.xhtml", "96 - Na véspera da Grande Guerra"),
            ])
            csv_path.write_text(
                "Capítulo;Título no DOCX;Título no EPUB;Comparação\n"
                "1;Véspera da Grande Guerra;Véspera da Grande Guerra;DIFERENTE\n",
                encoding="utf-8",
            )

            result = correct_epub_titles(original, translated, csv_path)

        self.assertEqual(result["corrected_count"], 1)

    def test_preserves_current_title_when_docx_title_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.epub"
            translated = root / "translated.epub"
            csv_path = root / "comparacao_capitulos.csv"
            _write_epub(original, [
                ("chapter_001.xhtml", "番外"),
            ])
            _write_epub(translated, [
                ("chapter_001.xhtml", "Capítulo 154 [520 Capítulo Extra] Juventude"),
            ])
            csv_path.write_text(
                "Capítulo;Título no DOCX;Título no EPUB;Comparação\n"
                "154;;[520 Capítulo Extra] Juventude;DIFERENTE\n",
                encoding="utf-8",
            )

            result = correct_epub_titles(original, translated, csv_path)

            with zipfile.ZipFile(result["output"]) as archive:
                chapter = archive.read(
                    "OEBPS/text/chapter_001.xhtml"
                ).decode("utf-8")

        self.assertEqual(result["corrected_count"], 0)
        self.assertIn(
            "<h1>Capítulo 154 [520 Capítulo Extra] Juventude</h1>",
            chapter,
        )

    def test_aborts_on_ambiguous_catalog_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.epub"
            translated = root / "translated.epub"
            csv_path = root / "comparacao_capitulos.csv"
            _write_epub(original, [
                ("chapter_001.xhtml", "第一章-王城命案"),
            ])
            _write_epub(translated, [
                ("chapter_001.xhtml", "Alfa Beta Gamma"),
            ])
            csv_path.write_text(
                "Capítulo;Título no DOCX;Título no EPUB;Comparação\n"
                "1;Um;Alfa Beta;DIFERENTE\n"
                "2;Dois;Beta Gamma;DIFERENTE\n",
                encoding="utf-8",
            )

            with self.assertRaises(StructuralMatchError):
                correct_epub_titles(original, translated, csv_path)

    def test_aborts_when_catalog_match_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.epub"
            translated = root / "translated.epub"
            csv_path = root / "comparacao_capitulos.csv"
            _write_epub(original, [
                ("chapter_001.xhtml", "第一章-王城命案"),
            ])
            _write_epub(translated, [
                ("chapter_001.xhtml", "Capítulo 1 - Inexistente"),
            ])
            csv_path.write_text(
                "Capítulo;Título no DOCX;Título no EPUB;Comparação\n"
                "1;Um;Outro título;DIFERENTE\n",
                encoding="utf-8",
            )

            with self.assertRaises(StructuralMatchError):
                correct_epub_titles(original, translated, csv_path)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from zhenhunxiaoshuo.producao_epub.src.epub.builder import build_epub
from zhenhunxiaoshuo.producao_epub.src.epub.loader import load_book_from_json
from zhenhunxiaoshuo.producao_epub.src.epub.validator import validate_epub

class EpubBuilderTests(unittest.TestCase):
    def test_builds_valid_epub(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "book.json"
            source.write_text(json.dumps({
                "chapter_count": 2,
                "chapters": [
                    {"chapter_title": "Capítulo 1", "chapter_lead": "Intro 1",
                     "paragraphs": ["Texto 1."]},
                    {"chapter_title": "Capítulo 2", "chapter_lead": "",
                     "paragraphs": ["Texto 2."]}
                ]
            }, ensure_ascii=False), encoding="utf-8")

            book = load_book_from_json(source, title="Livro")
            output = root / "book.epub"
            build_epub(book, output)
            result = validate_epub(output, 2)
            self.assertTrue(result["valid"], result["errors"])

            with zipfile.ZipFile(output) as epub:
                infos = epub.infolist()
                self.assertEqual("mimetype", infos[0].filename)
                self.assertEqual(zipfile.ZIP_STORED, infos[0].compress_type)
                chapter = epub.read("OEBPS/text/chapter_001.xhtml").decode("utf-8")
                self.assertIn("<h1>Capítulo 1</h1>", chapter)
                self.assertIn("Intro 1", chapter)
                self.assertIn("Texto 1.", chapter)

    def test_prefers_approved_epub_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "approved.json"
            source.write_text(json.dumps({
                "chapter_count": 1,
                "chapters": [{
                    "chapter_title": "Título bruto",
                    "chapter_lead": "Lead bruto",
                    "paragraphs": ["Texto bruto"],
                    "epub_title": "Título aprovado",
                    "epub_intro": "Intro aprovada",
                    "epub_paragraphs": ["Texto aprovado"]
                }]
            }, ensure_ascii=False), encoding="utf-8")

            book = load_book_from_json(source, title="Livro")
            self.assertEqual("Título aprovado", book.chapters[0].title)
            self.assertEqual("Intro aprovada", book.chapters[0].intro)
            self.assertEqual(["Texto aprovado"], book.chapters[0].paragraphs)

if __name__ == "__main__":
    unittest.main()

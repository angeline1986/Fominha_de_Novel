import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from zhenhunxiaoshuo.producao_epub.src import epub_builder

class EpubBuilderTests(unittest.TestCase):
    def test_builds_valid_epub(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "book": {
                    "id": "livro",
                    "title": "Livro",
                    "author": "",
                    "language": "pt-BR",
                }
            }
            (root / "config_zhenhunxiaoshuo.json").write_text(
                json.dumps(config, ensure_ascii=False), encoding="utf-8"
            )
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

            output = root / "book.epub"
            with patch.object(epub_builder, "PROJECT_ROOT", root):
                result = epub_builder.build_epub(source, output_path=output)
            self.assertEqual(output, result)

            with zipfile.ZipFile(output) as epub:
                infos = epub.infolist()
                self.assertEqual("mimetype", infos[0].filename)
                self.assertEqual(zipfile.ZIP_STORED, infos[0].compress_type)
                names = set(epub.namelist())
                self.assertIn("OEBPS/Styles/book.css", names)
                self.assertIn("OEBPS/Text/chapter_001.xhtml", names)
                self.assertIn("OEBPS/Text/chapter_002.xhtml", names)
                chapter = epub.read("OEBPS/Text/chapter_001.xhtml").decode("utf-8")
                self.assertIn("<h1>Capítulo 1</h1>", chapter)
                self.assertIn("Intro 1", chapter)
                self.assertIn("Texto 1.", chapter)

    def test_uses_current_chapter_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "book": {
                    "id": "livro",
                    "title": "Livro",
                    "author": "",
                    "language": "pt-BR",
                }
            }
            (root / "config_zhenhunxiaoshuo.json").write_text(
                json.dumps(config, ensure_ascii=False), encoding="utf-8"
            )
            source = root / "current.json"
            source.write_text(json.dumps({
                "chapter_count": 1,
                "chapters": [{
                    "chapter_title": "Título atual",
                    "chapter_lead": "Lead atual",
                    "paragraphs": ["Texto atual"]
                }]
            }, ensure_ascii=False), encoding="utf-8")

            output = root / "current.epub"
            with patch.object(epub_builder, "PROJECT_ROOT", root):
                epub_builder.build_epub(source, output_path=output)

            with zipfile.ZipFile(output) as epub:
                chapter = epub.read("OEBPS/Text/chapter_001.xhtml").decode("utf-8")
                self.assertIn("<h1>Título atual</h1>", chapter)
                self.assertIn("Lead atual", chapter)
                self.assertIn("Texto atual", chapter)

if __name__ == "__main__":
    unittest.main()

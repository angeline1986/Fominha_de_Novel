import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from nocfsb.menu import main
from nocfsb.src.epub_builder import build_epub
from nocfsb.src.epub_validation import validate_epub
from nocfsb.src.parser import build_book_urls
from nocfsb.src.scraper import validate_chapter_collection


class DetailedValidationTest(unittest.TestCase):
    def test_identical_text_in_different_volumes_blocks_collection(self):
        config = {"volumes": [
            {"base": "https://nocfsb.com/manga/book/volume-1", "start": 1, "end": 1},
            {"base": "https://nocfsb.com/manga/book/volume-2", "start": 1, "end": 1},
        ]}
        chapters = [
            {"url": url, "title": "Capítulo 01", "paragraphs": ["Mesmo texto longo."]}
            for url in build_book_urls(config)
        ]

        result = validate_chapter_collection(config, chapters)

        self.assertFalse(result["is_valid"])
        self.assertEqual(result["missing_urls"], [])
        self.assertEqual(result["duplicate_content_groups"], [[chapter["url"] for chapter in chapters]])

    def test_empty_content_and_generic_title_block_collection(self):
        config = {"volumes": [{"base": "https://nocfsb.com/manga/book/volume-1", "start": 1, "end": 1}]}
        url = build_book_urls(config)[0]

        result = validate_chapter_collection(config, [{"url": url, "title": "Capítulo", "paragraphs": ["  "]}])

        self.assertFalse(result["is_valid"])
        self.assertEqual(result["invalid_title_urls"], [url])
        self.assertEqual(result["empty_content_urls"], [url])

    def test_generated_epub_passes_archive_and_index_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = {
                "book": {"id": "test-book", "title": "Test Book", "author": "Test Author", "language": "pt-BR"},
                "output_epub": str(root / "test-book.epub"),
                "cover_source": "missing.jpg",
            }
            chapter = {"url": "https://nocfsb.com/manga/book/volume-1/capitulo-01/", "title": "Capítulo 01", "paragraphs": ["Texto do capítulo."]}
            with patch("nocfsb.src.epub_builder.__file__", str(root / "nocfsb" / "src" / "epub_builder.py")):
                path = build_epub([chapter], config)

            result = validate_epub(path, 1)

            self.assertTrue(result["is_valid"], result["issues"])
            self.assertEqual(result["chapters_checked"], 1)

    def test_corrupt_epub_fails_archive_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "broken.epub"
            path.write_bytes(b"not a zip archive")

            result = validate_epub(path, 1)

            self.assertFalse(result["is_valid"])
            self.assertTrue(result["issues"])

    def test_generate_option_publishes_only_validated_epub(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = {
                "book": {"id": "test-book", "title": "Test Book", "author": "Test Author"},
                "output_json": str(root / "chapters.json"),
                "output_epub": str(root / "book.epub"),
                "cover_source": "missing.jpg",
                "volumes": [{"base": "https://nocfsb.com/manga/book/volume-1", "start": 1, "end": 1}],
            }
            config_path = root / "config_test.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            (root / "chapters.json").write_text(json.dumps([{
                "url": build_book_urls(config)[0], "title": "Capítulo 01", "paragraphs": ["Texto do capítulo."]
            }]), encoding="utf-8")
            output = StringIO()
            with patch("nocfsb.menu.ROOT", root), patch(
                "nocfsb.src.epub_builder.__file__", str(root / "nocfsb" / "src" / "epub_builder.py")
            ), patch("builtins.input", side_effect=["3", "0"]), redirect_stdout(output):
                self.assertEqual(main(["--config", str(config_path)]), 0)

            self.assertTrue((root / "book.epub").exists())
            self.assertFalse((root / "book.candidate.epub").exists())
            self.assertIn("EPUB verificado", output.getvalue())

    def test_generate_option_blocks_duplicate_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = {
                "book": {"id": "test-book", "title": "Test Book"},
                "output_json": str(root / "chapters.json"),
                "output_epub": str(root / "book.epub"),
                "volumes": [
                    {"base": "https://nocfsb.com/manga/book/volume-1", "start": 1, "end": 1},
                    {"base": "https://nocfsb.com/manga/book/volume-2", "start": 1, "end": 1},
                ],
            }
            config_path = root / "config_test.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            (root / "chapters.json").write_text(json.dumps([
                {"url": url, "title": "Capítulo 01", "paragraphs": ["Texto repetido."]}
                for url in build_book_urls(config)
            ]), encoding="utf-8")
            output = StringIO()
            with patch("nocfsb.menu.ROOT", root), patch("builtins.input", side_effect=["3", "0"]), patch(
                "nocfsb.menu.build_epub"
            ) as build, redirect_stdout(output):
                self.assertEqual(main(["--config", str(config_path)]), 0)
            build.assert_not_called()
            self.assertIn("Grupos com texto repetido: 1", output.getvalue())


if __name__ == "__main__":
    unittest.main()

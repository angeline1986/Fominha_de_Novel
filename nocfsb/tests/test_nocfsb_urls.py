import json
import tempfile
import unittest
from pathlib import Path

from nocfsb.src.epub_builder import build_volume_sections, chapter_display_title
from nocfsb.src.parser import build_book_urls
from nocfsb.src.scraper import (
    build_pending_urls,
    filter_uncollected_urls,
    rebuild_cache_from_output,
    normalize_chapters,
    validate_chapter_collection,
)


class NocfsbUrlsTest(unittest.TestCase):
    def test_build_book_urls_includes_volume_ranges(self):
        config = {
            "volumes": [
                {"base": "https://nocfsb.com/manga/salt-society/volume-01", "start": 1, "end": 2, "leading": ["00_1"]},
                {"base": "https://nocfsb.com/manga/salt-society/volume-02", "start": 12, "end": 12},
            ]
        }

        urls = build_book_urls(config)

        self.assertIn("https://nocfsb.com/manga/salt-society/volume-01/capitulo-00_1/", urls)
        self.assertIn("https://nocfsb.com/manga/salt-society/volume-01/capitulo-01/", urls)
        self.assertIn("https://nocfsb.com/manga/salt-society/volume-01/capitulo-02/", urls)
        self.assertNotIn("https://nocfsb.com/manga/salt-society/volume-01/capitulo-1/", urls)
        self.assertIn("https://nocfsb.com/manga/salt-society/volume-02/capitulo-12/", urls)
        self.assertEqual(len(urls), 4)

    def test_filter_uncollected_urls_skips_completed_urls(self):
        cache = {"completed_urls": ["https://a", "https://b"]}
        urls = ["https://a", "https://b", "https://c"]

        self.assertEqual(filter_uncollected_urls(urls, cache), ["https://c"])

    def test_rebuild_cache_from_existing_output_when_cache_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "salt-society.json"
            cache_path = output_dir / "salt-society_cache.json"
            output_path.write_text(
                json.dumps([
                    {"url": "https://a", "title": "A", "paragraphs": ["x"], "source_page": 0, "file_name": ""},
                    {"url": "https://b", "title": "B", "paragraphs": ["y"], "source_page": 1, "file_name": ""},
                ]),
                encoding="utf-8"
            )

            cache = rebuild_cache_from_output(cache_path, output_path)

            self.assertEqual(cache["completed_urls"], ["https://a", "https://b"])
            self.assertEqual(len(cache["chapters"]), 2)
            self.assertEqual(cache["chapters"][0]["url"], "https://a")

    def test_normalize_chapters_drops_empty_and_duplicate_entries(self):
        chapters = [
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-0/", "title": "Salt Society (Novel)", "paragraphs": [], "source_page": 2},
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-00_1/", "title": "— Capítulo 00 - Prólogo", "paragraphs": ["Olá"], "source_page": 0},
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-00_1/", "title": "— Capítulo 00 - Prólogo", "paragraphs": ["Olá"], "source_page": 1},
        ]

        normalized = normalize_chapters(chapters)

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["url"], "https://nocfsb.com/manga/salt-society/volume-01/capitulo-00_1/")

    def test_config_metadata_and_cover_path_are_defined(self):
        config = {
            "book": {"author": "ARGON18"},
            "cover_source": "cover.jpg",
        }

        self.assertEqual(config["book"]["author"], "ARGON18")
        self.assertTrue(config["cover_source"].endswith(".jpg"))

    def test_validate_chapter_collection_detects_missing_number(self):
        config = {
            "volumes": [
                {"base": "https://nocfsb.com/manga/salt-society/volume-01", "start": 0, "end": 2},
            ]
        }
        chapters = [
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-0/", "title": "Capítulo 0", "paragraphs": ["x"]},
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-2/", "title": "Capítulo 2", "paragraphs": ["y"]},
        ]

        result = validate_chapter_collection(config, chapters)

        self.assertFalse(result["is_valid"])
        self.assertIn(1, result["missing_numbers"])

    def test_validate_chapter_collection_allows_intentional_gap_after_leading_chapter(self):
        config = {
            "volumes": [
                {"base": "https://nocfsb.com/manga/salt-society/volume-01", "start": 10, "end": 12, "leading": ["00_1"]},
            ]
        }
        chapters = [
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-00_1/", "title": "Prólogo", "paragraphs": ["x"]},
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-10/", "title": "Capítulo 10", "paragraphs": ["a"]},
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-11/", "title": "Capítulo 11", "paragraphs": ["b"]},
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-12/", "title": "Capítulo 12", "paragraphs": ["c"]},
        ]

        result = validate_chapter_collection(config, chapters)

        self.assertTrue(result["is_valid"])
        self.assertEqual(result["missing_numbers"], [])

    def test_validate_chapter_collection_detects_out_of_order_sequence(self):
        config = {
            "volumes": [
                {"base": "https://nocfsb.com/manga/salt-society/volume-01", "start": 10, "end": 12, "leading": ["00_1"]},
            ]
        }
        chapters = [
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-00_1/", "title": "Prólogo", "paragraphs": ["x"]},
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-10/", "title": "Capítulo 10", "paragraphs": ["a"]},
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-12/", "title": "Capítulo 12", "paragraphs": ["c"]},
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-11/", "title": "Capítulo 11", "paragraphs": ["b"]},
        ]

        result = validate_chapter_collection(config, chapters)

        self.assertFalse(result["is_valid"])
        self.assertIn("sequence_order", result)
        self.assertFalse(result["sequence_order"])
        self.assertIn(12, result["order_issues"])

    def test_build_pending_urls_prioritizes_failed_urls(self):
        urls = [
            "https://a",
            "https://b",
            "https://c",
        ]
        pending = build_pending_urls(urls, {"https://b"}, ["https://c"])

        self.assertEqual(pending, ["https://c", "https://a"])

    def test_chapter_display_title_includes_volume_identifier(self):
        chapter = {"url": "https://nocfsb.com/manga/salt-society/volume-02/capitulo-31/", "title": "— Capítulo 31"}

        self.assertEqual(chapter_display_title(chapter), "Volume 2 — Capítulo 31")

    def test_build_volume_sections_groups_chapters_by_volume(self):
        chapters = [
            {"url": "https://nocfsb.com/manga/salt-society/volume-01/capitulo-00_1/", "title": "Volume 1 — Capítulo 00 - Prólogo"},
            {"url": "https://nocfsb.com/manga/salt-society/volume-02/capitulo-31/", "title": "Volume 2 — Capítulo 31"},
            {"url": "https://nocfsb.com/manga/salt-society/volume-02/capitulo-32/", "title": "Volume 2 — Capítulo 32"},
        ]

        sections = build_volume_sections(chapters)

        self.assertEqual([section["volume_number"] for section in sections], [1, 2])
        self.assertEqual(len(sections[1]["chapters"]), 2)


if __name__ == "__main__":
    unittest.main()

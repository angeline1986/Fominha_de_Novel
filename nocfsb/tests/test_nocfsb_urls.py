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

    def test_same_chapter_number_in_different_volumes_is_preserved(self):
        config = {
            "volumes": [
                {"base": "https://nocfsb.com/manga/book/volume-1", "start": 1, "end": 1},
                {"base": "https://nocfsb.com/manga/book/volume-2", "start": 1, "end": 1},
            ]
        }
        chapters = [
            {"url": url, "title": "Capítulo 1", "paragraphs": [f"Texto do volume {index}"]}
            for index, url in enumerate(build_book_urls(config), start=1)
        ]

        self.assertEqual(len(normalize_chapters(chapters)), 2)
        self.assertTrue(validate_chapter_collection(config, chapters)["is_valid"])
        self.assertEqual(validate_chapter_collection(config, chapters[:1])["missing_urls"], [chapters[1]["url"]])

    def test_config_metadata_and_cover_path_are_defined(self):
        config = {
            "book": {"author": "ARGON18"},
            "cover_source": "cover.jpg",
        }

        self.assertEqual(config["book"]["author"], "ARGON18")
        self.assertTrue(config["cover_source"].endswith(".jpg"))

    def test_custom_nocfsb_config_builds_7_minutes_of_heaven_urls(self):
        config_path = Path(__file__).resolve().parents[1] / "config_7_minutes_of_heaven.json"
        self.assertTrue(config_path.exists(), "Configuração da obra não foi criada ainda.")

        config = json.loads(config_path.read_text(encoding="utf-8"))
        urls = build_book_urls(config)

        self.assertIn("https://nocfsb.com/manga/7-minutes-of-heaven/volume-1/capitulo-01/", urls)
        self.assertIn("https://nocfsb.com/manga/7-minutes-of-heaven/volume-2/capitulo-13_1/", urls)
        self.assertIn("https://nocfsb.com/manga/7-minutes-of-heaven/volume-3/capitulo-09_2/", urls)
        self.assertIn("https://nocfsb.com/manga/7-minutes-of-heaven/volume-4/capitulo-07_3/", urls)
        self.assertIn("https://nocfsb.com/manga/7-minutes-of-heaven/spin-off/spin-off-01/", urls)
        self.assertEqual(len(urls), 64)
        spin_off_urls = [url for url in urls if "/spin-off/" in url or "/spin-off-2-fim/" in url]
        self.assertEqual(
            spin_off_urls,
            [
                f"https://nocfsb.com/manga/7-minutes-of-heaven/spin-off/spin-off-{slug}/"
                for slug in ("01", "01-2", "02", "03", "04", "05")
            ] + [
                f"https://nocfsb.com/manga/7-minutes-of-heaven/spin-off-2-fim/spin-off-{slug}/"
                for slug in ("01_1", "02_1", "03_1", "03-2", "04_1", "04-2", "05_1", "05-2")
            ],
        )

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

    def test_build_volume_sections_keeps_spin_offs_after_volumes(self):
        chapters = [
            {"url": "https://nocfsb.com/manga/book/volume-1/capitulo-01/"},
            {"url": "https://nocfsb.com/manga/book/spin-off/spin-off-01/"},
            {"url": "https://nocfsb.com/manga/book/spin-off-2-fim/spin-off-01/"},
        ]

        sections = build_volume_sections(chapters)

        self.assertEqual([section["title"] for section in sections], ["Volume 1", "Spin-off", "Spin-off 2 Fim"])


if __name__ == "__main__":
    unittest.main()

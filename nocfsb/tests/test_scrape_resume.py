import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from nocfsb.menu import main
from nocfsb.src.http_client import fetch_html
from nocfsb.src.scraper import run_scrape, validate_chapter_collection


class ScrapeResumeTest(unittest.TestCase):
    def test_fetch_rejects_redirect_to_another_chapter(self):
        response = Mock()
        response.url = "https://nocfsb.com/manga/book/spin-off/spin-off-01/"
        session = Mock()
        session.get.return_value = response

        with self.assertRaisesRegex(RuntimeError, "Redirecionamento para outro capítulo"):
            fetch_html(session, "https://nocfsb.com/manga/book/spin-off-2-fim/spin-off-01/")

    def test_changed_config_drops_stale_cache_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            first = "https://nocfsb.com/manga/book/spin-off/spin-off-01/"
            wrong = "https://nocfsb.com/manga/book/spin-off-2-fim/spin-off-01/"
            correct = "https://nocfsb.com/manga/book/spin-off-2-fim/spin-off-01_1/"
            config = {
                "output_dir": str(output),
                "output_json": str(output / "chapters.json"),
                "cache_file": str(output / "cache.json"),
                "chapter_delay_min_ms": 0,
                "chapter_delay_max_ms": 0,
                "volumes": [
                    {"base": "https://nocfsb.com/manga/book/spin-off", "chapter_prefix": "spin-off", "chapters": ["01"]},
                    {"base": "https://nocfsb.com/manga/book/spin-off-2-fim", "chapter_prefix": "spin-off", "chapters": ["01_1"]},
                ],
            }
            chapters = [
                {"url": url, "title": "Spin Off 01", "paragraphs": ["Texto"], "source_page": index}
                for index, url in enumerate((first, wrong))
            ]
            (output / "cache.json").write_text(json.dumps({
                "chapters": chapters,
                "completed_urls": [first, wrong],
                "failed_urls": ["https://nocfsb.com/manga/book/spin-off/spin-off-06/"],
            }), encoding="utf-8")
            html = "<h1>Spin Off 01</h1><article><p>Texto correto.</p></article>"

            with patch("nocfsb.src.scraper.fetch_html", return_value=html) as fetch:
                summary = run_scrape(config)
            self.assertEqual(fetch.call_args.args[1], correct)
            self.assertEqual([chapter.url for chapter in summary.chapters], [first, correct])
            cache = json.loads((output / "cache.json").read_text(encoding="utf-8"))
            self.assertEqual(cache["completed_urls"], [first, correct])
            self.assertEqual(cache["failed_urls"], [])

    def test_new_book_option_creates_isolated_config_and_activates_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            existing_path = root / "config_existing.json"
            existing_data = {"book": {"id": "existing", "title": "Existing"}, "volumes": []}
            existing_path.write_text(json.dumps(existing_data), encoding="utf-8")
            answers = [
                "5", "Nova História", "", "https://nocfsb.com/manga/nova/volume-1/",
                "", "1", "2", "", "", "00_1", "s",
                "https://nocfsb.com/manga/nova/spin-off/", "l", "spin-off", "01_1, 01-2", "n", "0",
            ]
            output = StringIO()
            with patch("nocfsb.menu.ROOT", root), patch("builtins.input", side_effect=answers), redirect_stdout(output):
                self.assertEqual(main(["--config", str(existing_path)]), 0)

            new_path = root / "config_nova-historia.json"
            config = json.loads(new_path.read_text(encoding="utf-8"))
            self.assertEqual(config["book"]["title"], "Nova História")
            self.assertEqual(config["cache_file"], "output/nova-historia_cache.json")
            self.assertEqual(config["output_epub"], "output/nova-historia.epub")
            self.assertEqual(config["volumes"][0]["leading"], ["00_1"])
            self.assertEqual(config["volumes"][1]["chapter_prefix"], "spin-off")
            self.assertEqual(config["volumes"][1]["chapters"], ["01_1", "01-2"])
            self.assertEqual(json.loads(existing_path.read_text(encoding="utf-8")), existing_data)
            self.assertIn(f"config: {new_path}", output.getvalue())

            reopened = StringIO()
            with patch("nocfsb.menu.ROOT", root), patch("builtins.input", side_effect=["2", "0"]), redirect_stdout(reopened):
                self.assertEqual(main([]), 0)
            self.assertIn(f"config: {new_path}", reopened.getvalue())

    def test_initial_selection_offers_new_book(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for name in ("a", "b"):
                (root / f"config_{name}.json").write_text(
                    json.dumps({"book": {"title": name}, "volumes": []}), encoding="utf-8"
                )
            with patch("nocfsb.menu.ROOT", root), patch("nocfsb.menu._new_config", return_value=None) as create, patch(
                "builtins.input", return_value="n"
            ):
                self.assertEqual(main([]), 0)
            create.assert_called_once_with()

    def test_menu_without_config_asks_which_book_to_open(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = root / "config_a.json"
            second = root / "config_b.json"
            first.write_text(json.dumps({"book": {"title": "Obra A"}, "volumes": []}), encoding="utf-8")
            second.write_text(json.dumps({"book": {"title": "Obra B"}, "volumes": []}), encoding="utf-8")
            output = StringIO()
            with patch("nocfsb.menu.ROOT", root), patch("builtins.input", side_effect=["2", "0"]), redirect_stdout(output):
                self.assertEqual(main([]), 0)
            self.assertIn("2. Obra B", output.getvalue())
            self.assertIn(f"config: {second}", output.getvalue())

    def test_menu_returns_after_ctrl_c_without_traceback(self):
        with patch("builtins.input", side_effect=["1", "0"]), patch(
            "nocfsb.menu.load_config", return_value={"volumes": []}
        ), patch("nocfsb.menu.run_scrape", side_effect=KeyboardInterrupt):
            self.assertEqual(main(["--config", "unused.json"]), 0)

    def test_interrupt_after_first_chapter_resumes_from_second(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            config = {
                "book": {"id": "test-book"},
                "output_dir": str(output),
                "output_json": str(output / "chapters.json"),
                "cache_file": str(output / "cache.json"),
                "chapter_delay_min_ms": 0,
                "chapter_delay_max_ms": 0,
                "volumes": [{"base": "https://example.org/volume-1", "start": 1, "end": 2}],
            }
            html = "<h1>Capítulo 1</h1><article><p>Conteúdo do capítulo.</p></article>"

            with patch("nocfsb.src.scraper.fetch_html", return_value=html) as fetch, patch(
                "nocfsb.src.scraper.polite_sleep", side_effect=KeyboardInterrupt
            ):
                with self.assertRaises(KeyboardInterrupt):
                    run_scrape(config)
            self.assertEqual(fetch.call_count, 1)

            cache = json.loads((output / "cache.json").read_text(encoding="utf-8"))
            self.assertEqual(len(cache["chapters"]), 1)
            self.assertEqual(len(cache["completed_urls"]), 1)
            self.assertEqual(len(json.loads((output / "chapters.json").read_text(encoding="utf-8"))), 1)

            with patch("nocfsb.src.scraper.fetch_html", return_value=html) as fetch, patch(
                "nocfsb.src.scraper.polite_sleep"
            ):
                summary = run_scrape(config)
            self.assertEqual(fetch.call_count, 1)
            self.assertTrue(fetch.call_args.args[1].endswith("capitulo-02/"))
            self.assertEqual(summary.items_found, 2)
            self.assertTrue((output / "chapters-summary.json").exists())

    def test_invalid_chapter_is_retried_and_restored_to_book_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            config = {
                "output_dir": str(output),
                "output_json": str(output / "chapters.json"),
                "cache_file": str(output / "cache.json"),
                "chapter_delay_min_ms": 0,
                "chapter_delay_max_ms": 0,
                "volumes": [{"base": "https://example.org/volume-1", "start": 1, "end": 2}],
            }
            first_html = "<h1>Capítulo 1</h1><article><p>Conteúdo do primeiro.</p></article>"
            second_html = "<h1>Capítulo 2</h1><article><p>Conteúdo do segundo.</p></article>"
            with patch("nocfsb.src.scraper.fetch_html", side_effect=["<h1>Capítulo</h1>", second_html]), patch(
                "nocfsb.src.scraper.polite_sleep"
            ):
                first = run_scrape(config)
            self.assertEqual(first.items_found, 1)
            cache = json.loads((output / "cache.json").read_text(encoding="utf-8"))
            self.assertEqual(len(cache["failed_urls"]), 1)

            with patch("nocfsb.src.scraper.fetch_html", return_value=first_html) as fetch:
                second = run_scrape(config)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(second.items_found, 2)
            self.assertTrue(validate_chapter_collection(config)["is_valid"])


if __name__ == "__main__":
    unittest.main()

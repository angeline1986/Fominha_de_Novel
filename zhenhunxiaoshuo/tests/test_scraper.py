import tempfile
import unittest
from pathlib import Path

from zhenhunxiaoshuo.scraper import load_chapter_rows

class ScraperTests(unittest.TestCase):
    def test_load_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chapters.csv"
            path.write_text(
                "Título,Link\n第一章 王城命案,https://example.com/1.html\n",
                encoding="utf-8-sig",
            )
            rows = load_chapter_rows(path)
            self.assertEqual(rows[0]["title"], "第一章 王城命案")
            self.assertEqual(rows[0]["url"], "https://example.com/1.html")

    def test_load_csv_skips_introduction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chapters.csv"
            path.write_text(
                "Título,Link\n"
                "帝王攻略（语笑阑珊）简介,https://example.com/intro.html\n"
                "第一章 王城命案,https://example.com/1.html\n",
                encoding="utf-8-sig",
            )
            rows = load_chapter_rows(path)
            self.assertEqual(
                rows,
                [{"title": "第一章 王城命案", "url": "https://example.com/1.html"}],
            )

if __name__ == "__main__":
    unittest.main()

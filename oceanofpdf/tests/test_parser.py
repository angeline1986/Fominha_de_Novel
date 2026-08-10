from pathlib import Path
import unittest

from oceanofpdf.parser import parse_category_page


FIXTURE = Path(__file__).parent / "fixtures" / "omegaverse_page_1.html"
PAGE_URL = "https://oceanofpdf.com/category/genres/omegaverse/"


class ParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = FIXTURE.read_text(encoding="utf-8")
        cls.result = parse_category_page(cls.html, page_number=1, page_url=PAGE_URL)

    def test_extracts_seven_records(self):
        self.assertEqual(7, len(self.result.items))

    def test_first_record(self):
        item = self.result.items[0]
        self.assertEqual("The Heir (The Arrangement and the Heir Book 2)", item.title)
        self.assertEqual("River Thorne", item.author)
        self.assertEqual(["Romance", "Omegaverse", "M M Romance"], item.genres)
        self.assertEqual(1, item.source_page)
        self.assertIn("/authors/river-thorne/", item.source_url)

    def test_duplicate_comma_does_not_create_empty_genre(self):
        item = next(book for book in self.result.items if book.author == "Sophie O'Dare")
        self.assertEqual(["Omegaverse", "Gay", "M M Romance"], item.genres)

    def test_preserves_raw_title_from_source(self):
        item = next(book for book in self.result.items if book.author == "Mitsuru Si")
        self.assertEqual("Megumi and u0026 Tsugumi, Vol. 3", item.title)
        self.assertEqual(item.title, item.title_raw)

    def test_expected_authors(self):
        self.assertEqual(
            [
                "River Thorne",
                "Sophie O'Dare",
                "Marra Moore",
                "Jena Wade",
                "Eve Newton",
                "Colbie Dunbar",
                "Mitsuru Si",
            ],
            [item.author for item in self.result.items],
        )


if __name__ == "__main__":
    unittest.main()

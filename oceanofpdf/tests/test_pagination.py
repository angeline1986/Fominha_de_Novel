import unittest

from oceanofpdf.pagination import build_page_url, iter_page_urls


BASE = "https://oceanofpdf.com/category/genres/omegaverse/"


class PaginationTests(unittest.TestCase):
    def test_page_one_uses_category_root(self):
        self.assertEqual(BASE, build_page_url(BASE, 1))

    def test_page_two(self):
        self.assertEqual(BASE + "page/2/", build_page_url(BASE, 2))

    def test_page_452(self):
        self.assertEqual(BASE + "page/452/", build_page_url(BASE, 452))

    def test_range(self):
        values = list(iter_page_urls(BASE, 1, 3))
        self.assertEqual([1, 2, 3], [page for page, _ in values])

    def test_invalid_page(self):
        with self.assertRaises(ValueError):
            build_page_url(BASE, 0)


if __name__ == "__main__":
    unittest.main()

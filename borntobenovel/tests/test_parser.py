import base64
import unittest

from borntobenovel.parser import ParseError, parse_chapter_page
from borntobenovel.epub_builder import _format_paragraph
from borntobenovel.scraper import configured_urls, load_config, validate


URL = "https://borntobenovel.com/novel/mind-the-gap/chapters/ch-77"


class ParserTests(unittest.TestCase):
    def test_embedded_content_preserves_paragraphs(self):
        encoded = base64.b64encode('First paragraph.\r\n\r\nSecond paragraph with café.'.encode()).decode()
        page = f'<header><h1 class="header-title">Chapter 77</h1></header><div id="chapterContent"></div><script>const contentData = \'{encoded}\';</script>'
        result = parse_chapter_page(page, URL)
        self.assertEqual(result["paragraphs"], ["First paragraph.", "Second paragraph with café."])
        self.assertEqual(result["source_page"], 77)

    def test_rendered_html_keeps_spaces_between_spans(self):
        page = '<header><h1 class="header-title">Chapter 77</h1></header><div id="chapterContent"><p><span>Hello </span><span>world.</span></p></div>'
        self.assertEqual(parse_chapter_page(page, URL)["paragraphs"], ["Hello world."])

    def test_wrong_chapter_is_rejected(self):
        page = '<header><h1 class="header-title">Chapter 78</h1></header><div id="chapterContent"><p>Text</p></div>'
        with self.assertRaises(ParseError):
            parse_chapter_page(page, URL)

    def test_config_has_exact_requested_range(self):
        config = load_config()
        urls = configured_urls(config)
        self.assertEqual(len(urls), 64)
        self.assertEqual(urls[0], URL)
        self.assertTrue(urls[-1].endswith("/ch-140"))
        self.assertEqual(validate(config, [])["missing_urls"], urls)

    def test_epub_formats_reader_markup_safely(self):
        self.assertEqual(_format_paragraph("*Soft* and **strong** <text>"), "<p><em>Soft</em> and <strong>strong</strong> &lt;text&gt;</p>")
        self.assertEqual(_format_paragraph("* * *"), "<hr/>")


if __name__ == "__main__":
    unittest.main()

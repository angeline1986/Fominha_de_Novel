"""Regressions for duplicated scraped chapter headings in EPUB XHTML."""
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from nocfsb.src.epub_builder import generate_chapter_xhtml


class EpubHeadingDedupTest(unittest.TestCase):
    def render(self, title, paragraphs, url='https://nocfsb.com/manga/salt-society/volume-01/capitulo-06/'):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = {'title': title, 'url': url, 'paragraphs': list(paragraphs)}
            original = list(chapter['paragraphs'])
            filename = generate_chapter_xhtml(Path(tmp), chapter, 0)
            root = ET.parse(Path(tmp) / filename).getroot()
            ns = {'x': 'http://www.w3.org/1999/xhtml'}
            body = root.find('x:body', ns)
            h3 = body.find('x:h3', ns).text
            content = [p.text for p in body.findall('x:p', ns)]
            self.assertEqual(chapter['paragraphs'], original)
            return h3, content

    def test_duplicate_with_arrow_removed(self):
        heading, paragraphs = self.render('— Capítulo 06', ['↢—Capítulo 6', '— Gi-hyeon, você está brincando comigo?', 'Outro parágrafo'])
        self.assertEqual(heading, 'Volume 1 — Capítulo 06')
        self.assertEqual(paragraphs, ['— Gi-hyeon, você está brincando comigo?', 'Outro parágrafo'])

    def test_real_salt_society_bom_arrow_box_drawing_removed(self):
        _, paragraphs = self.render(
            'Capítulo 06', ['\ufeff↫─Capítulo 6', '— Gi-hyeon, você está brincando comigo?']
        )
        self.assertEqual(paragraphs, ['— Gi-hyeon, você está brincando comigo?'])

    def test_decorated_heading_with_zwsp_removed(self):
        _, paragraphs = self.render('Capítulo 06', ['\u200b↫─Capítulo 006', 'Narrativa'])
        self.assertEqual(paragraphs, ['Narrativa'])

    def test_decorated_heading_with_subtitle_preserved(self):
        _, paragraphs = self.render('Capítulo 06', ['\ufeff↫─Capítulo 6 — A revelação', 'Narrativa'])
        self.assertEqual(paragraphs, ['\ufeff↫─Capítulo 6 — A revelação', 'Narrativa'])

    def test_plain_padded_number_removed(self):
        _, paragraphs = self.render('Capítulo 06', [' Capítulo 006 ', 'Narrativa'])
        self.assertEqual(paragraphs, ['Narrativa'])

    def test_nonmatching_number_preserved(self):
        _, paragraphs = self.render('Capítulo 06', ['Capítulo 7', 'Texto'])
        self.assertEqual(paragraphs, ['Capítulo 7', 'Texto'])

    def test_real_dialogue_preserved(self):
        _, paragraphs = self.render('Capítulo 06', ['— Capítulo 6? Não acredito!', 'Texto'])
        self.assertEqual(paragraphs, ['— Capítulo 6? Não acredito!', 'Texto'])

    def test_subtitle_preserved(self):
        _, paragraphs = self.render('Capítulo 06', ['Capítulo 6 — A revelação', 'Texto'])
        self.assertEqual(paragraphs, ['Capítulo 6 — A revelação', 'Texto'])

    def test_only_first_nonempty_paragraph_eligible(self):
        _, paragraphs = self.render('Capítulo 06', ['', '↢—Capítulo 6', 'Capítulo 6', 'Narrativa'])
        self.assertEqual(paragraphs, [None, 'Capítulo 6', 'Narrativa'])

    def test_title_without_chapter_number_preserved(self):
        _, paragraphs = self.render('Prólogo', ['Capítulo 6', 'Narrativa'])
        self.assertEqual(paragraphs, ['Capítulo 6', 'Narrativa'])


if __name__ == '__main__':
    unittest.main()

"""Regression tests for Salt Society's volume navigation."""
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from nocfsb.src.epub_builder import build_volume_sections, generate_nav, generate_ncx


class EpubVolumeNavigationTest(unittest.TestCase):
    def test_salt_society_five_volumes_in_both_indexes(self):
        intervals = [(1, 0, 30), (2, 31, 59), (3, 60, 85),
                     (4, 86, 114), (5, 115, 129)]
        chapters = []
        for volume, start, end in intervals:
            for number in range(start, end + 1):
                chapters.append({
                    "title": f"Volume {volume} — Capítulo {number:02d}",
                    "file_name": f"file{len(chapters) + 1:04d}.xhtml",
                    "url": f"https://nocfsb.com/manga/salt-society/volume-{volume:02d}/capitulo-{number:02d}/",
                    "volume_number": volume,
                })
        self.assertEqual(len(chapters), 130)
        sections = build_volume_sections(chapters)
        self.assertEqual([len(s["chapters"]) for s in sections], [31, 29, 26, 29, 15])

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            config = {"book": {"title": "Salt Society", "id": "salt-society"}}
            generate_nav(folder, sections)
            generate_ncx(folder, sections, config)

            nav = ET.parse(folder / "nav.xhtml").getroot()
            html_ns = {"x": "http://www.w3.org/1999/xhtml"}
            top = nav.findall(".//x:nav/x:ol/x:li", html_ns)
            self.assertEqual(len(top), 6)  # title page + five volumes
            for idx, item in enumerate(top[1:]):
                self.assertEqual(item.find("x:a", html_ns).text, f"Volume {idx + 1}")
                children = item.findall("x:ol/x:li", html_ns)
                self.assertEqual(len(children), intervals[idx][2] - intervals[idx][1] + 1)
                self.assertFalse(children[0].find("x:a", html_ns).text.startswith("Volume"))

            ncx = ET.parse(folder / "toc.ncx").getroot()
            ns = {"n": "http://www.daisy.org/z3986/2005/ncx/"}
            self.assertEqual(ncx.find('.//n:meta[@name="dtb:depth"]', ns).get("content"), "2")
            parents = ncx.findall("n:navMap/n:navPoint", ns)
            self.assertEqual(len(parents), 6)
            orders = [int(point.get("playOrder")) for point in ncx.findall(".//n:navPoint", ns)]
            self.assertEqual(orders, list(range(1, 137)))  # title + 5 volumes + 130 chapters
            self.assertEqual([len(x.findall("n:navPoint", ns)) for x in parents[1:]],
                             [31, 29, 26, 29, 15])


if __name__ == "__main__":
    unittest.main()

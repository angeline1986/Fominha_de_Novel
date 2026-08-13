import unittest
from pathlib import Path

from zhenhunxiaoshuo.producao_epub.src.title_corrector import _ordered_mapping


class StructuralTitleCorrectorTests(unittest.TestCase):
    def test_extra_does_not_shift_physical_mapping(self):
        files = [Path(f"chapter_{n:03d}.xhtml") for n in range(1, 6)]
        rows = [
            {"source_position": "1", "titulo": "Capítulo 151 - A"},
            {"source_position": "2", "titulo": "Capítulo 152 - B"},
            {"source_position": "3", "titulo": "Extra"},
            {"source_position": "4", "titulo": "Capítulo 153 - C"},
            {"source_position": "5", "titulo": "Capítulo 154 - D"},
        ]
        mapping = _ordered_mapping(rows, files)
        self.assertEqual(mapping[2]["file"].name, "chapter_003.xhtml")
        self.assertEqual(mapping[3]["file"].name, "chapter_004.xhtml")
        self.assertEqual(mapping[4]["file"].name, "chapter_005.xhtml")


if __name__ == "__main__":
    unittest.main()

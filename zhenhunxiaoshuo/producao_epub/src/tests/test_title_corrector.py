import csv
import tempfile
import unittest
from pathlib import Path

from zhenhunxiaoshuo.producao_epub.src.title_corrector import _read_title_csv


class TitleCorrectorTests(unittest.TestCase):

    def test_semicolon_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "titles.csv"
            path.write_text(
                "Capítulo;Título no DOCX;Título no EPUB;Comparação\n"
                "151;Som maligno;Som Demoníaco;DIFERENTE\n",
                encoding="utf-8",
            )

            data = _read_title_csv(path)

        self.assertEqual(data["delimiter"], ";")
        self.assertEqual(
            data["chapter_titles"][151],
            "Som maligno",
        )


if __name__ == "__main__":
    unittest.main()

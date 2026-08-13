import unittest

from zhenhunxiaoshuo.producao_epub.src.title_corrector import (
    build_full_title,
    load_title_map,
)


class TitleCorrectorTests(unittest.TestCase):
    def test_full_title(self):
        self.assertEqual(
            build_full_title(2, "Torre Nove Mistérios"),
            "Capítulo 2 - Torre Nove Mistérios",
        )


if __name__ == "__main__":
    unittest.main()

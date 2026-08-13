import unittest
from zhenhunxiaoshuo.producao_epub.src import epub_builder, title_corrector
from zhenhunxiaoshuo.manipulacao_json.src import json_corrector


class OutputLayoutTests(unittest.TestCase):
    def test_review_output_is_numbered(self):
        self.assertEqual(json_corrector.OUTPUT_DIR.name, "2_revisao")

    def test_post_translation_output_is_numbered(self):
        self.assertEqual(title_corrector.CORRECTED_EPUB_DIR.name, "4_pos_trad")

    def test_generation_names(self):
        config = {"book": {"id": "obra"}}
        bruto = epub_builder._output_path(config, epub_builder.MODE_STANDARD)
        polido = epub_builder._output_path(config, epub_builder.MODE_NO_REDUNDANCY)
        self.assertEqual(bruto.name, "obra_bruto.epub")
        self.assertEqual(polido.name, "obra_polido.epub")
        self.assertEqual(bruto.parent.name, "3_geracao")
        self.assertEqual(polido.parent.name, "3_geracao")


if __name__ == "__main__":
    unittest.main()

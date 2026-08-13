import unittest

from zhenhunxiaoshuo.producao_epub.src.title_corrector import StructuralMatchError


class TitleCorrectorIdentityContractTests(unittest.TestCase):
    def test_menu_compatibility_constants_exist(self):
        from zhenhunxiaoshuo.producao_epub.src import title_corrector
        self.assertTrue(hasattr(title_corrector, 'ORIGINAL_EPUB_DIR'))
        self.assertTrue(hasattr(title_corrector, 'TRANSLATED_EPUB_DIR'))
        self.assertTrue(hasattr(title_corrector, 'TITLE_CSV_DIR'))
        self.assertTrue(hasattr(title_corrector, 'CORRECTED_EPUB_DIR'))

    def test_public_error_type_exists(self):
        self.assertTrue(issubclass(StructuralMatchError, ValueError))


if __name__ == "__main__":
    unittest.main()

import unittest

from zhenhunxiaoshuo.producao_epub.src.title_corrector import StructuralMatchError


class TitleCorrectorIdentityContractTests(unittest.TestCase):
    def test_public_error_type_exists(self):
        self.assertTrue(issubclass(StructuralMatchError, ValueError))


if __name__ == "__main__":
    unittest.main()

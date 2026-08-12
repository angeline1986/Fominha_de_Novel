import unittest

from zhenhunxiaoshuo.epub_builder import _split_lead


class EpubNoRedundancyTests(unittest.TestCase):
    def test_split_chinese_lead(self):
        title, phrase = _split_lead("【第一章-王城命案】西南王府的客房就长这样")
        self.assertEqual(title, "第一章-王城命案")
        self.assertEqual(phrase, "西南王府的客房就长这样")

    def test_split_translated_lead(self):
        title, phrase = _split_lead("[Capítulo 1 - O Assassinato] Assim são os quartos")
        self.assertEqual(title, "Capítulo 1 - O Assassinato")
        self.assertEqual(phrase, "Assim são os quartos")

    def test_unknown_format_is_not_guessed(self):
        self.assertEqual(_split_lead("texto sem delimitador"), (None, None))


if __name__ == "__main__":
    unittest.main()

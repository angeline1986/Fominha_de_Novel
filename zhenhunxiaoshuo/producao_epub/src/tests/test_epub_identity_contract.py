import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from zhenhunxiaoshuo.identity_contract import inspect_epub_identity
from zhenhunxiaoshuo.producao_epub.src import epub_builder


class EpubIdentityContractTests(unittest.TestCase):
    def test_chapter_xhtml_contains_ref_id(self):
        chapter = {
            "ref_id": "zhenhun-11257",
            "chapter_type": "chapter",
            "story_chapter_number": 151,
            "chapter_title": "第一百五十一章 魔音",
            "paragraphs": ["texto"],
        }
        xhtml = epub_builder._chapter_xhtml(
            chapter, 1, "zh-CN", epub_builder.MODE_NO_REDUNDANCY
        )
        self.assertIn('id="zref-zhenhun-11257"', xhtml)
        self.assertIn('data-ref-id="zhenhun-11257"', xhtml)
        self.assertIn('data-story-number="151"', xhtml)


if __name__ == "__main__":
    unittest.main()

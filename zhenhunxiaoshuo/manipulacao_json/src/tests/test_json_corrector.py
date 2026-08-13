import json
import tempfile
import unittest
from pathlib import Path

from zhenhunxiaoshuo.manipulacao_json.src.json_corrector import normalize_book_json


class PhysicalReferenceTests(unittest.TestCase):

    def test_confirmed_151_154_and_extra_order(self):
        data = {
            "chapters": [
                {
                    "source_url": "https://www.zhenhunxiaoshuo.com/11257.html",
                    "chapter_title": "第一百五十二章 魔音",
                    "chapter_lead": "【第一百五十二章-魔音】x",
                },
                {
                    "source_url": "https://www.zhenhunxiaoshuo.com/11258.html",
                    "chapter_title": "第一百五十二章 缘分",
                    "chapter_lead": "【第一百五十二章-缘分】y",
                },
                {
                    "source_url": "https://www.zhenhunxiaoshuo.com/11259.html",
                    "chapter_title": "第154章 【520番外】年少",
                    "chapter_lead": "番外",
                },
                {
                    "source_url": "https://www.zhenhunxiaoshuo.com/11260.html",
                    "chapter_title": "第一百五十三章 再度交锋",
                    "chapter_lead": "【第一百五十三章-再度交锋】z",
                },
                {
                    "source_url": "https://www.zhenhunxiaoshuo.com/11261.html",
                    "chapter_title": "第一百五十四章 变故",
                    "chapter_lead": "【第一百五十四章-变故】w",
                },
            ]
        }

        reference = {
            "reference_name": "test",
            "overrides": [
                {
                    "source_url": "https://www.zhenhunxiaoshuo.com/11257.html",
                    "chapter_type": "chapter",
                    "story_chapter_number": 151,
                    "corrected_title": "第一百五十一章 魔音",
                },
                {
                    "source_url": "https://www.zhenhunxiaoshuo.com/11258.html",
                    "chapter_type": "chapter",
                    "story_chapter_number": 152,
                    "corrected_title": "第一百五十二章 缘分",
                },
                {
                    "source_url": "https://www.zhenhunxiaoshuo.com/11260.html",
                    "chapter_type": "chapter",
                    "story_chapter_number": 153,
                    "corrected_title": "第一百五十三章 再度交锋",
                },
                {
                    "source_url": "https://www.zhenhunxiaoshuo.com/11261.html",
                    "chapter_type": "chapter",
                    "story_chapter_number": 154,
                    "corrected_title": "第一百五十四章 变故",
                },
                {
                    "source_url": "https://www.zhenhunxiaoshuo.com/11259.html",
                    "chapter_type": "extra",
                    "story_chapter_number": None,
                    "move_after_source_url": "https://www.zhenhunxiaoshuo.com/11261.html",
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "ref.json"
            ref.write_text(json.dumps(reference, ensure_ascii=False), encoding="utf-8")
            out = normalize_book_json(data, reference_file=ref)

        chapters = out["chapters"]

        self.assertEqual(chapters[0]["story_chapter_number"], 151)
        self.assertEqual(chapters[0]["chapter_title"], "第一百五十一章 魔音")
        self.assertEqual(chapters[1]["story_chapter_number"], 152)
        self.assertEqual(chapters[2]["story_chapter_number"], 153)
        self.assertEqual(chapters[3]["story_chapter_number"], 154)
        self.assertEqual(chapters[4]["chapter_type"], "extra")
        self.assertEqual(
            chapters[4]["source_url"],
            "https://www.zhenhunxiaoshuo.com/11259.html",
        )


if __name__ == "__main__":
    unittest.main()

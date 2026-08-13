import unittest

from zhenhunxiaoshuo.manipulacao_json.src import json_corrector


def chapter(url, title, lead=None):
    return {
        "source_url": url,
        "csv_title": title,
        "chapter_title": title,
        "chapter_lead": lead or f"【{title}】teste",
        "paragraph_count": 1,
        "title_matches_csv": True,
        "paragraphs": ["texto"],
    }


class JsonPhysicalReferenceTests(unittest.TestCase):

    def test_partial_sample_uses_url_mapping(self):
        data = {
            "chapters": [
                chapter("https://www.zhenhunxiaoshuo.com/11129.html", "第二十五章 魏紫衣"),
                chapter("https://www.zhenhunxiaoshuo.com/11235.html", "第一百二九章 出征"),
                chapter("https://www.zhenhunxiaoshuo.com/11250.html", "第一百一十四章 蜃影"),
                chapter("https://www.zhenhunxiaoshuo.com/11257.html", "第一百五十二章 魔音"),
                chapter("https://www.zhenhunxiaoshuo.com/11259.html", "第154章 【520番外】年少"),
                chapter("https://www.zhenhunxiaoshuo.com/11261.html", "第一百五十四章 变故"),
            ]
        }

        normalized = json_corrector._normalize(data)
        by_url = {item["source_url"]: item for item in normalized["chapters"]}

        self.assertEqual(by_url["https://www.zhenhunxiaoshuo.com/11129.html"]["story_chapter_number"], 24)
        self.assertEqual(by_url["https://www.zhenhunxiaoshuo.com/11235.html"]["story_chapter_number"], 129)
        self.assertEqual(by_url["https://www.zhenhunxiaoshuo.com/11250.html"]["story_chapter_number"], 144)
        self.assertEqual(by_url["https://www.zhenhunxiaoshuo.com/11257.html"]["story_chapter_number"], 151)
        self.assertEqual(by_url["https://www.zhenhunxiaoshuo.com/11261.html"]["story_chapter_number"], 154)

        extra = by_url["https://www.zhenhunxiaoshuo.com/11259.html"]
        self.assertEqual(extra["chapter_type"], "extra")
        self.assertIsNone(extra["story_chapter_number"])

    def test_source_value_is_preserved_for_audit(self):
        data = {
            "chapters": [
                chapter("https://www.zhenhunxiaoshuo.com/11250.html", "第一百一十四章 蜃影")
            ]
        }

        item = json_corrector._normalize(data)["chapters"][0]

        self.assertEqual(item["source_declared_number"], 114)
        self.assertEqual(item["story_chapter_number"], 144)
        self.assertEqual(item["source_chapter_title"], "第一百一十四章 蜃影")
        self.assertEqual(item["chapter_title"], "第一百四十四章 蜃影")


if __name__ == "__main__":
    unittest.main()

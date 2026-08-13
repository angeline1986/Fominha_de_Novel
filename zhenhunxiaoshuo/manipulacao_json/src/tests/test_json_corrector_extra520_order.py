import unittest
from zhenhunxiaoshuo.manipulacao_json.src import json_corrector

def chapter(url, title):
    return {
        "source_url": url,
        "csv_title": title,
        "chapter_title": title,
        "chapter_lead": f"【{title}】teste",
        "paragraph_count": 1,
        "title_matches_csv": True,
        "paragraphs": ["texto"],
    }

class Extra520EditorialOrderTests(unittest.TestCase):
    def test_reference_declares_extra_520_after_154(self):
        ref = json_corrector._load_reference()["physical_book"]["chapter_map"]
        extra = ref["https://www.zhenhunxiaoshuo.com/11259.html"]
        self.assertEqual(extra["editorial_after"], 154)
        self.assertEqual(extra["editorial_position"], 156)

    def test_real_critical_sequence(self):
        data = {"chapters": [
            chapter("https://www.zhenhunxiaoshuo.com/11257.html", "第一百五十二章 魔音"),
            chapter("https://www.zhenhunxiaoshuo.com/11258.html", "第一百五十二章 缘分"),
            chapter("https://www.zhenhunxiaoshuo.com/11259.html", "第154章 【520番外】年少"),
            chapter("https://www.zhenhunxiaoshuo.com/11260.html", "第一百五十三章 再度交锋"),
            chapter("https://www.zhenhunxiaoshuo.com/11261.html", "第一百五十四章 变故"),
            chapter("https://www.zhenhunxiaoshuo.com/11262.html", "第一百五十五章 天之涯"),
            chapter("https://www.zhenhunxiaoshuo.com/11263.html", "第一百五十六章 不如拐去打仗"),
        ]}
        rows = json_corrector._normalize(data)["chapters"]
        expected = ["11257","11258","11260","11261","11259","11262","11263"]
        actual = [row["source_url"].rsplit("/",1)[-1].replace(".html","") for row in rows]
        self.assertEqual(actual, expected)

        extra = next(row for row in rows if row["source_url"].endswith("/11259.html"))
        self.assertEqual(extra["source_position"], 3)
        self.assertEqual(extra["corrected_position"], 5)
        self.assertEqual(extra["editorial_position"], 156)
        self.assertEqual(extra["chapter_type"], "extra")
        self.assertIsNone(extra["story_chapter_number"])

if __name__ == "__main__":
    unittest.main()

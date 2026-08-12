import unittest
from zhenhunxiaoshuo.parser import parse_chapter

HTML = """
<html><body>
  <h1 class="article-title">第一章 王城命案</h1>
  <article class="article-content">
    <p>【第一章-王城命案】西南王府的客房就长这样</p>
    <p>西南有座山，名曰落仙。</p>
    <p>落仙山名字好听，景致也美。</p>
  </article>
</body></html>
"""

class ParserTests(unittest.TestCase):
    def test_separates_title_lead_and_story(self):
        chapter = parse_chapter(
            HTML,
            "https://www.zhenhunxiaoshuo.com/11106.html",
            "第一章 王城命案",
        )
        self.assertEqual(chapter.chapter_title, "第一章 王城命案")
        self.assertEqual(chapter.chapter_lead, "【第一章-王城命案】西南王府的客房就长这样")
        self.assertEqual(chapter.paragraphs[0], "西南有座山，名曰落仙。")
        self.assertEqual(chapter.paragraphs[1], "落仙山名字好听，景致也美。")
        self.assertEqual(chapter.paragraph_count, 2)
        self.assertTrue(chapter.title_matches_csv)

if __name__ == "__main__":
    unittest.main()

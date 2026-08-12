import json
import tempfile
import unittest
from pathlib import Path

from zhenhunxiaoshuo.models import Chapter
from zhenhunxiaoshuo.storage import save_book

class StorageTests(unittest.TestCase):
    def test_save_book(self):
        chapter = Chapter("u", "t", "t", "lead", ["p1", "p2"])
        with tempfile.TemporaryDirectory() as tmp:
            path = save_book([chapter], Path(tmp) / "book.json")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["chapter_count"], 1)
            self.assertEqual(data["chapters"][0]["paragraph_count"], 2)

if __name__ == "__main__":
    unittest.main()

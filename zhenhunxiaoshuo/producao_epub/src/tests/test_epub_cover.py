import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from zhenhunxiaoshuo.producao_epub.src import epub_builder


class EpubCoverIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "producao_epub/input/capas").mkdir(parents=True)
        (self.root / "producao_epub/output/3_geracao").mkdir(parents=True)
        self.cover_path = self.root / "producao_epub/input/capas/cover.jpg"
        self.cover_path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-for-test\xff\xd9")
        self.config = {
            "book": {
                "id": "livro_teste",
                "title": "Livro Teste",
                "author": "Autor",
                "language": "zh-CN",
            },
            "cover_path": "producao_epub/input/capas/cover.jpg",
        }
        (self.root / "config_zhenhunxiaoshuo.json").write_text(
            json.dumps(self.config, ensure_ascii=False), encoding="utf-8"
        )
        self.chapters = [
            {
                "chapter_title": "第一章 原始标题",
                "chapter_lead": "【第一章 新标题】 第一段引言",
                "paragraphs": ["正文 A1", "正文 A2"],
            },
            {
                "chapter_title": "第二章 原始标题",
                "chapter_lead": "【第二章 新标题】 第二段引言",
                "paragraphs": ["正文 B1", "正文 B2"],
            },
        ]
        self.json_path = self.root / "book.json"
        self.json_path.write_text(
            json.dumps({"chapters": self.chapters}, ensure_ascii=False),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _build(self, mode):
        with patch.object(epub_builder, "PROJECT_ROOT", self.root):
            return epub_builder.build_epub(self.json_path, mode=mode)

    def _inspect(self, path, mode):
        with zipfile.ZipFile(path) as epub:
            names = set(epub.namelist())
            self.assertIn("OEBPS/Images/cover.jpg", names)
            self.assertIn("OEBPS/cover.xhtml", names)
            self.assertIn("OEBPS/nav.xhtml", names)
            self.assertIn("OEBPS/toc.ncx", names)

            opf = ET.fromstring(epub.read("OEBPS/content.opf"))
            manifest = next(node for node in opf if node.tag.endswith("manifest"))
            spine = next(node for node in opf if node.tag.endswith("spine"))
            cover_items = [
                item for item in manifest
                if "cover-image" in item.attrib.get("properties", "").split()
            ]
            self.assertEqual(1, len(cover_items))
            cover_item = cover_items[0]
            self.assertEqual("image/jpeg", cover_item.attrib.get("media-type"))
            href = cover_item.attrib["href"]
            self.assertIn(f"OEBPS/{href}", names)

            cover_xhtml = ET.fromstring(epub.read("OEBPS/cover.xhtml"))
            image = next(node for node in cover_xhtml.iter() if node.tag.endswith("img"))
            self.assertEqual(href, image.attrib.get("src"))

            chapter_names = [f"OEBPS/Text/chapter_{i:03d}.xhtml" for i in range(1, 3)]
            self.assertTrue(all(name in names for name in chapter_names))
            self.assertEqual(2, len(chapter_names))

            itemrefs = [
                item.attrib.get("idref") for item in spine if item.tag.endswith("itemref")
            ]
            self.assertEqual(
                ["cover-page", "chapter_001", "chapter_002"],
                itemrefs,
            )

            nav = epub.read("OEBPS/nav.xhtml").decode("utf-8")
            ncx = epub.read("OEBPS/toc.ncx").decode("utf-8")
            self.assertLess(nav.index("chapter_001.xhtml"), nav.index("chapter_002.xhtml"))
            self.assertLess(ncx.index("chapter_001.xhtml"), ncx.index("chapter_002.xhtml"))

            chapter1 = epub.read(chapter_names[0]).decode("utf-8")
            chapter2 = epub.read(chapter_names[1]).decode("utf-8")
            for text in ["正文 A1", "正文 A2"]:
                self.assertIn(text, chapter1)
            for text in ["正文 B1", "正文 B2"]:
                self.assertIn(text, chapter2)

            if mode == epub_builder.MODE_STANDARD:
                self.assertIn("第一章 原始标题", chapter1)
                self.assertIn("【第一章 新标题】 第一段引言", chapter1)
            else:
                self.assertIn("第一章 新标题", chapter1)
                self.assertIn("第一段引言", chapter1)
                self.assertNotIn("【第一章 新标题】", chapter1)

    def test_standard_epub_contains_cover_and_preserves_chapters(self):
        path = self._build(epub_builder.MODE_STANDARD)
        self._inspect(path, epub_builder.MODE_STANDARD)

    def test_no_redundancy_epub_contains_cover_and_preserves_chapters(self):
        path = self._build(epub_builder.MODE_NO_REDUNDANCY)
        self._inspect(path, epub_builder.MODE_NO_REDUNDANCY)

    def test_cover_path_from_current_config_is_resolved_from_project_root(self):
        with patch.object(epub_builder, "PROJECT_ROOT", self.root):
            self.assertEqual(self.cover_path, epub_builder.find_cover(self.config))

    def test_missing_cover_builds_epub_without_cover_assets(self):
        self.cover_path.unlink()
        with patch.object(epub_builder, "PROJECT_ROOT", self.root):
            output = epub_builder.build_epub(self.json_path)

        with zipfile.ZipFile(output) as epub:
            names = set(epub.namelist())
            self.assertNotIn("OEBPS/Images/cover.jpg", names)
            self.assertNotIn("OEBPS/cover.xhtml", names)


if __name__ == "__main__":
    unittest.main()

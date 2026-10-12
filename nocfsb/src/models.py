from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChapterRecord:
    url: str
    title: str = ""
    paragraphs: list[str] = field(default_factory=list)
    source_page: int = 0
    file_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "paragraphs": self.paragraphs,
            "source_page": self.source_page,
            "file_name": self.file_name,
        }


@dataclass
class ScrapeSummary:
    source: str
    items_found: int
    urls_total: int
    chapters: list[ChapterRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "items_found": self.items_found,
            "urls_total": self.urls_total,
            "chapters": [chapter.to_dict() for chapter in self.chapters],
        }

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class BookRecord:
    title: str
    author: str
    genres: list[str]
    source_url: str
    source_page: int
    title_raw: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PageResult:
    page: int
    url: str
    items: list[BookRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "url": self.url,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class ScrapeSummary:
    source: str
    category: str
    start_page: int
    end_page: int
    pages_processed: int
    items_found: int
    pages_with_errors: list[int]
    items: list[BookRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "category": self.category,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "pages_processed": self.pages_processed,
            "items_found": self.items_found,
            "pages_with_errors": self.pages_with_errors,
            "items": [item.to_dict() for item in self.items],
        }

from dataclasses import dataclass, field
from typing import List

@dataclass
class Chapter:
    source_url: str
    csv_title: str
    chapter_title: str
    chapter_lead: str
    paragraphs: List[str] = field(default_factory=list)

    @property
    def paragraph_count(self) -> int:
        return len(self.paragraphs)

    @property
    def title_matches_csv(self) -> bool:
        return self.csv_title.strip() == self.chapter_title.strip()

    def to_dict(self) -> dict:
        return {
            "source_url": self.source_url,
            "csv_title": self.csv_title,
            "chapter_title": self.chapter_title,
            "chapter_lead": self.chapter_lead,
            "paragraph_count": self.paragraph_count,
            "title_matches_csv": self.title_matches_csv,
            "paragraphs": self.paragraphs,
        }

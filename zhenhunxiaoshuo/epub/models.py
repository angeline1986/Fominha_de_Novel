from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

@dataclass(frozen=True)
class EpubChapter:
    index: int
    title: str
    intro: str = ""
    paragraphs: List[str] = field(default_factory=list)
    source_url: str = ""

    @property
    def filename(self) -> str:
        return f"chapter_{self.index:03d}.xhtml"

@dataclass(frozen=True)
class EpubBook:
    title: str
    author: str
    language: str
    chapters: List[EpubChapter]
    cover_path: Optional[Path] = None
    identifier: Optional[str] = None

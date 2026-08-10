from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .models import BookRecord, PageResult


_SPACE_RE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return _SPACE_RE.sub(" ", value.replace("\xa0", " ")).strip()


def _parse_metadata_block(block: Tag) -> dict[str, str]:
    """Parse label/value pairs from .postmetainfo without depending on <br> layout."""
    metadata: dict[str, str] = {}
    current_label: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_label, buffer
        if current_label:
            metadata[current_label] = clean_text(" ".join(buffer))
        current_label = None
        buffer = []

    for child in block.children:
        if isinstance(child, Tag) and child.name == "strong":
            flush()
            current_label = clean_text(child.get_text(" ", strip=True)).rstrip(":").lower()
        elif isinstance(child, Tag) and child.name == "br":
            flush()
        else:
            text = clean_text(str(child) if not isinstance(child, Tag) else child.get_text(" ", strip=True))
            if text:
                buffer.append(text)

    flush()
    return metadata


def _split_genres(raw_genres: str) -> list[str]:
    genres: list[str] = []
    seen: set[str] = set()
    for part in raw_genres.split(","):
        genre = clean_text(part)
        if not genre:
            continue
        key = genre.casefold()
        if key not in seen:
            genres.append(genre)
            seen.add(key)
    return genres


def parse_category_page(
    html: str,
    *,
    page_number: int,
    page_url: str,
    item_selector: str = "article.post",
    title_selector: str = "h2.entry-title a",
    metadata_selector: str = ".postmetainfo",
) -> PageResult:
    soup = BeautifulSoup(html, "lxml")
    items: list[BookRecord] = []

    for article in soup.select(item_selector):
        title_link = article.select_one(title_selector)
        metadata_block = article.select_one(metadata_selector)
        if title_link is None or metadata_block is None:
            continue

        raw_title = clean_text(title_link.get_text(" ", strip=True))
        if not raw_title:
            continue

        metadata = _parse_metadata_block(metadata_block)
        author = clean_text(metadata.get("author"))
        genres = _split_genres(metadata.get("genre", ""))
        href = clean_text(title_link.get("href"))
        source_url = urljoin(page_url, href) if href else page_url

        items.append(
            BookRecord(
                title=raw_title,
                title_raw=raw_title,
                author=author,
                genres=genres,
                source_url=source_url,
                source_page=page_number,
            )
        )

    return PageResult(page=page_number, url=page_url, items=items)

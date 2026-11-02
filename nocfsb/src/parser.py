from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag


_SPACE_RE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return _SPACE_RE.sub(" ", value.replace("\xa0", " ")).strip()


def build_book_urls(config: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for volume in config.get("volumes", []):
        base = str(volume["base"]).rstrip("/")
        chapter_prefix = str(volume.get("chapter_prefix", "capitulo")).strip() or "capitulo"
        if "chapters" in volume:
            for chapter in volume["chapters"]:
                chapter_slug = str(chapter).strip()
                if not chapter_slug:
                    continue
                if not chapter_slug.startswith(f"{chapter_prefix}-"):
                    chapter_slug = f"{chapter_prefix}-{chapter_slug}"
                urls.append(f"{base}/{chapter_slug}/")
            continue
        leading = volume.get("leading", [])
        for chapter in leading:
            chapter_slug = str(chapter).strip()
            if not chapter_slug:
                continue
            if chapter_slug.startswith(f"{chapter_prefix}-"):
                urls.append(f"{base}/{chapter_slug}/")
            else:
                urls.append(f"{base}/{chapter_prefix}-{chapter_slug}/")

        start = int(volume.get("start", 0))
        end = int(volume.get("end", start))
        chapter_suffix = str(volume.get("chapter_suffix", "")).strip()
        for chapter_number in range(start, end + 1):
            slug = str(chapter_number)
            if chapter_number < 10:
                slug = f"0{chapter_number}"
            urls.append(f"{base}/{chapter_prefix}-{slug}{chapter_suffix}/")
    return urls


def extract_chapter_title(soup: BeautifulSoup) -> str:
    selectors = [
        "div.c-breadcrumb > ol > li.active",
        "h1",
        "h2",
        ".chapter-title",
        ".entry-title",
    ]
    for selector in selectors:
        element = soup.select_one(selector)
        if element is not None:
            title = clean_text(element.get_text(" ", strip=True))
            if title:
                return title
    return "Capítulo"


def extract_paragraphs(soup: BeautifulSoup) -> list[str]:
    paragraphs: list[str] = []
    selectors = [
        "div.reading-content div.text-left p",
        "div.chapter-content p",
        "article p",
        ".reading-content p",
    ]
    for selector in selectors:
        nodes = soup.select(selector)
        if not nodes:
            continue
        for node in nodes:
            text = clean_text(node.get_text(" ", strip=True))
            if text:
                paragraphs.append(text)
        if paragraphs:
            break
    return paragraphs


def parse_chapter_page(html: str, url: str, source_page: int = 0) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    title = extract_chapter_title(soup)
    paragraphs = extract_paragraphs(soup)
    return {
        "url": url,
        "title": title,
        "paragraphs": paragraphs,
        "source_page": source_page,
    }

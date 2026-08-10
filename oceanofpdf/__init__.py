"""OceanOfPDF category metadata scraper.

This package extracts bibliographic metadata from category archive pages.
It does not download book files.
"""

from .models import BookRecord, PageResult, ScrapeSummary
from .parser import parse_category_page
from .pagination import build_page_url

__all__ = [
    "BookRecord",
    "PageResult",
    "ScrapeSummary",
    "parse_category_page",
    "build_page_url",
]

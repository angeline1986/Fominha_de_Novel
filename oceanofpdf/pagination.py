from __future__ import annotations


def normalize_base_url(base_url: str) -> str:
    value = base_url.strip()
    if not value:
        raise ValueError("base_url cannot be empty")
    return value.rstrip("/") + "/"


def build_page_url(base_url: str, page_number: int) -> str:
    """Build an OceanOfPDF archive URL.

    Page 1 uses the category root. Pages >= 2 use /page/{n}/.
    """
    if page_number < 1:
        raise ValueError("page_number must be >= 1")

    root = normalize_base_url(base_url)
    if page_number == 1:
        return root
    return f"{root}page/{page_number}/"


def iter_page_urls(base_url: str, start_page: int, end_page: int):
    if start_page < 1:
        raise ValueError("start_page must be >= 1")
    if end_page < start_page:
        raise ValueError("end_page must be >= start_page")

    for page_number in range(start_page, end_page + 1):
        yield page_number, build_page_url(base_url, page_number)

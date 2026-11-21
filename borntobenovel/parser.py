from __future__ import annotations

import base64
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup


class ParseError(ValueError):
    pass


_CONTENT_RE = re.compile(r"\bconst\s+contentData\s*=\s*(['\"])([A-Za-z0-9+/=\s]+)\1\s*;")
_NUMBER_RE = re.compile(r"/ch-(\d+)/?$", re.IGNORECASE)


def chapter_number(url: str) -> int:
    match = _NUMBER_RE.search(urlsplit(url).path)
    if match is None:
        raise ParseError(f"URL de capítulo inválida: {url}")
    return int(match.group(1))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def parse_chapter_page(html: str, url: str) -> dict:
    number = chapter_number(url)
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one("header h1.header-title")
    if title_node is None:
        raise ParseError(f"Título ausente: {url}")
    title = _clean_text(title_node.get_text(" ", strip=True))
    if not re.fullmatch(rf"Chapter\s+0*{number}(?:\b.*)?", title, re.IGNORECASE):
        raise ParseError(f"Título inesperado para capítulo {number}: {title!r}")

    content = soup.select_one("#chapterContent")
    if content is None:
        raise ParseError(f"Contêiner de texto ausente: {url}")
    # O HTML entregue por requests contém o contêiner vazio. O leitor o preenche
    # a partir desta string codificada, que já está na resposta da página.
    match = _CONTENT_RE.search(html)
    if match:
        try:
            decoded = base64.b64decode(re.sub(r"\s+", "", match.group(2)), validate=True).decode("utf-8")
        except (ValueError, UnicodeError) as exc:
            raise ParseError(f"Texto codificado inválido: {url}") from exc
        paragraphs = [_clean_text(part) for part in decoded.splitlines() if part.strip()]
    else:
        # Também aceita HTML salvo depois da execução do JavaScript no navegador.
        paragraphs = [_clean_text(node.get_text("", strip=False)) for node in content.select("p")]
    paragraphs = [part for part in paragraphs if part]
    if not paragraphs:
        raise ParseError(f"Capítulo sem parágrafos: {url}")
    return {"url": url, "title": title, "paragraphs": paragraphs, "source_page": number}

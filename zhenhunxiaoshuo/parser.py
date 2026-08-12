from bs4 import BeautifulSoup
from .models import Chapter

TITLE_SELECTOR = "h1.article-title"
LEAD_SELECTOR = "article.article-content > p:first-child"
PARAGRAPH_SELECTOR = "article.article-content > p:not(:first-child)"

class ParseError(ValueError):
    pass

def parse_chapter(html: str, source_url: str, csv_title: str) -> Chapter:
    soup = BeautifulSoup(html, "html.parser")

    title_node = soup.select_one(TITLE_SELECTOR)
    lead_node = soup.select_one(LEAD_SELECTOR)
    paragraph_nodes = soup.select(PARAGRAPH_SELECTOR)

    if title_node is None:
        raise ParseError(f"Título não encontrado: {source_url}")
    if lead_node is None:
        raise ParseError(f"Título + frase de efeito não encontrado: {source_url}")
    if not paragraph_nodes:
        raise ParseError(f"Parágrafos da história não encontrados: {source_url}")

    return Chapter(
        source_url=source_url,
        csv_title=csv_title,
        chapter_title=title_node.get_text(" ", strip=True),
        chapter_lead=lead_node.get_text(" ", strip=True),
        paragraphs=[
            node.get_text(" ", strip=True)
            for node in paragraph_nodes
            if node.get_text(" ", strip=True)
        ],
    )

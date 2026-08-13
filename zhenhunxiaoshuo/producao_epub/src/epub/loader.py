import json
from pathlib import Path
from .models import EpubBook, EpubChapter

class EpubInputError(ValueError):
    pass

def load_book_from_json(json_path, *, title, author="", language="pt-BR",
                        cover_path=None, identifier=None):
    path = Path(json_path)
    if not path.is_file():
        raise EpubInputError(f"JSON não encontrado: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("chapters")
    if not isinstance(rows, list) or not rows:
        raise EpubInputError("JSON sem lista válida em 'chapters'.")

    chapters = []
    for pos, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise EpubInputError(f"Capítulo {pos}: objeto inválido.")

        chapter_title = row.get("epub_title", row.get("chapter_title", ""))
        chapter_intro = row.get("epub_intro", row.get("chapter_lead", ""))
        paragraphs = row.get("epub_paragraphs", row.get("paragraphs", []))

        if not isinstance(chapter_title, str) or not chapter_title.strip():
            raise EpubInputError(f"Capítulo {pos}: título ausente.")
        if not isinstance(chapter_intro, str):
            raise EpubInputError(f"Capítulo {pos}: intro inválida.")
        if not isinstance(paragraphs, list) or not all(isinstance(x, str) for x in paragraphs):
            raise EpubInputError(f"Capítulo {pos}: paragraphs inválido.")

        chapters.append(EpubChapter(
            index=pos,
            title=chapter_title.strip(),
            intro=chapter_intro.strip(),
            paragraphs=[x.strip() for x in paragraphs if x.strip()],
            source_url=str(row.get("source_url", "") or ""),
        ))

    declared = payload.get("chapter_count")
    if declared is not None and int(declared) != len(chapters):
        raise EpubInputError(
            f"chapter_count={declared} difere de {len(chapters)} capítulos carregados."
        )

    cover = Path(cover_path).resolve() if cover_path else None
    if cover is not None and not cover.is_file():
        raise EpubInputError(f"Capa não encontrada: {cover}")

    if not str(title).strip():
        raise EpubInputError("Título do livro é obrigatório.")

    return EpubBook(
        title=str(title).strip(),
        author=str(author).strip(),
        language=str(language).strip() or "pt-BR",
        chapters=chapters,
        cover_path=cover,
        identifier=identifier,
    )

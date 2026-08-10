import re
import uuid
from pathlib import Path
from typing import List, Tuple

from docx import Document
from ebooklib import epub


BOOK_TITLE = "O Tirano que se Ajoelhou por Mim"
BOOK_AUTHORS = ["Yi Jian Shengcai Miao", "Mofa Lingxiao"]
BOOK_ARTIST = "Luming Dongman"
BOOK_LANGUAGE = "pt-BR"
BOOK_IDENTIFIER = str(uuid.uuid4())
BOOK_DESCRIPTION = "Compilação em EPUB dos capítulos traduzidos da novel."
BOOK_PUBLISHER = "Edição pessoal"

INPUT_DIR = Path("Traduzidos")
OUTPUT_FILE = "O_Tirano_que_se_Ajoelhou_por_Mim.epub"


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def html_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def natural_sort_key(path: Path):
    parts = re.split(r"(\d+)", path.name.lower())
    key = []
    for part in parts:
        key.append(int(part) if part.isdigit() else part)
    return key


def find_cover_image(input_dir: Path) -> Path | None:
    candidates = [
        input_dir / "Capa.jpg",
        input_dir / "Capa.jpeg",
        input_dir / "Capa.png",
        input_dir / "capa.jpg",
        input_dir / "capa.jpeg",
        input_dir / "capa.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    for path in sorted(input_dir.iterdir(), key=natural_sort_key):
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            return path
    return None


def get_docx_files(input_dir: Path) -> List[Path]:
    files = [p for p in input_dir.iterdir() if p.suffix.lower() == ".docx"]
    return sorted(files, key=natural_sort_key)


def is_range_heading(text: str) -> bool:
    text = clean_text(text)
    if not text:
        return False

    patterns = [
        r"^Romance Capítulos \d+ a \d+$",
        r"^Novel Capítulos \d+ a \d+$",
        r"^Capítulos \d+ a \d+$",
    ]
    return any(re.match(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def is_chapter_title(text: str) -> bool:
    text = clean_text(text)
    return bool(re.match(r"^Capítulo\s+\d+\b", text, flags=re.IGNORECASE))


def extract_chapters_from_docx(docx_path: Path) -> List[Tuple[str, List[str]]]:
    document = Document(str(docx_path))
    paragraphs = [p.text for p in document.paragraphs]

    chapters: List[Tuple[str, List[str]]] = []
    current_title: str | None = None
    current_body: List[str] = []

    for raw in paragraphs:
        text = clean_text(raw)
        if not text:
            continue

        if is_range_heading(text):
            continue

        if is_chapter_title(text):
            if current_title:
                chapters.append((current_title, current_body))
            current_title = text
            current_body = []
            continue

        if current_title:
            current_body.append(text)

    if current_title:
        chapters.append((current_title, current_body))

    return chapters


def create_stylesheet(book: epub.EpubBook) -> epub.EpubItem:
    css = '''
    body {
        font-family: serif;
        line-height: 1.6;
        margin: 5%;
    }
    h1 {
        text-align: center;
        margin-top: 1.2em;
        margin-bottom: 1.2em;
    }
    p {
        text-indent: 1.5em;
        margin: 0.55em 0;
    }
    .title-page {
        text-align: center;
        margin-top: 25%;
    }
    .title-page h1 {
        margin-bottom: 0.6em;
    }
    .title-page p {
        text-indent: 0;
        margin: 0.3em 0;
    }
    '''
    item = epub.EpubItem(
        uid="style_main",
        file_name="style/style.css",
        media_type="text/css",
        content=css.encode("utf-8"),
    )
    book.add_item(item)
    return item


def add_metadata(book: epub.EpubBook) -> None:
    book.set_identifier(BOOK_IDENTIFIER)
    book.set_title(BOOK_TITLE)
    book.set_language(BOOK_LANGUAGE)

    for author in BOOK_AUTHORS:
        book.add_author(author)

    book.add_metadata("DC", "publisher", BOOK_PUBLISHER)
    book.add_metadata("DC", "description", BOOK_DESCRIPTION)
    book.add_metadata("DC", "contributor", BOOK_ARTIST, {"role": "art"})


def add_cover(book: epub.EpubBook, cover_path: Path | None) -> None:
    if not cover_path:
        print("Aviso: nenhuma capa encontrada. O EPUB será gerado sem capa.")
        return

    with open(cover_path, "rb") as f:
        content = f.read()

    ext = cover_path.suffix.lower()
    cover_name = "cover.jpg" if ext in {".jpg", ".jpeg"} else "cover.png"
    book.set_cover(cover_name, content)


def create_title_page(book: epub.EpubBook, css_item: epub.EpubItem) -> epub.EpubHtml:
    title_page = epub.EpubHtml(
        title="Página de rosto",
        file_name="title_page.xhtml",
        lang=BOOK_LANGUAGE,
    )
    title_page.add_item(css_item)
    title_page.set_content(
        f'''<html xmlns="http://www.w3.org/1999/xhtml" lang="{BOOK_LANGUAGE}" xml:lang="{BOOK_LANGUAGE}">
<head>
  <title>{html_escape(BOOK_TITLE)}</title>
  <link rel="stylesheet" type="text/css" href="style/style.css"/>
</head>
<body>
  <div class="title-page">
    <h1>{html_escape(BOOK_TITLE)}</h1>
    <p><strong>Autores:</strong> {html_escape(" & ".join(BOOK_AUTHORS))}</p>
    <p><strong>Arte:</strong> {html_escape(BOOK_ARTIST)}</p>
  </div>
</body>
</html>'''
    )
    book.add_item(title_page)
    return title_page


def create_chapter_item(index: int, title: str, paragraphs: List[str], css_item: epub.EpubItem) -> epub.EpubHtml:
    chapter = epub.EpubHtml(
        title=title,
        file_name=f"chap_{index:03}.xhtml",
        lang=BOOK_LANGUAGE,
    )
    chapter.add_item(css_item)

    body_parts = [f"<h1>{html_escape(title)}</h1>"]
    for paragraph in paragraphs:
        body_parts.append(f"<p>{html_escape(paragraph)}</p>")

    chapter.set_content(
        f'''<html xmlns="http://www.w3.org/1999/xhtml" lang="{BOOK_LANGUAGE}" xml:lang="{BOOK_LANGUAGE}">
<head>
  <title>{html_escape(title)}</title>
  <link rel="stylesheet" type="text/css" href="style/style.css"/>
</head>
<body>
  {''.join(body_parts)}
</body>
</html>'''
    )
    return chapter


def build_epub(input_dir: Path, output_file: Path) -> None:
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Pasta não encontrada: {input_dir.resolve()}")

    docx_files = get_docx_files(input_dir)
    if not docx_files:
        raise FileNotFoundError(f"Nenhum .docx encontrado em: {input_dir.resolve()}")

    all_chapters: List[Tuple[str, List[str]]] = []
    for docx_path in docx_files:
        print(f"Lendo: {docx_path.name}")
        extracted = extract_chapters_from_docx(docx_path)
        if not extracted:
            print(f"  Aviso: nenhum capítulo detectado em {docx_path.name}")
        else:
            print(f"  OK: {len(extracted)} capítulos encontrados")
            all_chapters.extend(extracted)

    if not all_chapters:
        raise RuntimeError("Nenhum capítulo foi extraído dos arquivos DOCX.")

    book = epub.EpubBook()
    add_metadata(book)

    css_item = create_stylesheet(book)
    add_cover(book, find_cover_image(input_dir))
    title_page = create_title_page(book, css_item)

    epub_chapters = []
    for idx, (title, paragraphs) in enumerate(all_chapters, start=1):
        item = create_chapter_item(idx, title, paragraphs, css_item)
        book.add_item(item)
        epub_chapters.append(item)

    book.toc = (epub.Link("title_page.xhtml", "Página de rosto", "title_page"),) + tuple(epub_chapters)
    book.add_item(epub.EpubNav())
    book.add_item(epub.EpubNcx())
    book.spine = ["nav", title_page] + epub_chapters

    epub.write_epub(str(output_file), book, {})
    print(f"\nEPUB gerado com sucesso: {output_file.resolve()}")
    print(f"Total de capítulos no EPUB: {len(epub_chapters)}")


def main() -> None:
    output_path = Path(OUTPUT_FILE)
    build_epub(INPUT_DIR, output_path)


if __name__ == "__main__":
    main()

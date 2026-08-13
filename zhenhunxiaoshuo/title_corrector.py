import csv
import html
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TRANSLATED_EPUB_DIR = ROOT / "input" / "translated_epub"
TITLE_CSV_DIR = ROOT / "input" / "title_csv"
OUTPUT_DIR = ROOT / "output" / "epub_corrected"


def load_title_map(csv_path):
    """
    Usa:
      Capítulo       -> número do capítulo
      Título no DOCX -> título final desejado

    Linhas sem número ou sem Título no DOCX são ignoradas.
    """
    csv_path = Path(csv_path)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)

        delimiter = ";" if sample.count(";") >= sample.count(",") else ","
        reader = csv.DictReader(f, delimiter=delimiter)

        required = {"Capítulo", "Título no DOCX"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(
                "CSV deve conter as colunas 'Capítulo' e 'Título no DOCX'."
            )

        mapping = {}

        for row in reader:
            raw_number = (row.get("Capítulo") or "").strip()
            target_title = (row.get("Título no DOCX") or "").strip()

            if not raw_number.isdigit():
                continue
            if not target_title:
                continue

            mapping[int(raw_number)] = target_title

    return mapping


def build_full_title(chapter_number, title):
    return f"Capítulo {chapter_number} - {title}"


def _replace_first_tag_text(text, tag, new_value):
    escaped = html.escape(new_value, quote=False)
    pattern = re.compile(
        rf"(<{tag}\b[^>]*>)(.*?)(</{tag}>)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    return pattern.sub(
        lambda m: m.group(1) + escaped + m.group(3),
        text,
        count=1,
    )


def _chapter_number_from_path(path):
    match = re.search(r"chapter_(\d+)\.xhtml$", path, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _update_chapter_xhtml(content, chapter_number, desired_title):
    full_title = build_full_title(chapter_number, desired_title)
    updated = _replace_first_tag_text(content, "title", full_title)
    updated = _replace_first_tag_text(updated, "h1", full_title)
    return updated


def _update_nav_xhtml(content, title_map):
    """
    Atualiza links do nav.xhtml usando o número presente no href.
    Ex.: href="Text/chapter_001.xhtml"
    """
    pattern = re.compile(
        r'(<a\b[^>]*href=["\'][^"\']*chapter_(\d+)\.xhtml[^"\']*["\'][^>]*>)'
        r'(.*?)'
        r'(</a>)',
        flags=re.IGNORECASE | re.DOTALL,
    )

    def repl(match):
        number = int(match.group(2))
        desired = title_map.get(number)
        if not desired:
            return match.group(0)

        full_title = html.escape(
            build_full_title(number, desired),
            quote=False,
        )
        return match.group(1) + full_title + match.group(4)

    return pattern.sub(repl, content)


def _update_toc_ncx(content, title_map):
    """
    Atualiza o <text> dentro do navPoint que aponta para chapter_NNN.xhtml.
    """
    navpoint_pattern = re.compile(
        r"(<navPoint\b.*?</navPoint>)",
        flags=re.IGNORECASE | re.DOTALL,
    )

    def repl_navpoint(match):
        block = match.group(1)

        src_match = re.search(
            r'<content\b[^>]*src=["\'][^"\']*chapter_(\d+)\.xhtml[^"\']*["\']',
            block,
            flags=re.IGNORECASE,
        )
        if not src_match:
            return block

        number = int(src_match.group(1))
        desired = title_map.get(number)
        if not desired:
            return block

        full_title = html.escape(
            build_full_title(number, desired),
            quote=False,
        )

        return re.sub(
            r"(<navLabel\b.*?<text\b[^>]*>)(.*?)(</text>.*?</navLabel>)",
            lambda m: m.group(1) + full_title + m.group(3),
            block,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )

    return navpoint_pattern.sub(repl_navpoint, content)


def correct_epub_titles(epub_path, csv_path, output_path=None):
    epub_path = Path(epub_path)
    csv_path = Path(csv_path)

    if not epub_path.is_file():
        raise FileNotFoundError(f"EPUB não encontrado: {epub_path}")
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV não encontrado: {csv_path}")

    title_map = load_title_map(csv_path)

    if not title_map:
        raise ValueError("Nenhum título aplicável foi encontrado no CSV.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = OUTPUT_DIR / f"{epub_path.stem}_titulos_corrigidos.epub"
    else:
        output_path = Path(output_path)

    corrected_chapters = []
    untouched_chapters = []
    nav_updated = False
    ncx_updated = False

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        with zipfile.ZipFile(epub_path, "r") as zin:
            zin.extractall(tmp)

        chapter_files = sorted(tmp.rglob("chapter_*.xhtml"))

        for chapter_file in chapter_files:
            number = _chapter_number_from_path(chapter_file.name)
            if number is None:
                continue

            desired = title_map.get(number)
            if not desired:
                untouched_chapters.append(number)
                continue

            content = chapter_file.read_text(encoding="utf-8")
            updated = _update_chapter_xhtml(content, number, desired)

            if updated != content:
                chapter_file.write_text(updated, encoding="utf-8")
                corrected_chapters.append(number)

        for nav_file in tmp.rglob("nav.xhtml"):
            content = nav_file.read_text(encoding="utf-8")
            updated = _update_nav_xhtml(content, title_map)
            if updated != content:
                nav_file.write_text(updated, encoding="utf-8")
                nav_updated = True

        for ncx_file in tmp.rglob("toc.ncx"):
            content = ncx_file.read_text(encoding="utf-8")
            updated = _update_toc_ncx(content, title_map)
            if updated != content:
                ncx_file.write_text(updated, encoding="utf-8")
                ncx_updated = True

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(output_path, "w") as zout:
            mimetype = tmp / "mimetype"

            if mimetype.is_file():
                info = zipfile.ZipInfo("mimetype")
                info.compress_type = zipfile.ZIP_STORED
                zout.writestr(info, mimetype.read_bytes())

            for file_path in sorted(tmp.rglob("*")):
                if not file_path.is_file():
                    continue

                rel = file_path.relative_to(tmp).as_posix()

                if rel == "mimetype":
                    continue

                zout.write(
                    file_path,
                    rel,
                    compress_type=zipfile.ZIP_DEFLATED,
                )

    return {
        "output": output_path,
        "titles_in_csv": len(title_map),
        "corrected_chapters": corrected_chapters,
        "corrected_count": len(corrected_chapters),
        "untouched_chapters": untouched_chapters,
        "nav_updated": nav_updated,
        "ncx_updated": ncx_updated,
    }

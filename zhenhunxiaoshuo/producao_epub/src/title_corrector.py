import csv
import html
import posixpath
import re
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_EPUB_DIR = (
    PROJECT_ROOT
    / "producao_epub"
    / "output"
    / "gerados"
    / "sem_redundancia"
)
TRANSLATED_EPUB_DIR = PROJECT_ROOT / "producao_epub" / "input" / "traduzidos"
TITLE_CSV_DIR = PROJECT_ROOT / "producao_epub" / "input" / "capitulos"
OUTPUT_DIR = PROJECT_ROOT / "producao_epub" / "output" / "pos_traducao"

CHAPTER_FILE_RE = re.compile(r"chapter[_-]?(\d+)\.xhtml?$", re.IGNORECASE)
HEADING_RE = re.compile(
    r"(<h1\b[^>]*>)(.*?)(</h1>)",
    re.IGNORECASE | re.DOTALL,
)
TITLE_TAG_RE = re.compile(
    r"(<title\b[^>]*>)(.*?)(</title>)",
    re.IGNORECASE | re.DOTALL,
)
WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+", re.UNICODE)
ANCHOR_STOPWORDS = {
    "a", "as", "o", "os", "um", "uma", "uns", "umas",
    "de", "da", "das", "do", "dos", "em", "na", "nas",
    "no", "nos", "e", "ao", "aos", "capitulo", "capítulo",
}


class StructuralMatchError(ValueError):
    pass


def _detect_delimiter(csv_path):
    sample = Path(csv_path).read_text(
        encoding="utf-8-sig",
        errors="replace",
    )[:8192]

    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t").delimiter
    except csv.Error:
        return ";" if sample.count(";") >= sample.count(",") else ","


def _read_title_csv(csv_path):
    delimiter = _detect_delimiter(csv_path)

    with Path(csv_path).open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        rows = list(reader)

    if not rows:
        raise ValueError("CSV de títulos está vazio.")

    chapter_titles = {}
    special_rows = []

    for row in rows:
        chapter_raw = str(row.get("Capítulo") or "").strip()
        docx_title = str(row.get("Título no DOCX") or "").strip()

        if chapter_raw.isdigit():
            number = int(chapter_raw)
            chapter_titles[number] = docx_title or None
        else:
            special_rows.append(row)

    return {
        "delimiter": delimiter,
        "rows": rows,
        "chapter_titles": chapter_titles,
        "special_rows": special_rows,
        "numbered_rows": [
            row
            for row in rows
            if str(row.get("Capítulo") or "").strip().isdigit()
        ],
    }


def build_full_title(number, title):
    title = str(title or "").strip()
    return f"Capítulo {number} - {title}" if title else f"Capítulo {number}"


def load_title_map(csv_path):
    data = _read_title_csv(csv_path)
    return {
        number: build_full_title(number, title)
        for number, title in data["chapter_titles"].items()
        if title
    }


def _extract_current_heading_from_text(text, fallback):
    match = HEADING_RE.search(text)
    if not match:
        return fallback

    value = re.sub(r"<[^>]+>", "", match.group(2))
    return html.unescape(value).strip()


def _extract_current_heading(path):
    return _extract_current_heading_from_text(
        path.read_text(encoding="utf-8"),
        path.stem,
    )


def _replace_visible_title(path, new_title):
    text = path.read_text(encoding="utf-8")
    escaped = html.escape(new_title, quote=False)

    updated, heading_count = HEADING_RE.subn(
        lambda match: match.group(1) + escaped + match.group(3),
        text,
        count=1,
    )

    if heading_count == 0:
        raise ValueError(
            f"Título <h1> não encontrado em {path.name}."
        )

    updated, _ = TITLE_TAG_RE.subn(
        lambda match: match.group(1) + escaped + match.group(3),
        updated,
        count=1,
    )

    path.write_text(updated, encoding="utf-8")


def _find_opf_name(archive):
    try:
        container = archive.read("META-INF/container.xml")
    except KeyError as exc:
        raise ValueError("META-INF/container.xml não encontrado no EPUB.") from exc

    root_el = ET.fromstring(container)
    rootfile = next(
        (
            node
            for node in root_el.iter()
            if node.tag.endswith("rootfile")
        ),
        None,
    )

    if rootfile is None:
        raise ValueError("rootfile não encontrado em container.xml.")

    full_path = rootfile.attrib.get("full-path")
    if not full_path:
        raise ValueError("full-path ausente em container.xml.")

    if full_path not in archive.namelist():
        raise ValueError(f"OPF não encontrado: {full_path}")

    return full_path


def _resolve_href(opf_name, href):
    base = posixpath.dirname(opf_name)
    return posixpath.normpath(posixpath.join(base, href))


def _epub_structure(epub_path):
    epub_path = Path(epub_path)

    with zipfile.ZipFile(epub_path, "r") as archive:
        names = set(archive.namelist())
        opf_name = _find_opf_name(archive)
        package = ET.fromstring(archive.read(opf_name))

        manifest = next(
            (node for node in package if node.tag.endswith("manifest")),
            None,
        )
        spine = next(
            (node for node in package if node.tag.endswith("spine")),
            None,
        )

        if manifest is None or spine is None:
            raise ValueError("manifest/spine não encontrados no OPF.")

        href_by_id = {}
        for item in manifest:
            if not item.tag.endswith("item"):
                continue

            item_id = item.attrib.get("id")
            href = item.attrib.get("href")

            if item_id and href:
                href_by_id[item_id] = _resolve_href(opf_name, href)

        spine_chapters = []
        missing_spine_hrefs = []
        for itemref in spine:
            if not itemref.tag.endswith("itemref"):
                continue

            href = href_by_id.get(itemref.attrib.get("idref"))
            if not href:
                continue

            if CHAPTER_FILE_RE.search(Path(href).name):
                if href not in names:
                    missing_spine_hrefs.append(href)
                spine_chapters.append(href)

        chapter_documents = sorted(
            (
                name for name in names
                if CHAPTER_FILE_RE.search(Path(name).name)
            ),
            key=lambda name: int(CHAPTER_FILE_RE.search(Path(name).name).group(1)),
        )

        headings = {}
        for name in chapter_documents:
            text = archive.read(name).decode("utf-8", errors="replace")
            headings[name] = _extract_current_heading_from_text(
                text,
                Path(name).stem,
            )

    return {
        "path": epub_path,
        "chapter_documents": chapter_documents,
        "spine_chapters": spine_chapters,
        "missing_spine_hrefs": missing_spine_hrefs,
        "headings": headings,
    }


def _ensure_spine_matches_documents(structure, label):
    documents = [Path(name).name for name in structure["chapter_documents"]]
    spine = [Path(name).name for name in structure["spine_chapters"]]

    if structure["missing_spine_hrefs"]:
        missing = ", ".join(structure["missing_spine_hrefs"][:3])
        raise StructuralMatchError(
            "ERRO: o EPUB traduzido não possui correspondência estrutural "
            "1:1 com o EPUB original.\n"
            f"{label}: XHTML referenciado no spine não encontrado: {missing}"
        )

    if len(documents) != len(spine):
        raise StructuralMatchError(
            "ERRO: o EPUB traduzido não possui correspondência estrutural "
            "1:1 com o EPUB original.\n"
            f"{label}: documentos={len(documents)} spine={len(spine)}"
        )

    if documents != spine:
        for index, (doc, item) in enumerate(zip(documents, spine), start=1):
            if doc != item:
                raise StructuralMatchError(
                    "ERRO: o EPUB traduzido não possui correspondência "
                    "estrutural 1:1 com o EPUB original.\n"
                    f"{label}: divergência de ordem na posição {index}: "
                    f"documento={doc} spine={item}"
                )


def validate_structural_match(original_epub_path, translated_epub_path):
    original = _epub_structure(original_epub_path)
    translated = _epub_structure(translated_epub_path)

    _ensure_spine_matches_documents(original, "Original")
    _ensure_spine_matches_documents(translated, "Traduzido")

    original_names = [Path(name).name for name in original["spine_chapters"]]
    translated_names = [Path(name).name for name in translated["spine_chapters"]]

    if len(original_names) != len(translated_names):
        raise StructuralMatchError(
            "ERRO: o EPUB traduzido não possui correspondência estrutural "
            "1:1 com o EPUB original.\n"
            f"Original: {len(original_names)} capítulos\n"
            f"Traduzido: {len(translated_names)} capítulos"
        )

    for index, (original_name, translated_name) in enumerate(
        zip(original_names, translated_names),
        start=1,
    ):
        if original_name != translated_name:
            raise StructuralMatchError(
                "ERRO: o EPUB traduzido não possui correspondência estrutural "
                "1:1 com o EPUB original.\n"
                f"Divergência encontrada na posição {index}:\n"
                f"Original: {original_name}\n"
                f"Traduzido: {translated_name}"
            )

    return {
        "chapter_count": len(original_names),
        "original": original,
        "translated": translated,
    }


def _normalize_anchor_words(text):
    normalized = html.unescape(str(text or "")).lower()
    normalized = normalized.replace("_", " ").replace("-", " ")
    return {
        word
        for word in WORD_RE.findall(normalized)
        if len(word) > 2 and word not in ANCHOR_STOPWORDS
    }


def _normalize_title_anchor(text):
    normalized = html.unescape(str(text or "")).lower()
    normalized = re.sub(r"\[[^\]]+\]", " ", normalized)
    normalized = normalized.replace("(", " ").replace(")", " ")
    normalized = normalized.replace("_", " ").replace("-", " ")
    normalized = re.sub(r"\bcap[ií]tulo\b", " ", normalized)
    normalized = re.sub(r"\bextra\b", " ", normalized)
    normalized = re.sub(r"\b[0-9]+\b", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    words = [
        word
        for word in WORD_RE.findall(normalized)
        if word not in ANCHOR_STOPWORDS
    ]
    return " ".join(words)


def _extract_visible_chapter_number(title):
    match = re.search(r"\bcap[ií]tulo\s+([0-9]+)\b", str(title or ""), re.I)
    if match:
        return int(match.group(1))
    return None


def _looks_like_extra_title(title):
    text = str(title or "").lower()
    return "extra" in text or "bônus" in text or "bonus" in text


def _csv_epub_anchor_matches(csv_title, current_title):
    csv_anchor = _normalize_title_anchor(csv_title)
    current_anchor = _normalize_title_anchor(current_title)

    if not csv_anchor or not current_anchor:
        return False

    return (
        csv_anchor == current_anchor
        or csv_anchor in current_anchor
    )


def _find_csv_row_for_title(numbered_rows, current_title, start_index):
    candidates = []
    current_number = _extract_visible_chapter_number(current_title)

    for index, row in enumerate(numbered_rows[start_index:], start=start_index):
        csv_epub_title = str(row.get("Título no EPUB") or "").strip()
        if not _csv_epub_anchor_matches(csv_epub_title, current_title):
            continue

        csv_chapter = int(str(row.get("Capítulo") or "").strip())
        candidates.append((index, row, csv_chapter))

    if not candidates:
        raise StructuralMatchError(
            "ERRO: nenhuma correspondência confiável foi encontrada no CSV "
            "de comparação.\n"
            f"EPUB traduzido: {current_title}"
        )

    ranked_candidates = sorted(
        candidates,
        key=lambda candidate: len(
            _normalize_title_anchor(candidate[1].get("Título no EPUB")).split()
        ),
        reverse=True,
    )
    best_score = len(
        _normalize_title_anchor(ranked_candidates[0][1].get("Título no EPUB")).split()
    )
    best_candidates = [
        candidate
        for candidate in ranked_candidates
        if len(
            _normalize_title_anchor(candidate[1].get("Título no EPUB")).split()
        ) == best_score
    ]
    if current_number is not None:
        numbered_candidates = [
            candidate
            for candidate in best_candidates
            if candidate[2] == current_number
        ]
        if len(numbered_candidates) == 1:
            return numbered_candidates[0][0], numbered_candidates[0][1]

    if len(best_candidates) == 1:
        return best_candidates[0][0], best_candidates[0][1]
    best_anchors = {
        _normalize_title_anchor(candidate[1].get("Título no EPUB"))
        for candidate in best_candidates
    }
    if len(best_anchors) == 1:
        first_best = min(best_candidates, key=lambda candidate: candidate[0])
        return first_best[0], first_best[1]

    first_index, first_row, _ = candidates[0]
    same_anchor_run = [candidates[0]]
    first_anchor = _normalize_title_anchor(first_row.get("Título no EPUB"))

    for candidate in candidates[1:]:
        index, row, _ = candidate
        if index != same_anchor_run[-1][0] + 1:
            break
        if _normalize_title_anchor(row.get("Título no EPUB")) != first_anchor:
            break
        same_anchor_run.append(candidate)

    if len(same_anchor_run) == len(candidates):
        return first_index, first_row

    preview = ", ".join(
        f"{candidate[2]}:{candidate[1].get('Título no EPUB')}"
        for candidate in candidates[:5]
    )
    raise StructuralMatchError(
        "ERRO: mais de uma correspondência plausível foi encontrada no CSV "
        "de comparação.\n"
        f"EPUB traduzido: {current_title}\n"
        f"Candidatas: {preview}"
    )


def _build_title_mapping(validation, csv_data, translated_root):
    numbered_rows = csv_data["numbered_rows"]
    mapping = []
    next_csv_index = 0

    for position, (original_name, translated_name) in enumerate(zip(
        validation["original"]["spine_chapters"],
        validation["translated"]["spine_chapters"],
    ), start=1):
        original_title = validation["original"]["headings"].get(
            original_name,
            Path(original_name).stem,
        )
        translated_path = translated_root / translated_name
        current_title = _extract_current_heading(translated_path)
        search_start = 0 if _looks_like_extra_title(current_title) else next_csv_index
        csv_index, csv_row = _find_csv_row_for_title(
            numbered_rows,
            current_title,
            search_start,
        )
        if not _looks_like_extra_title(current_title):
            next_csv_index = csv_index + 1
        csv_epub_title = str(csv_row.get("Título no EPUB") or "").strip()
        editorial_title = str(csv_row.get("Título no DOCX") or "").strip()
        csv_chapter = int(str(csv_row.get("Capítulo") or "").strip())

        new_title = (
            build_full_title(csv_chapter, editorial_title)
            if editorial_title
            else current_title
        )

        mapping.append({
            "position": position,
            "filename": Path(translated_name).name,
            "href": translated_name,
            "xhtml": translated_path,
            "original_title": original_title,
            "csv_chapter": csv_chapter,
            "csv_index": csv_index,
            "csv_epub_title": csv_epub_title,
            "current_title": current_title,
            "new_title": new_title,
        })

    return mapping


def _update_nav_titles(root, mapping):
    title_by_filename = {
        entry["filename"]: entry["new_title"]
        for entry in mapping
    }
    updated = False

    for nav_path in root.rglob("nav.xhtml"):
        tree = ET.parse(nav_path)
        doc = tree.getroot()
        changed = False

        for anchor in doc.iter():
            if not anchor.tag.endswith("a"):
                continue

            href = anchor.attrib.get("href", "").split("#", 1)[0]
            filename = Path(href).name
            title = title_by_filename.get(filename)

            if title and anchor.text != title:
                anchor.text = title
                changed = True

        if changed:
            tree.write(nav_path, encoding="utf-8", xml_declaration=True)
            updated = True

    return updated


def _update_ncx_titles(root, mapping):
    title_by_filename = {
        entry["filename"]: entry["new_title"]
        for entry in mapping
    }
    updated = False

    for ncx_path in root.rglob("toc.ncx"):
        tree = ET.parse(ncx_path)
        doc = tree.getroot()
        changed = False

        for navpoint in doc.iter():
            if not navpoint.tag.endswith("navPoint"):
                continue

            content = next(
                (
                    node
                    for node in navpoint.iter()
                    if node.tag.endswith("content")
                ),
                None,
            )
            label = next(
                (
                    node
                    for node in navpoint.iter()
                    if node.tag.endswith("text")
                ),
                None,
            )

            if content is None or label is None:
                continue

            filename = Path(content.attrib.get("src", "").split("#", 1)[0]).name
            title = title_by_filename.get(filename)

            if title and label.text != title:
                label.text = title
                changed = True

        if changed:
            tree.write(ncx_path, encoding="utf-8", xml_declaration=True)
            updated = True

    return updated


def _pack_epub(root, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w") as archive:
        mimetype = root / "mimetype"

        if mimetype.is_file():
            archive.write(
                mimetype,
                "mimetype",
                compress_type=zipfile.ZIP_STORED,
            )

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue

            relative = path.relative_to(root).as_posix()

            if relative == "mimetype":
                continue

            archive.write(
                path,
                relative,
                compress_type=zipfile.ZIP_DEFLATED,
            )


def correct_epub_titles(original_epub_path, translated_epub_path, csv_path):
    original_epub_path = Path(original_epub_path)
    translated_epub_path = Path(translated_epub_path)
    csv_path = Path(csv_path)

    csv_data = _read_title_csv(csv_path)
    validation = validate_structural_match(
        original_epub_path,
        translated_epub_path,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        with zipfile.ZipFile(translated_epub_path, "r") as archive:
            archive.extractall(root)

        mapping = _build_title_mapping(validation, csv_data, root)
        changed_titles = 0

        for entry in mapping:
            if entry["new_title"] != entry["current_title"]:
                _replace_visible_title(
                    entry["xhtml"],
                    entry["new_title"],
                )
                changed_titles += 1

        nav_updated = _update_nav_titles(root, mapping)
        ncx_updated = _update_ncx_titles(root, mapping)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        output = (
            OUTPUT_DIR
            / f"{translated_epub_path.stem}_titulos_corrigidos.epub"
        )

        _pack_epub(root, output)

    return {
        "output": output,
        "delimiter": csv_data["delimiter"],
        "titles_in_csv": len(csv_data["rows"]),
        "mapped_entries": len(mapping),
        "chapter_count": validation["chapter_count"],
        "corrected_count": changed_titles,
        "spine_preserved": True,
        "nav_updated": nav_updated,
        "ncx_updated": ncx_updated,
        "original_epub": original_epub_path,
        "translated_epub": translated_epub_path,
    }

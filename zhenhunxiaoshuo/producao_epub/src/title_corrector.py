import csv
import json
import html
import re
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRANSLATED_EPUB_DIR = PROJECT_ROOT / "producao_epub" / "input" / "traduzidos"
TITLE_CSV_DIR = PROJECT_ROOT / "producao_epub" / "input" / "capitulos"
JSON_DIR = PROJECT_ROOT / "manipulacao_json" / "output" / "revisados"
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


def _detect_delimiter(csv_path):
    sample = Path(csv_path).read_text(
        encoding="utf-8-sig",
        errors="replace",
    )[:8192]

    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\\t,").delimiter
    except csv.Error:
        # O CSV usado neste projeto normalmente é separado por ponto-e-vírgula.
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


def _ordered_mapping(rows, chapter_files):
    mapping = []
    for index, row in enumerate(rows):
        source_position = str(row.get("source_position") or "").strip()
        if source_position.isdigit():
            file_index = int(source_position) - 1
        else:
            file_index = index

        if not 0 <= file_index < len(chapter_files):
            continue

        mapping.append({
            "row": row,
            "file": chapter_files[file_index],
        })

    return mapping


def _load_adjusted_json(json_path):
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))

    chapters = data.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        raise ValueError(
            "JSON ajustado inválido: campo 'chapters' ausente ou vazio."
        )

    if not any("corrected_position" in chapter for chapter in chapters):
        raise ValueError(
            "O JSON selecionado não possui 'corrected_position'. "
            "Use primeiro 'Ajustar JSON com referência física'."
        )

    return data


def _chapter_files(root):
    result = []

    for path in root.rglob("*.xhtml"):
        match = CHAPTER_FILE_RE.search(path.name)
        if match:
            result.append((int(match.group(1)), path))

    result.sort(key=lambda item: item[0])
    return [path for _, path in result]


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


def _extract_current_heading(path):
    text = path.read_text(encoding="utf-8")
    match = HEADING_RE.search(text)

    if not match:
        return path.stem

    # Remove tags residuais simples, se houver.
    value = re.sub(r"<[^>]+>", "", match.group(2))
    return html.unescape(value).strip()


def _build_structural_mapping(adjusted_json, chapter_files, csv_data):
    chapters = adjusted_json["chapters"]

    if len(chapter_files) < len(chapters):
        raise ValueError(
            "O EPUB possui menos arquivos de capítulo do que o JSON ajustado: "
            f"EPUB={len(chapter_files)} JSON={len(chapters)}."
        )

    title_by_story_number = csv_data["chapter_titles"]
    mapping = []

    for entry in chapters:
        source_position = entry.get("source_position")
        corrected_position = entry.get("corrected_position")
        chapter_type = entry.get("chapter_type")
        story_number = entry.get("story_chapter_number")

        if not isinstance(source_position, int):
            raise ValueError(
                "JSON ajustado contém entrada sem source_position válido."
            )

        if not isinstance(corrected_position, int):
            raise ValueError(
                "JSON ajustado contém entrada sem corrected_position válido."
            )

        # O EPUB traduzido é gerado a partir do JSON já ajustado.
        # Portanto, sua posição física corresponde a corrected_position,
        # não à source_position original do site.
        if not 1 <= corrected_position <= len(chapter_files):
            raise ValueError(
                f"corrected_position fora do EPUB: {corrected_position}"
            )

        xhtml = chapter_files[corrected_position - 1]
        current_title = _extract_current_heading(xhtml)

        new_title = None

        if chapter_type == "chapter" and isinstance(story_number, int):
            editorial_title = title_by_story_number.get(story_number)

            if editorial_title:
                new_title = f"Capítulo {story_number} - {editorial_title}"

        # Quando não existe título editorial no DOCX (por exemplo capítulos
        # posteriores ou extras), o título traduzido atual é preservado.
        if not new_title:
            new_title = current_title

        mapping.append(
            {
                "source_position": source_position,
                "corrected_position": corrected_position,
                "chapter_type": chapter_type,
                "story_chapter_number": story_number,
                "xhtml": xhtml,
                "filename": xhtml.name,
                "current_title": current_title,
                "new_title": new_title,
            }
        )

    mapping.sort(key=lambda item: item["corrected_position"])
    return mapping


def _find_opf(root):
    container = root / "META-INF" / "container.xml"

    if not container.is_file():
        raise ValueError("META-INF/container.xml não encontrado no EPUB.")

    tree = ET.parse(container)
    root_el = tree.getroot()

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

    opf = root / full_path
    if not opf.is_file():
        raise ValueError(f"OPF não encontrado: {full_path}")

    return opf


def _reorder_opf_spine(root, mapping):
    opf = _find_opf(root)
    tree = ET.parse(opf)
    package = tree.getroot()

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
    id_by_filename = {}

    for item in manifest:
        if not item.tag.endswith("item"):
            continue

        item_id = item.attrib.get("id")
        href = item.attrib.get("href")

        if item_id and href:
            href_by_id[item_id] = href
            id_by_filename[Path(href).name] = item_id

    desired_ids = []

    for entry in mapping:
        item_id = id_by_filename.get(entry["filename"])
        if item_id:
            desired_ids.append(item_id)

    if not desired_ids:
        raise ValueError(
            "Nenhum chapter XHTML do JSON foi localizado no manifest OPF."
        )

    desired_set = set(desired_ids)
    itemrefs = list(spine)
    chapter_slots = [
        index
        for index, itemref in enumerate(itemrefs)
        if itemref.attrib.get("idref") in desired_set
    ]

    if len(chapter_slots) != len(desired_ids):
        raise ValueError(
            "Quantidade de capítulos no spine não corresponde ao mapeamento "
            f"estrutural: spine={len(chapter_slots)} mapa={len(desired_ids)}."
        )

    by_idref = {
        itemref.attrib.get("idref"): itemref
        for itemref in itemrefs
        if itemref.attrib.get("idref")
    }

    for slot, desired_id in zip(chapter_slots, desired_ids):
        spine.remove(itemrefs[slot])
        spine.insert(slot, by_idref[desired_id])

    tree.write(opf, encoding="utf-8", xml_declaration=True)
    return True


def _reorder_nav(root, mapping):
    title_by_filename = {
        entry["filename"]: entry["new_title"]
        for entry in mapping
    }
    desired_filenames = [
        entry["filename"]
        for entry in mapping
    ]

    updated = False

    for nav_path in root.rglob("nav.xhtml"):
        tree = ET.parse(nav_path)
        doc = tree.getroot()

        nav_node = None

        for node in doc.iter():
            if not node.tag.endswith("nav"):
                continue

            attrs = " ".join(
                f"{key}={value}"
                for key, value in node.attrib.items()
            )

            if "toc" in attrs:
                nav_node = node
                break

        if nav_node is None:
            continue

        ol = next(
            (node for node in nav_node if node.tag.endswith("ol")),
            None,
        )
        if ol is None:
            continue

        children = list(ol)
        chapter_items = {}
        chapter_slots = []

        for index, li in enumerate(children):
            anchor = next(
                (node for node in li.iter() if node.tag.endswith("a")),
                None,
            )
            if anchor is None:
                continue

            href = anchor.attrib.get("href", "").split("#", 1)[0]
            filename = Path(href).name

            if filename in title_by_filename:
                chapter_items[filename] = li
                chapter_slots.append(index)
                anchor.text = title_by_filename[filename]

        desired = [
            chapter_items[name]
            for name in desired_filenames
            if name in chapter_items
        ]

        if chapter_slots and len(desired) == len(chapter_slots):
            for slot, li in zip(chapter_slots, desired):
                ol.remove(children[slot])
                ol.insert(slot, li)

        tree.write(nav_path, encoding="utf-8", xml_declaration=True)
        updated = True

    return updated


def _reorder_ncx(root, mapping):
    title_by_filename = {
        entry["filename"]: entry["new_title"]
        for entry in mapping
    }
    desired_filenames = [
        entry["filename"]
        for entry in mapping
    ]

    updated = False

    for ncx_path in root.rglob("toc.ncx"):
        tree = ET.parse(ncx_path)
        doc = tree.getroot()

        nav_map = next(
            (node for node in doc.iter() if node.tag.endswith("navMap")),
            None,
        )
        if nav_map is None:
            continue

        children = list(nav_map)
        chapter_points = {}
        chapter_slots = []

        for index, navpoint in enumerate(children):
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

            if content is None:
                continue

            src = content.attrib.get("src", "").split("#", 1)[0]
            filename = Path(src).name

            if filename in title_by_filename:
                chapter_points[filename] = navpoint
                chapter_slots.append(index)

                if label is not None:
                    label.text = title_by_filename[filename]

        desired = [
            chapter_points[name]
            for name in desired_filenames
            if name in chapter_points
        ]

        if chapter_slots and len(desired) == len(chapter_slots):
            for slot, navpoint in zip(chapter_slots, desired):
                nav_map.remove(children[slot])
                nav_map.insert(slot, navpoint)

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


def correct_epub_titles(epub_path, csv_path, adjusted_json_path):
    epub_path = Path(epub_path)
    csv_path = Path(csv_path)
    adjusted_json_path = Path(adjusted_json_path)

    csv_data = _read_title_csv(csv_path)
    adjusted_json = _load_adjusted_json(adjusted_json_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        with zipfile.ZipFile(epub_path, "r") as archive:
            archive.extractall(root)

        chapter_files = _chapter_files(root)

        if not chapter_files:
            raise ValueError(
                "Nenhum arquivo chapter_*.xhtml encontrado no EPUB."
            )

        mapping = _build_structural_mapping(
            adjusted_json,
            chapter_files,
            csv_data,
        )

        changed_titles = 0

        for entry in mapping:
            if entry["new_title"] != entry["current_title"]:
                _replace_visible_title(
                    entry["xhtml"],
                    entry["new_title"],
                )
                changed_titles += 1

        spine_updated = _reorder_opf_spine(root, mapping)
        nav_updated = _reorder_nav(root, mapping)
        ncx_updated = _reorder_ncx(root, mapping)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        output = (
            OUTPUT_DIR
            / f"{epub_path.stem}_titulos_corrigidos.epub"
        )

        _pack_epub(root, output)

    return {
        "output": output,
        "delimiter": csv_data["delimiter"],
        "titles_in_csv": len(csv_data["rows"]),
        "mapped_entries": len(mapping),
        "corrected_count": changed_titles,
        "spine_updated": spine_updated,
        "nav_updated": nav_updated,
        "ncx_updated": ncx_updated,
        "json_used": adjusted_json_path,
    }

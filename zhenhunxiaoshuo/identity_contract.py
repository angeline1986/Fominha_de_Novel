from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

CONTRACT_VERSION = 1
REF_PREFIX = "zhenhun-"

OPF_NS = "http://www.idpf.org/2007/opf"
CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
XHTML_NS = "http://www.w3.org/1999/xhtml"
NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"

ET.register_namespace("", XHTML_NS)
ET.register_namespace("opf", OPF_NS)


class IdentityContractError(ValueError):
    """Raised when the chapter identity contract is broken."""


def build_ref_id(source_url: str | None, fallback_position: int | None = None) -> str:
    source_url = (source_url or "").strip()
    match = re.search(r"/(\d+)\.html(?:[?#].*)?$", source_url)
    if match:
        return f"{REF_PREFIX}{match.group(1)}"

    if source_url:
        digest = hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:12]
        return f"{REF_PREFIX}{digest}"

    if fallback_position is not None:
        return f"{REF_PREFIX}pos-{int(fallback_position):04d}"

    raise IdentityContractError("Não foi possível gerar ref_id sem source_url ou posição.")


def ref_id_to_source_url(ref_id: str) -> str | None:
    match = re.fullmatch(rf"{re.escape(REF_PREFIX)}(\d+)", (ref_id or "").strip())
    if not match:
        return None
    return f"https://www.zhenhunxiaoshuo.com/{match.group(1)}.html"


def apply_identity_to_adjusted_json(data: dict) -> dict:
    """Adds an immutable chapter identity without changing editorial decisions."""
    chapters = data.get("chapters")
    if not isinstance(chapters, list):
        raise IdentityContractError("JSON sem lista 'chapters'.")

    seen: set[str] = set()
    manifest: list[dict] = []

    for index, chapter in enumerate(chapters, start=1):
        ref_id = chapter.get("ref_id") or build_ref_id(
            chapter.get("source_url"),
            chapter.get("source_position") or index,
        )
        if ref_id in seen:
            raise IdentityContractError(f"ref_id duplicado no JSON: {ref_id}")
        seen.add(ref_id)
        chapter["ref_id"] = ref_id

        manifest.append(
            {
                "ref_id": ref_id,
                "sequence": chapter.get("corrected_position", index),
                "source_position": chapter.get("source_position", index),
                "type": chapter.get("chapter_type", "chapter"),
                "story_chapter_number": chapter.get("story_chapter_number"),
                "source_url": chapter.get("source_url"),
            }
        )

    data["identity_contract"] = {
        "version": CONTRACT_VERSION,
        "id_field": "ref_id",
        "sequence_field": "corrected_position",
        "type_field": "chapter_type",
        "total_entries": len(manifest),
        "identity_checksum": identity_checksum(manifest),
        "entries": manifest,
    }
    return data


def identity_checksum(entries: list[dict]) -> str:
    normalized = [
        {
            "ref_id": item.get("ref_id"),
            "sequence": item.get("sequence"),
            "type": item.get("type"),
            "story_chapter_number": item.get("story_chapter_number"),
        }
        for item in entries
    ]
    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_container_opf(zf: zipfile.ZipFile) -> str:
    try:
        container = ET.fromstring(zf.read("META-INF/container.xml"))
    except KeyError as exc:
        raise IdentityContractError("EPUB sem META-INF/container.xml.") from exc

    rootfile = container.find(f".//{{{CONTAINER_NS}}}rootfile")
    if rootfile is None:
        # tolerate documents where namespace parsing differs
        rootfile = next((e for e in container.iter() if e.tag.endswith("rootfile")), None)

    if rootfile is None or not rootfile.get("full-path"):
        raise IdentityContractError("Não foi possível localizar o OPF no EPUB.")

    return rootfile.get("full-path")


def _opf_spine_documents(zf: zipfile.ZipFile) -> tuple[str, list[str]]:
    opf_path = _read_container_opf(zf)
    root = ET.fromstring(zf.read(opf_path))

    manifest = {}
    for item in root.iter():
        if item.tag.endswith("item") and item.get("id") and item.get("href"):
            manifest[item.get("id")] = {
                "href": item.get("href"),
                "media_type": item.get("media-type", ""),
                "properties": item.get("properties", ""),
            }

    opf_dir = PurePosixPath(opf_path).parent
    docs = []
    for itemref in root.iter():
        if not itemref.tag.endswith("itemref"):
            continue
        entry = manifest.get(itemref.get("idref"))
        if not entry:
            continue
        if entry["media_type"] != "application/xhtml+xml":
            continue
        href = entry["href"].split("#", 1)[0]
        internal = str((opf_dir / href))
        docs.append(internal)

    return opf_path, docs


def _is_probable_chapter(path: str, raw: bytes) -> bool:
    name = PurePosixPath(path).name.lower()
    if name in {"nav.xhtml", "cover.xhtml", "titlepage.xhtml", "toc.xhtml"}:
        return False
    text = raw.decode("utf-8", errors="ignore")
    if "data-ref-id=" in text or "zhenhun-ref-id" in text or "id=\"zref-" in text:
        return True
    if re.search(r"<h1\b", text, flags=re.I):
        return True
    return name.startswith("chapter_") or name.startswith("chapter-")


def _remove_attr(open_tag: str, name: str) -> str:
    return re.sub(
        rf"\s+{re.escape(name)}\s*=\s*(['\"]).*?\1",
        "",
        open_tag,
        flags=re.I | re.S,
    )


def _inject_marker(raw: bytes, chapter: dict) -> bytes:
    text = raw.decode("utf-8")
    ref_id = chapter["ref_id"]
    story = chapter.get("story_chapter_number")
    chapter_type = chapter.get("chapter_type") or "chapter"

    body_match = re.search(r"<body\b[^>]*>", text, flags=re.I | re.S)
    if not body_match:
        raise IdentityContractError(f"XHTML sem <body>: {ref_id}")

    body_tag = body_match.group(0)
    # Ensure the strongest transport marker is a standard XHTML id.
    body_tag = _remove_attr(body_tag, "id")
    body_tag = _remove_attr(body_tag, "data-ref-id")
    body_tag = _remove_attr(body_tag, "data-story-number")
    body_tag = _remove_attr(body_tag, "data-chapter-type")

    attrs = [
        f'id="zref-{html.escape(ref_id, quote=True)}"',
        f'data-ref-id="{html.escape(ref_id, quote=True)}"',
        f'data-chapter-type="{html.escape(str(chapter_type), quote=True)}"',
    ]
    if story is not None:
        attrs.append(f'data-story-number="{int(story)}"')

    new_body = body_tag[:-1].rstrip() + " " + " ".join(attrs) + ">"
    text = text[:body_match.start()] + new_body + text[body_match.end():]

    # Add redundant metadata in <head>. This is diagnostic/fallback;
    # body id is the primary transport identity.
    meta = (
        f'<meta name="zhenhun-ref-id" content="{html.escape(ref_id, quote=True)}" />'
    )
    if "name=\"zhenhun-ref-id\"" not in text and "name='zhenhun-ref-id'" not in text:
        text = re.sub(
            r"</head>",
            meta + "\n</head>",
            text,
            count=1,
            flags=re.I,
        )

    return text.encode("utf-8")


def _extract_marker(raw: bytes) -> dict | None:
    text = raw.decode("utf-8", errors="ignore")

    ref_match = re.search(
        r"\bdata-ref-id\s*=\s*(['\"])(.*?)\1",
        text,
        flags=re.I | re.S,
    )
    ref_id = ref_match.group(2).strip() if ref_match else None

    if not ref_id:
        id_match = re.search(
            r"\bid\s*=\s*(['\"])zref-([^'\"]+)\1",
            text,
            flags=re.I,
        )
        if id_match:
            ref_id = id_match.group(2).strip()

    if not ref_id:
        meta_match = re.search(
            r"<meta\b[^>]*name\s*=\s*(['\"])zhenhun-ref-id\1[^>]*"
            r"content\s*=\s*(['\"])(.*?)\2",
            text,
            flags=re.I | re.S,
        )
        if meta_match:
            ref_id = meta_match.group(3).strip()

    if not ref_id:
        return None

    story_match = re.search(
        r"\bdata-story-number\s*=\s*(['\"])(\d+)\1",
        text,
        flags=re.I,
    )
    type_match = re.search(
        r"\bdata-chapter-type\s*=\s*(['\"])(.*?)\1",
        text,
        flags=re.I | re.S,
    )

    return {
        "ref_id": ref_id,
        "story_chapter_number": int(story_match.group(2)) if story_match else None,
        "chapter_type": type_match.group(2).strip() if type_match else None,
    }


def _rewrite_zip(epub_path: Path, replacements: dict[str, bytes]) -> None:
    epub_path = Path(epub_path)
    with tempfile.TemporaryDirectory() as tmp:
        temp_epub = Path(tmp) / epub_path.name
        with zipfile.ZipFile(epub_path, "r") as zin, zipfile.ZipFile(temp_epub, "w") as zout:
            names = zin.namelist()

            # EPUB requires mimetype first and uncompressed.
            if "mimetype" in names:
                zout.writestr(
                    "mimetype",
                    replacements.get("mimetype", zin.read("mimetype")),
                    compress_type=zipfile.ZIP_STORED,
                )

            for info in zin.infolist():
                if info.filename == "mimetype":
                    continue
                data = replacements.get(info.filename, zin.read(info.filename))
                new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                new_info.comment = info.comment
                new_info.extra = info.extra
                new_info.internal_attr = info.internal_attr
                new_info.external_attr = info.external_attr
                new_info.create_system = info.create_system
                new_info.flag_bits = info.flag_bits
                zout.writestr(new_info, data, compress_type=zipfile.ZIP_DEFLATED)

        shutil.copy2(temp_epub, epub_path)


def inject_identity_into_epub(epub_path: str | Path, adjusted_json_path: str | Path) -> dict:
    epub_path = Path(epub_path)
    adjusted_json_path = Path(adjusted_json_path)
    data = json.loads(adjusted_json_path.read_text(encoding="utf-8"))
    apply_identity_to_adjusted_json(data)
    chapters = data["chapters"]

    with zipfile.ZipFile(epub_path, "r") as zf:
        _opf, spine_docs = _opf_spine_documents(zf)
        chapter_docs = [
            path for path in spine_docs
            if path in zf.namelist() and _is_probable_chapter(path, zf.read(path))
        ]

        if len(chapter_docs) != len(chapters):
            raise IdentityContractError(
                "Contrato de identidade não pode ser injetado: "
                f"JSON={len(chapters)} capítulos, EPUB={len(chapter_docs)} XHTMLs."
            )

        replacements = {
            path: _inject_marker(zf.read(path), chapter)
            for path, chapter in zip(chapter_docs, chapters)
        }

    _rewrite_zip(epub_path, replacements)

    verification = inspect_epub_identity(epub_path)
    expected_ids = [chapter["ref_id"] for chapter in chapters]
    if verification["ref_ids"] != expected_ids:
        raise IdentityContractError(
            "Falha ao validar ref_id após injeção no EPUB."
        )

    return {
        "epub": epub_path,
        "chapter_count": len(chapters),
        "ref_ids": expected_ids,
        "identity_checksum": data["identity_contract"]["identity_checksum"],
    }


def inspect_epub_identity(epub_path: str | Path) -> dict:
    epub_path = Path(epub_path)
    entries = []

    with zipfile.ZipFile(epub_path, "r") as zf:
        _opf, spine_docs = _opf_spine_documents(zf)
        for path in spine_docs:
            if path not in zf.namelist():
                continue
            marker = _extract_marker(zf.read(path))
            if marker:
                marker["xhtml"] = path
                entries.append(marker)

    ref_ids = [item["ref_id"] for item in entries]
    duplicates = sorted({rid for rid in ref_ids if ref_ids.count(rid) > 1})

    return {
        "epub": epub_path,
        "entries": entries,
        "ref_ids": ref_ids,
        "duplicates": duplicates,
        "count": len(entries),
    }


def validate_identity_pair(original_epub: str | Path, translated_epub: str | Path) -> dict:
    original = inspect_epub_identity(original_epub)
    translated = inspect_epub_identity(translated_epub)

    if original["duplicates"]:
        raise IdentityContractError(
            f"ref_id duplicado no EPUB original: {original['duplicates']}"
        )
    if translated["duplicates"]:
        raise IdentityContractError(
            f"ref_id duplicado no EPUB traduzido: {translated['duplicates']}"
        )
    if not original["ref_ids"]:
        raise IdentityContractError(
            "EPUB original não possui contrato de identidade. Regenere-o pela opção 3."
        )
    if not translated["ref_ids"]:
        raise IdentityContractError(
            "EPUB traduzido não preservou ref_id. "
            "Traduza novamente no Calibre o EPUB chinês gerado com o novo contrato."
        )
    if original["ref_ids"] != translated["ref_ids"]:
        missing = sorted(set(original["ref_ids"]) - set(translated["ref_ids"]))
        extra = sorted(set(translated["ref_ids"]) - set(original["ref_ids"]))
        raise IdentityContractError(
            "Contrato de identidade quebrado pelo processo de tradução. "
            f"original={len(original['ref_ids'])}, traduzido={len(translated['ref_ids'])}, "
            f"ausentes={missing[:10]}, inesperados={extra[:10]}."
        )

    return {
        "count": len(original["ref_ids"]),
        "ref_ids": original["ref_ids"],
        "original_entries": original["entries"],
        "translated_entries": translated["entries"],
    }


def _detect_csv(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";"
    return delimiter


def _load_editorial_titles(csv_path: Path):
    delimiter = _detect_csv(csv_path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=delimiter))

    numeric = {}
    special = {}
    for row in rows:
        chapter = (row.get("Capítulo") or "").strip()
        docx = (row.get("Título no DOCX") or "").strip()
        if chapter.isdigit():
            numeric[int(chapter)] = docx
        elif chapter:
            special[chapter] = docx

    return delimiter, numeric, special


def _load_physical_reference() -> dict:
    root = Path(__file__).resolve().parent
    path = (
        root
        / "manipulacao_json"
        / "input"
        / "referencias"
        / "physical_book_overrides.json"
    )
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("physical_book", {}).get("chapter_map", {})


def _format_target_title(meta: dict, numeric_titles: dict[int, str], special_titles: dict[str, str]):
    chapter_type = meta.get("chapter_type") or "chapter"
    story = meta.get("story_chapter_number")

    if chapter_type == "chapter":
        if story is None:
            return None
        editorial = (numeric_titles.get(int(story)) or "").strip()
        if not editorial:
            return None
        return f"Capítulo {int(story)} - {editorial}"

    # Extras remain extras. Use a special editorial title only when explicitly supplied.
    source_url = ref_id_to_source_url(meta["ref_id"])
    reference = _load_physical_reference().get(source_url or "", {})
    label = (reference.get("label") or "").strip()
    editorial = (special_titles.get(label) or "").strip() if label else ""
    if label and editorial:
        return f"{label} - {editorial}"
    return None


def _replace_first_title_and_h1(raw: bytes, target: str) -> bytes:
    text = raw.decode("utf-8")
    escaped = html.escape(target, quote=False)

    if re.search(r"<title\b[^>]*>.*?</title>", text, flags=re.I | re.S):
        text = re.sub(
            r"(<title\b[^>]*>).*?(</title>)",
            rf"\1{escaped}\2",
            text,
            count=1,
            flags=re.I | re.S,
        )

    if re.search(r"<h1\b[^>]*>.*?</h1>", text, flags=re.I | re.S):
        text = re.sub(
            r"(<h1\b[^>]*>).*?(</h1>)",
            rf"\1{escaped}\2",
            text,
            count=1,
            flags=re.I | re.S,
        )

    return text.encode("utf-8")


def _update_ncx(raw: bytes, title_by_basename: dict[str, str]) -> tuple[bytes, bool]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return raw, False

    changed = False
    for nav_point in root.iter():
        if not nav_point.tag.endswith("navPoint"):
            continue
        content = next((x for x in nav_point if x.tag.endswith("content")), None)
        nav_label = next((x for x in nav_point if x.tag.endswith("navLabel")), None)
        if content is None or nav_label is None:
            continue
        src = (content.get("src") or "").split("#", 1)[0]
        target = title_by_basename.get(PurePosixPath(src).name)
        if not target:
            continue
        text_node = next((x for x in nav_label.iter() if x.tag.endswith("text")), None)
        if text_node is not None and text_node.text != target:
            text_node.text = target
            changed = True

    if not changed:
        return raw, False
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), True


def _update_nav(raw: bytes, title_by_basename: dict[str, str]) -> tuple[bytes, bool]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return raw, False

    changed = False
    for anchor in root.iter():
        if not anchor.tag.endswith("a"):
            continue
        href = (anchor.get("href") or "").split("#", 1)[0]
        target = title_by_basename.get(PurePosixPath(href).name)
        if not target:
            continue
        if "".join(anchor.itertext()).strip() != target:
            # Preserve attributes, replace child content by plain text.
            for child in list(anchor):
                anchor.remove(child)
            anchor.text = target
            changed = True

    if not changed:
        return raw, False
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), True


def correct_epub_titles_by_identity(
    original_epub: str | Path,
    translated_epub: str | Path,
    csv_file: str | Path,
) -> dict:
    original_epub = Path(original_epub)
    translated_epub = Path(translated_epub)
    csv_file = Path(csv_file)

    pair = validate_identity_pair(original_epub, translated_epub)
    delimiter, numeric_titles, special_titles = _load_editorial_titles(csv_file)

    original_by_ref = {
        entry["ref_id"]: entry for entry in pair["original_entries"]
    }
    translated_by_ref = {
        entry["ref_id"]: entry for entry in pair["translated_entries"]
    }

    replacements = {}
    title_by_basename = {}
    corrected_count = 0

    with zipfile.ZipFile(translated_epub, "r") as zf:
        names = set(zf.namelist())

        for ref_id in pair["ref_ids"]:
            meta = dict(original_by_ref[ref_id])
            meta["ref_id"] = ref_id
            target = _format_target_title(meta, numeric_titles, special_titles)
            if not target:
                continue

            xhtml = translated_by_ref[ref_id]["xhtml"]
            raw = zf.read(xhtml)
            new_raw = _replace_first_title_and_h1(raw, target)
            if new_raw != raw:
                replacements[xhtml] = new_raw
                corrected_count += 1
                title_by_basename[PurePosixPath(xhtml).name] = target

        nav_updated = False
        ncx_updated = False
        for name in names:
            basename = PurePosixPath(name).name.lower()
            if basename == "nav.xhtml":
                updated, changed = _update_nav(
                    replacements.get(name, zf.read(name)),
                    title_by_basename,
                )
                if changed:
                    replacements[name] = updated
                    nav_updated = True
            elif basename == "toc.ncx":
                updated, changed = _update_ncx(
                    replacements.get(name, zf.read(name)),
                    title_by_basename,
                )
                if changed:
                    replacements[name] = updated
                    ncx_updated = True

    root = Path(__file__).resolve().parent
    output_dir = root / "producao_epub" / "output" / "4_pos_trad"
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = re.sub(r"_titulos_corrigidos$|_final$", "", translated_epub.stem, flags=re.I)
    output = output_dir / f"{base_name}_final.epub"
    shutil.copy2(translated_epub, output)
    _rewrite_zip(output, replacements)

    # Contract must still be intact after title editing.
    after = validate_identity_pair(original_epub, output)

    return {
        "output": output,
        "delimiter": delimiter,
        "chapter_count": pair["count"],
        "mapped_entries": pair["count"],
        "corrected_count": corrected_count,
        "spine_preserved": after["ref_ids"] == pair["ref_ids"],
        "nav_updated": nav_updated,
        "ncx_updated": ncx_updated,
        "identity_contract": True,
    }

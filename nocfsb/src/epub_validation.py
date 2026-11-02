from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def validate_epub(path: str | Path, expected_chapters: int) -> dict:
    """Check archive integrity, chapter files, manifest, spine, and indexes."""
    issues: list[str] = []
    chapter_files = [f"file{index:04d}.xhtml" for index in range(1, expected_chapters + 1)]
    checked = 0
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            name_set = set(names)
            if not names or names[0] != "mimetype":
                issues.append("O primeiro arquivo do EPUB deve ser mimetype.")
            elif archive.read("mimetype") != b"application/epub+zip":
                issues.append("Tipo MIME inválido.")
            elif archive.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
                issues.append("O arquivo mimetype não pode ser compactado.")

            bad_member = archive.testzip()
            if bad_member:
                issues.append(f"Arquivo corrompido no ZIP: {bad_member}")

            required = {"META-INF/container.xml", "OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/toc.ncx"}
            for name in sorted(required - name_set):
                issues.append(f"Arquivo obrigatório ausente: {name}")
            for name in required & name_set:
                try:
                    ET.fromstring(archive.read(name))
                except ET.ParseError:
                    issues.append(f"XML inválido: {name}")

            if "OEBPS/content.opf" in name_set:
                try:
                    opf = ET.fromstring(archive.read("OEBPS/content.opf"))
                    manifest = {
                        item.get("id"): item.get("href")
                        for item in opf.findall(".//{*}manifest/{*}item")
                    }
                    for href in manifest.values():
                        if href and f"OEBPS/{href}" not in name_set:
                            issues.append(f"Arquivo do manifesto ausente: {href}")
                    spine = [item.get("idref") for item in opf.findall(".//{*}spine/{*}itemref")]
                    if len(spine) != expected_chapters + 1:
                        issues.append(f"Índice de leitura contém {len(spine) - 1} capítulos; esperado: {expected_chapters}.")
                    for index, chapter_file in enumerate(chapter_files, start=1):
                        if f"OEBPS/{chapter_file}" not in name_set:
                            issues.append(f"Capítulo ausente no EPUB: {chapter_file}")
                        elif manifest.get(f"chap{index}") != chapter_file or f"chap{index}" not in spine:
                            issues.append(f"Capítulo fora do manifesto ou da leitura: {chapter_file}")
                except ET.ParseError:
                    pass

            for chapter_file in chapter_files:
                archive_name = f"OEBPS/{chapter_file}"
                if archive_name not in name_set:
                    continue
                try:
                    page = ET.fromstring(archive.read(archive_name))
                except ET.ParseError:
                    issues.append(f"XHTML inválido: {chapter_file}")
                    continue
                if not any("".join(p.itertext()).strip() for p in page.findall(".//{*}p")):
                    issues.append(f"Capítulo sem texto no EPUB: {chapter_file}")
                checked += 1

            for index_name, tag, attr in (("nav.xhtml", "a", "href"), ("toc.ncx", "content", "src")):
                archive_name = f"OEBPS/{index_name}"
                if archive_name not in name_set:
                    continue
                try:
                    index = ET.fromstring(archive.read(archive_name))
                except ET.ParseError:
                    continue
                linked = {element.get(attr) for element in index.findall(f".//{{*}}{tag}")}
                missing = [chapter_file for chapter_file in chapter_files if chapter_file not in linked]
                if missing:
                    issues.append(f"{index_name} não referencia {len(missing)} capítulos.")
    except (OSError, zipfile.BadZipFile) as exc:
        issues.append(f"Não foi possível abrir o EPUB: {exc}")

    return {"is_valid": not issues, "issues": issues, "chapters_checked": checked}

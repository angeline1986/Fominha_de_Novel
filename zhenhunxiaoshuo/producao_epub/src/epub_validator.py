from __future__ import annotations

import html
import json
import re
import zipfile
from pathlib import Path

from zhenhunxiaoshuo.identity_contract import inspect_epub_identity

MODULE_ROOT = Path(__file__).resolve().parents[1]
FINAL_EPUB_DIR = MODULE_ROOT / "output" / "4_pos_trad"
VALIDATION_DIR = MODULE_ROOT / "output" / "5_validacao"
REFERENCE_FILE = (
    MODULE_ROOT.parent
    / "manipulacao_json"
    / "input"
    / "referencias"
    / "physical_book_overrides.json"
)


def _read_h1(zf, xhtml):
    raw = zf.read(xhtml).decode("utf-8", errors="ignore")
    match = re.search(r"<h1\b[^>]*>(.*?)</h1>", raw, flags=re.I | re.S)
    if not match:
        return ""
    value = re.sub(r"<[^>]+>", "", match.group(1))
    return html.unescape(value).strip()


def validate_final_epub(epub_path, reference_path=REFERENCE_FILE):
    epub_path = Path(epub_path)
    reference_path = Path(reference_path)
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    chapter_map = reference["physical_book"]["chapter_map"]

    identity = inspect_epub_identity(epub_path)
    rows = []
    errors = []
    warnings = []

    with zipfile.ZipFile(epub_path, "r") as zf:
        for index, entry in enumerate(identity["entries"], start=1):
            ref_id = entry["ref_id"]
            match = re.fullmatch(r"zhenhun-(\d+)", ref_id)
            source_url = (
                f"https://www.zhenhunxiaoshuo.com/{match.group(1)}.html"
                if match else None
            )
            expected = chapter_map.get(source_url)
            title = _read_h1(zf, entry["xhtml"])

            row_errors = []
            row_warnings = []

            if expected is None:
                row_errors.append("ref_id não existe na referência física")
            else:
                expected_type = expected.get("chapter_type", "chapter")
                expected_story = expected.get("story_chapter_number")
                actual_type = entry.get("chapter_type")
                actual_story = entry.get("story_chapter_number")

                if actual_type != expected_type:
                    row_errors.append(
                        f"tipo esperado={expected_type}, encontrado={actual_type}"
                    )

                if actual_story != expected_story:
                    row_errors.append(
                        f"número narrativo esperado={expected_story}, encontrado={actual_story}"
                    )

                if expected_type == "chapter" and expected_story is not None:
                    if not re.match(
                        rf"^\s*Capítulo\s+{int(expected_story)}(?:\D|$)",
                        title,
                        flags=re.I,
                    ):
                        row_errors.append(
                            f"título não começa com Capítulo {expected_story}"
                        )

                if expected_type == "extra":
                    if re.match(r"^\s*Capítulo\s+\d+", title, flags=re.I):
                        row_errors.append(
                            "extra apresentado como capítulo numerado"
                        )
                    label = (expected.get("label") or "").strip()
                    if label and label.lower() not in title.lower():
                        row_warnings.append(
                            f"título não contém o rótulo físico: {label}"
                        )

            rows.append({
                "index": index,
                "ref_id": ref_id,
                "xhtml": entry["xhtml"],
                "title": title,
                "errors": row_errors,
                "warnings": row_warnings,
                "expected": expected,
            })
            errors.extend((ref_id, item) for item in row_errors)
            warnings.extend((ref_id, item) for item in row_warnings)

    # Validate relative editorial order only among entries present in this EPUB.
    expected_positions = []
    for row in rows:
        expected = row["expected"]
        if expected and expected.get("editorial_position") is not None:
            expected_positions.append(
                (row["ref_id"], int(expected["editorial_position"]))
            )
    for previous, current in zip(expected_positions, expected_positions[1:]):
        if current[1] <= previous[1]:
            errors.append((
                current[0],
                f"ordem editorial inválida: {previous[1]} -> {current[1]}",
            ))

    status = "APROVADO" if not errors else "REVISÃO NECESSÁRIA"
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    report_path = VALIDATION_DIR / "validacao.html"

    table_rows = []
    for row in rows:
        state = "ERRO" if row["errors"] else ("AVISO" if row["warnings"] else "OK")
        details = "<br>".join(
            html.escape(x) for x in (row["errors"] + row["warnings"])
        ) or "—"
        table_rows.append(
            "<tr>"
            f"<td>{row['index']}</td>"
            f"<td>{html.escape(row['ref_id'])}</td>"
            f"<td>{html.escape(row['title'])}</td>"
            f"<td>{state}</td>"
            f"<td>{details}</td>"
            "</tr>"
        )

    document = f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Validação EPUB</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;margin:40px;color:#2c3e50}}
h1{{color:#7209b7}}
.ok{{color:#087f5b}} .bad{{color:#c92a2a}}
table{{border-collapse:collapse;width:100%;margin-top:24px}}
th,td{{border:1px solid #dee2e6;padding:8px;text-align:left;vertical-align:top}}
th{{background:#f8f9fa}}
code{{background:#f1f3f5;padding:2px 5px;border-radius:4px}}
</style>
</head>
<body>
<h1>Validação final do EPUB</h1>
<p><strong>Status:</strong> <span class="{'ok' if not errors else 'bad'}">{status}</span></p>
<p><strong>EPUB:</strong> {html.escape(epub_path.name)}</p>
<p><strong>Referência:</strong> {html.escape(reference_path.name)}</p>
<p><strong>ref_id:</strong> {identity['count']} encontrados, {len(identity['duplicates'])} duplicados</p>
<p><strong>Erros:</strong> {len(errors)} &nbsp; <strong>Avisos:</strong> {len(warnings)}</p>
<table>
<thead><tr><th>#</th><th>ref_id</th><th>Título</th><th>Status</th><th>Detalhes</th></tr></thead>
<tbody>{''.join(table_rows)}</tbody>
</table>
</body></html>"""

    report_path.write_text(document, encoding="utf-8")
    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "ref_count": identity["count"],
        "duplicates": identity["duplicates"],
        "report": report_path,
    }

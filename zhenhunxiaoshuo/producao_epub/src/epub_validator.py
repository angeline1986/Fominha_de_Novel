from __future__ import annotations

import html
import json
import re
import zipfile
from pathlib import Path
from posixpath import basename

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


def _badge(label, kind):
    return f'<span class="status {kind}">{html.escape(label)}</span>'


def _status_rank(status):
    return {
        "DIVERGÊNCIA": 0,
        "ERRO": 0,
        "AVISO": 1,
        "ATENÇÃO": 1,
        "OK": 2,
    }.get(status, 3)


def _status_kind(status):
    return {
        "DIVERGÊNCIA": "bad",
        "ERRO": "bad",
        "AVISO": "warn",
        "ATENÇÃO": "warn",
        "OK": "ok",
    }.get(status, "info")


def _table_row(*cells, status=None):
    attrs = f' data-status="{html.escape(status, quote=True)}"' if status else ""
    return "<tr" + attrs + ">" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"


def _filter_select(select_id, table_id, all_label, aria_label, statuses):
    options = [f'<option value="Todos">{html.escape(all_label)}</option>']
    options.extend(
        f'<option value="{html.escape(status, quote=True)}">{html.escape(status)}</option>'
        for status in statuses
    )
    return (
        f'<select class="column-filter" id="{select_id}" '
        f'data-filter-target="{table_id}" '
        f'aria-label="{html.escape(aria_label, quote=True)}">'
        + "".join(options)
        + "</select>"
    )


def _find_first_name(names, suffix):
    suffix = suffix.lower()
    return next((name for name in names if name.lower().endswith(suffix)), None)


def _href_matches(raw, xhtml):
    target = basename(xhtml)
    escaped = re.escape(target)
    return bool(re.search(
        rf"\b(?:href|src)\s*=\s*(['\"])[^'\"]*{escaped}(?:#[^'\"]*)?\1",
        raw,
        flags=re.I,
    ))


def _epub_navigation_index(epub_path):
    with zipfile.ZipFile(epub_path, "r") as zf:
        names = zf.namelist()
        nav_path = _find_first_name(names, "nav.xhtml")
        toc_path = _find_first_name(names, "toc.ncx")
        nav_raw = zf.read(nav_path).decode("utf-8", errors="ignore") if nav_path else ""
        toc_raw = zf.read(toc_path).decode("utf-8", errors="ignore") if toc_path else ""
    return {
        "nav_path": nav_path,
        "nav_raw": nav_raw,
        "toc_path": toc_path,
        "toc_raw": toc_raw,
    }


def _expected_label(expected):
    expected_type = expected.get("chapter_type", "chapter")
    story_number = expected.get("story_chapter_number")
    if expected_type == "extra":
        label = (expected.get("label") or "").strip()
        if label:
            return f"Extra: {label}"
        position = expected.get("editorial_position")
        if position is not None:
            return f"Extra na posição editorial {position}"
        return "Extra"
    if story_number is not None:
        return f"Capítulo {int(story_number)}"
    return expected_type


def _found_label(row):
    actual_type = row.get("actual_type") or "sem tipo"
    actual_story = row.get("actual_story")
    title = row["title"] or "Sem título visível"
    if actual_type == "chapter" and actual_story is not None:
        if re.match(rf"^\s*Capítulo\s+{int(actual_story)}(?:\D|$)", title, flags=re.I):
            return title
        return f"Capítulo {int(actual_story)} - {title}"
    if actual_type == "extra":
        return f"Extra - {title}"
    return title


def _position_label(expected):
    if expected.get("chapter_type") == "extra":
        reason = expected.get("reason") or ""
        match = re.search(r"ap[oó]s\s+cap[ií]tulo\s+(\d+)", reason, flags=re.I)
        if match:
            return f"Após o capítulo {match.group(1)}"
    position = expected.get("editorial_position")
    if position is not None:
        return f"Posição editorial {position}"
    return "Não informada"


def _issue_action(row, problem):
    expected = row["expected"]
    if expected and expected.get("chapter_type") == "extra":
        if "capítulo numerado" in problem:
            return "Ajustar somente a apresentação editorial do título para que o extra não pareça capítulo regular."
        if "rótulo físico" in problem:
            return "Revisar o título visível do extra contra o rótulo físico informado."
    if "tipo esperado" in problem:
        return "Verificar a marcação data-chapter-type no XHTML correspondente."
    if "número narrativo" in problem or "título não começa" in problem:
        return "Conferir o número editorial do capítulo e regenerar/corrigir o EPUB final."
    if "ordem editorial" in problem:
        return "Conferir a ordem dos itens cobertos pela referência física."
    return "Revisar o item coberto pela referência física."


def _action_locations(row, problem, navigation):
    if "título" in problem or "capítulo numerado" in problem:
        def item(label, text, muted=False):
            css = ' class="muted"' if muted else ""
            return (
                f"<div{css}><span>{html.escape(label)}</span> "
                f"{html.escape(text)}</div>"
            )

        locations = [item("XHTML", f"{basename(row['xhtml'])} → <h1>")]
        nav_path = navigation["nav_path"]
        toc_path = navigation["toc_path"]
        if toc_path is None:
            locations.append(item("NCX", "não disponível", muted=True))
        elif _href_matches(navigation["toc_raw"], row["xhtml"]):
            locations.append(item("NCX", f"{basename(toc_path)} → navPoint"))
        else:
            locations.append(
                item("NCX", f"{basename(toc_path)} → navPoint não localizado", muted=True)
            )

        if nav_path is None:
            locations.append(item("NAV", "não disponível", muted=True))
        elif _href_matches(navigation["nav_raw"], row["xhtml"]):
            locations.append(item("NAV", f"{basename(nav_path)} → entrada"))
        else:
            locations.append(
                item("NAV", f"{basename(nav_path)} → entrada não localizada", muted=True)
            )
        return '<div class="adjust-list">' + "".join(locations) + "</div>"
    if "tipo esperado" in problem:
        return html.escape(f"{row['xhtml']} → data-chapter-type")
    if "número narrativo" in problem:
        return html.escape(f"{row['xhtml']} → data-story-number")
    if "ordem editorial" in problem:
        return html.escape(row["xhtml"])
    return html.escape(row["xhtml"] or "Não determinado")


def _extra_suffix(title, label):
    if not label:
        return ""
    cleaned = re.sub(r"^\s*Capítulo\s+\d+\s*", "", title or "", flags=re.I)
    cleaned = re.sub(r"^\s*\[[^\]]+\]\s*", "", cleaned).strip()
    if cleaned and cleaned.lower() != label.lower():
        return cleaned
    return ""


def _expected_action_value(row, problem):
    expected = row["expected"] or {}
    title = row["title"] or ""
    expected_type = expected.get("chapter_type")
    story_number = expected.get("story_chapter_number")
    if expected_type == "extra":
        label = (expected.get("label") or "").strip()
        if not label:
            return _expected_label(expected)
        suffix = _extra_suffix(title, label)
        return f"{label} — {suffix}" if suffix else label
    if story_number is not None:
        return f"Capítulo {int(story_number)}"
    return _expected_label(expected)


def _clear_reason(row, problem):
    expected = row["expected"] or {}
    if expected.get("chapter_type") == "extra":
        if "capítulo numerado" in problem:
            return (
                "A referência física classifica o item como extra, mas o "
                "título visível o apresenta como capítulo regular."
            )
        if "rótulo físico" in problem:
            return (
                "A referência física informa um rótulo para o extra, mas o "
                "título visível não contém esse rótulo."
            )
    if "número narrativo" in problem or "título não começa" in problem:
        story = expected.get("story_chapter_number")
        if story is not None:
            return (
                f"A referência física confirma Capítulo {int(story)}, mas o "
                "EPUB apresenta outro número."
            )
    if "tipo esperado" in problem:
        return (
            "A referência física define um tipo editorial diferente daquele "
            "marcado no EPUB."
        )
    if "ordem editorial" in problem:
        return "O item está fora da ordem editorial definida pela referência física."
    return problem


def validate_final_epub(epub_path, reference_path=REFERENCE_FILE):
    epub_path = Path(epub_path)
    reference_path = Path(reference_path)
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    chapter_map = reference["physical_book"]["chapter_map"]

    identity = inspect_epub_identity(epub_path)
    navigation = _epub_navigation_index(epub_path)
    rows = []
    errors = []
    warnings = []
    uncovered = []

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
            actual_type = entry.get("chapter_type")
            actual_story = entry.get("story_chapter_number")

            if expected is None:
                pass
            else:
                expected_type = expected.get("chapter_type", "chapter")
                expected_story = expected.get("story_chapter_number")

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
                "actual_type": actual_type,
                "actual_story": actual_story,
            })
            if expected is None:
                uncovered.append(ref_id)
            else:
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
            problem = f"ordem editorial inválida: {previous[1]} -> {current[1]}"
            errors.append((
                current[0],
                problem,
            ))
            for row in rows:
                if row["ref_id"] == current[0]:
                    row["errors"].append(problem)
                    break

    status = "APROVADO" if not errors else "REVISÃO NECESSÁRIA"
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    report_path = VALIDATION_DIR / "validacao.html"

    covered_rows = [row for row in rows if row["expected"] is not None]
    covered_count = len(covered_rows)
    uncovered_count = len(uncovered)
    duplicate_count = len(identity["duplicates"])
    structural_errors = []
    if not identity["ref_ids"]:
        structural_errors.append("Nenhum ref_id encontrado.")
    if identity["duplicates"]:
        structural_errors.append("Há ref_id duplicado.")

    summary_border = "var(--bad)" if errors or structural_errors else "var(--ok)"
    status_class = "bad" if errors or structural_errors else "ok"
    real_issue_count = len(errors) + len(structural_errors)
    status = "APROVADO" if real_issue_count == 0 else "REVISÃO NECESSÁRIA"

    covered_table_rows = []
    covered_statuses = set()
    for row in covered_rows:
        if row["errors"]:
            status_label = "DIVERGÊNCIA"
        elif row["warnings"]:
            status_label = "AVISO"
        else:
            status_label = "OK"
        covered_statuses.add(status_label)
        state = _badge(status_label, _status_kind(status_label))
        covered_table_rows.append((_status_rank(status_label), _table_row(
            f"<code>{html.escape(row['ref_id'])}</code>",
            html.escape(_expected_label(row["expected"])),
            html.escape(_found_label(row)),
            state,
            status=status_label,
        )))
    covered_table = "".join(row for _, row in sorted(covered_table_rows)) or (
        '<tr><td colspan="4">Nenhum item do EPUB possui referência física aplicável.</td></tr>'
    )
    covered_filter = _filter_select(
        "filter-covered",
        "table-covered",
        "STATUS",
        "Filtrar por status",
        sorted(covered_statuses, key=_status_rank),
    )

    order_ok = not any("ordem editorial inválida" in item for _, item in errors)
    type_warnings = sum(
        1 for row in covered_rows
        if row["expected"].get("chapter_type") == "extra" and (row["errors"] or row["warnings"])
    )
    structural_rows = [
        (
            _status_rank("OK" if identity["ref_ids"] else "ERRO"),
            _table_row(
            "Quantidade de ref_id",
            _badge("OK" if identity["ref_ids"] else "ERRO", "ok" if identity["ref_ids"] else "bad"),
            f"{identity['count']} identificadores encontrados.",
            status="OK" if identity["ref_ids"] else "ERRO",
        )),
        (
            _status_rank("OK" if not identity["duplicates"] else "ERRO"),
            _table_row(
                "Duplicidade de ref_id",
                _badge("OK" if not identity["duplicates"] else "ERRO", "ok" if not identity["duplicates"] else "bad"),
                "Nenhum identificador duplicado." if not identity["duplicates"]
                else "Duplicados: " + ", ".join(html.escape(item) for item in identity["duplicates"]),
                status="OK" if not identity["duplicates"] else "ERRO",
            ),
        ),
        (
            _status_rank("OK" if order_ok else "ERRO"),
            _table_row(
                "Ordem dos itens cobertos",
                _badge("OK" if order_ok else "ERRO", "ok" if order_ok else "bad"),
                "Ordem compatível com editorial_position nos itens que possuem referência."
                if order_ok else "Existe inversão na ordem editorial dos itens cobertos.",
                status="OK" if order_ok else "ERRO",
            ),
        ),
        (
            _status_rank("OK" if type_warnings == 0 else "ATENÇÃO"),
            _table_row(
                "Tipos chapter/extra",
                _badge("OK" if type_warnings == 0 else "ATENÇÃO", "ok" if type_warnings == 0 else "warn"),
                "Tipos coerentes nos itens cobertos pela referência."
                if type_warnings == 0 else f"{type_warnings} item(ns) extra exigem atenção na apresentação editorial.",
                status="OK" if type_warnings == 0 else "ATENÇÃO",
            ),
        ),
    ]
    structural_table = "".join(row for _, row in sorted(structural_rows))
    structural_statuses = sorted(
        {re.search(r'data-status="([^"]+)"', row).group(1) for _, row in structural_rows},
        key=_status_rank,
    )
    structural_filter = _filter_select(
        "filter-integrity",
        "table-integrity",
        "RESULTADO",
        "Filtrar por resultado",
        structural_statuses,
    )

    issue_rows = []
    for ref_id, problem in errors:
        row = next((item for item in covered_rows if item["ref_id"] == ref_id), None)
        if row is None:
            issue_rows.append(_table_row(
                f"<code>{html.escape(ref_id)}</code>",
                "Não determinado",
                "Não determinado",
                "Referência física",
                html.escape(_clear_reason({"expected": {}}, problem)),
            ))
            continue
        issue_rows.append(_table_row(
            f"<code>{html.escape(ref_id)}</code>",
            _action_locations(row, problem, navigation),
            html.escape(row["title"] or "Sem título visível"),
            html.escape(_expected_action_value(row, problem)),
            html.escape(_clear_reason(row, problem)),
        ))
    issues_html = (
        '<table class="issues-table"><thead><tr><th>Ref ID</th><th>Onde ajustar</th><th>Como está</th>'
        '<th>Como deveria estar</th><th>Motivo</th></tr></thead>'
        f"<tbody>{''.join(issue_rows)}</tbody></table>"
        if issue_rows else
        '<div class="card"><p>Nenhuma divergência acionável encontrada.</p></div>'
    )
    issue_summary = (
        f"{len(errors)} divergência encontrada."
        if len(errors) == 1 else
        f"{len(errors)} divergências encontradas."
    )
    issue_next_step = (
        'Corrija o item indicado na coluna "Onde ajustar" e execute novamente: '
        "<strong>5. Validação</strong>."
        if errors else
        "Nenhuma divergência acionável encontrada."
    )

    uncovered_rows = "\n".join(
        _table_row(f"<code>{html.escape(row['ref_id'])}</code>", html.escape(row["title"] or "Sem título visível"))
        for row in rows if row["expected"] is None
    )
    uncovered_details = ""
    if uncovered_rows:
        uncovered_details = (
            '<details><summary>Listar itens sem referência física</summary>'
            '<table><thead><tr><th>ref_id</th><th>Título</th></tr></thead>'
            f"<tbody>{uncovered_rows}</tbody></table></details>"
        )

    divergence_sentence = (
        f"Foi encontrada {len(errors)} divergência editorial real."
        if len(errors) == 1 else
        f"Foram encontradas {len(errors)} divergências editoriais reais."
    )
    no_reference_sentence = (
        f"{uncovered_count} item não possui referência física aplicável e, portanto, não é considerado erro."
        if uncovered_count == 1 else
        f"{uncovered_count} itens não possuem referência física aplicável e, portanto, não são considerados erros."
    )

    document = f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Validação final do EPUB</title>
<style>
:root{{
  --bg:#f5f7fb; --card:#ffffff; --text:#243447; --muted:#6b7785;
  --line:#e4e9f0; --ok:#14866d; --ok-bg:#e9f8f3;
  --warn:#b7791f; --warn-bg:#fff7e6; --bad:#c2413b; --bad-bg:#fdeeee;
  --info:#3366cc; --info-bg:#edf3ff; --accent:#7209b7;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:32px 24px 56px}}
header{{margin-bottom:24px}}
h1{{margin:0 0 6px;color:var(--accent);font-size:30px}}
.subtitle{{color:var(--muted);font-size:14px}}
.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin:22px 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}
.metric-label{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
.metric-value{{font-size:28px;font-weight:700;margin-top:6px}}
.status{{display:inline-block;padding:7px 11px;border-radius:999px;font-weight:700;font-size:13px}}
.ok{{background:var(--ok-bg);color:var(--ok)}} .warn{{background:var(--warn-bg);color:var(--warn)}}
.bad{{background:var(--bad-bg);color:var(--bad)}} .info{{background:var(--info-bg);color:var(--info)}}
section{{margin-top:22px}} section h2{{font-size:18px;margin:0 0 12px}}
.summary{{background:var(--card);border:1px solid var(--line);border-left:5px solid {summary_border};border-radius:14px;padding:18px 20px}}
.summary p{{margin:6px 0;line-height:1.5}}
table{{width:100%;border-collapse:separate;border-spacing:0;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}}
th,td{{padding:11px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:13px}}
th{{background:#f9fbfd;color:#52606d;font-size:12px;text-transform:uppercase;letter-spacing:.03em}}
tr:last-child td{{border-bottom:0}}
.issues-table{{table-layout:fixed}}
.issues-table th:nth-child(1),.issues-table td:nth-child(1){{width:12%}}
.issues-table th:nth-child(2),.issues-table td:nth-child(2){{width:28%}}
.issues-table th:nth-child(3),.issues-table td:nth-child(3){{width:18%}}
.issues-table th:nth-child(4),.issues-table td:nth-child(4){{width:18%}}
.issues-table th:nth-child(5),.issues-table td:nth-child(5){{width:24%}}
code{{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px;background:#f2f4f7;padding:2px 5px;border-radius:5px}}
.note{{color:var(--muted);font-size:13px;line-height:1.5}}
.column-filter{{width:auto;min-width:max-content;border:1px solid var(--line);border-radius:7px;background:#fff;color:#52606d;font:inherit;font-size:12px;font-weight:700;letter-spacing:.03em;padding:5px 26px 5px 8px;text-transform:uppercase;cursor:pointer}}
.adjust-list{{display:grid;gap:5px;line-height:1.35}}
.adjust-list div{{display:grid;grid-template-columns:56px 1fr;gap:10px;align-items:baseline}}
.adjust-list span{{color:#52606d;font-size:12px;font-weight:700;letter-spacing:.03em}}
.adjust-list .muted{{color:var(--muted)}}
details{{margin-top:14px}} summary{{cursor:pointer;color:var(--info);font-weight:700}}
.footer{{margin-top:28px;color:var(--muted);font-size:12px}}
@media (max-width:950px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
@media (max-width:520px){{.grid{{grid-template-columns:1fr}} main{{padding:20px 14px 40px}}}}
</style>
</head>
<body>
<main>
  <header>
    <h1>Validação final do EPUB</h1>
    <div class="subtitle">{html.escape(epub_path.name)} · referência: {html.escape(reference_path.name)}</div>
  </header>

  <div class="summary">
    {_badge(status, status_class)}
    <p><strong>Resumo:</strong> o contrato de identidade está preservado e os itens cobertos pela referência física foram avaliados separadamente.</p>
    <p>{html.escape(divergence_sentence)} {html.escape(no_reference_sentence)}</p>
  </div>

  <div class="grid">
    <div class="card"><div class="metric-label">ref_id encontrados</div><div class="metric-value">{identity['count']}</div></div>
    <div class="card"><div class="metric-label">ref_id duplicados</div><div class="metric-value">{duplicate_count}</div></div>
    <div class="card"><div class="metric-label">Cobertos pela referência</div><div class="metric-value">{covered_count}</div></div>
    <div class="card"><div class="metric-label">Divergências reais</div><div class="metric-value">{len(errors)}</div></div>
    <div class="card"><div class="metric-label">Sem referência física</div><div class="metric-value">{uncovered_count}</div></div>
  </div>

  <section>
    <h2>1. Integridade estrutural</h2>
    <table>
      <thead><tr><th>Verificação</th><th>{structural_filter}</th><th>Observação</th></tr></thead>
      <tbody id="table-integrity">{structural_table}</tbody>
    </table>
  </section>

  <section>
    <h2>2. Itens cobertos pela referência física</h2>
    <table>
      <thead><tr><th>ref_id</th><th>Esperado</th><th>Encontrado</th><th>{covered_filter}</th></tr></thead>
      <tbody id="table-covered">{covered_table}</tbody>
    </table>
    <p class="note">A tabela mostra apenas itens presentes em <code>physical_book_overrides.json</code>.</p>
  </section>

  <section>
    <h2>3. Divergências que exigem ação</h2>
    {issues_html}
    <p class="note">{html.escape(issue_summary)}</p>
    <p class="note">{issue_next_step}</p>
  </section>

  <section>
    <h2>4. Itens sem referência física</h2>
    <div class="card">
      {_badge("SEM REFERÊNCIA FÍSICA", "info")}
      <p><strong>{uncovered_count} item(ns)</strong> não estão presentes em <code>physical_book_overrides.json</code>.</p>
      <p class="note">Isso não significa erro. Esses itens apenas não podem ser validados contra essa referência específica. Eles continuam sujeitos às validações estruturais do EPUB e do contrato de identidade.</p>
      {uncovered_details}
    </div>
  </section>

  <section>
    <h2>5. Conclusão</h2>
    <div class="card">
      <p><strong>Estado geral:</strong> {_badge(status, status_class)}</p>
      <p>O EPUB possui {identity['count']} ref_id encontrados, {covered_count} item(ns) coberto(s) pela referência física e {len(errors)} divergência(s) acionável(is).</p>
    </div>
  </section>

  <div class="footer">Relatório gerado pela opção 5 — Validação.</div>
</main>
<script>
document.querySelectorAll('select[data-filter-target]').forEach(function(select) {{
  function applyFilter() {{
    var target = document.getElementById(select.dataset.filterTarget);
    var selected = select.value;
    if (!target) return;
    target.querySelectorAll('tr[data-status]').forEach(function(row) {{
      row.hidden = selected !== 'Todos' && row.dataset.status !== selected;
    }});
  }}
  select.addEventListener('change', applyFilter);
  applyFilter();
}});
</script>
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

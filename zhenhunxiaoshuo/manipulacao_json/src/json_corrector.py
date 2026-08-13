from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_FILE = MODULE_ROOT / "input" / "referencias" / "physical_book_overrides.json"
OUTPUT_DIR = MODULE_ROOT / "output" / "revisados"
# Compatibilidade com o menu atual, que importa este nome público.
REVIEWED_JSON_DIR = OUTPUT_DIR

EXTRA_MARKERS = ("番外", "extra", "especial")
ARABIC_PREFIX_RE = re.compile(r"^第\s*(\d+)\s*章")
CHINESE_PREFIX_RE = re.compile(r"^第\s*([零〇一二三四五六七八九十百千万两]+)\s*章")
LEAD_PREFIX_RE = re.compile(r"^(【)\s*第[^】]{0,30}?章")


class JsonCorrectionError(ValueError):
    pass


def _load_reference() -> dict[str, Any]:
    if not REFERENCE_FILE.is_file():
        raise JsonCorrectionError(f"Referência física não encontrada: {REFERENCE_FILE}")
    return json.loads(REFERENCE_FILE.read_text(encoding="utf-8"))


def _chinese_digit(ch: str) -> int:
    values = {
        "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    }
    return values[ch]


def chinese_number_to_int(value: str) -> int | None:
    if not value:
        return None
    if value.isdigit():
        return int(value)

    total = 0
    section = 0
    number = 0
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}

    try:
        for ch in value:
            if ch in "零〇一二三四五六七八九两":
                number = _chinese_digit(ch)
                continue

            unit = units.get(ch)
            if unit is None:
                return None

            if unit == 10000:
                section = (section + number) * unit
                total += section
                section = 0
                number = 0
                continue

            if number == 0:
                number = 1
            section += number * unit
            number = 0

        return total + section + number
    except (KeyError, TypeError):
        return None


def int_to_chinese(value: int) -> str:
    if not 0 < value < 10000:
        return str(value)

    digits = "零一二三四五六七八九"

    if value < 10:
        return digits[value]
    if value < 20:
        return "十" + (digits[value % 10] if value % 10 else "")
    if value < 100:
        tens, ones = divmod(value, 10)
        return digits[tens] + "十" + (digits[ones] if ones else "")
    if value < 1000:
        hundreds, rest = divmod(value, 100)
        result = digits[hundreds] + "百"
        if not rest:
            return result
        if rest < 10:
            return result + "零" + digits[rest]
        return result + int_to_chinese(rest)

    thousands, rest = divmod(value, 1000)
    result = digits[thousands] + "千"
    if not rest:
        return result
    if rest < 100:
        return result + "零" + int_to_chinese(rest)
    return result + int_to_chinese(rest)


def _declared_number(title: str | None) -> int | None:
    title = (title or "").strip()

    match = ARABIC_PREFIX_RE.match(title)
    if match:
        return int(match.group(1))

    match = CHINESE_PREFIX_RE.match(title)
    if match:
        return chinese_number_to_int(match.group(1))

    return None


def _lead_declared_number(lead: str | None) -> int | None:
    lead = (lead or "").strip()
    if not lead.startswith("【"):
        return None

    inner = lead[1:].split("】", 1)[0].replace("-章", "章")
    return _declared_number(inner)


def _is_extra_marker(chapter: dict[str, Any]) -> bool:
    combined = " ".join(
        str(chapter.get(key) or "")
        for key in ("chapter_title", "chapter_lead", "csv_title")
    ).lower()
    return any(marker.lower() in combined for marker in EXTRA_MARKERS)


def _rewrite_title_number(title: str | None, number: int) -> str | None:
    if not title:
        return title

    replacement = f"第{int_to_chinese(number)}章"
    if ARABIC_PREFIX_RE.match(title):
        return ARABIC_PREFIX_RE.sub(replacement, title, count=1)
    if CHINESE_PREFIX_RE.match(title):
        return CHINESE_PREFIX_RE.sub(replacement, title, count=1)
    return title


def _rewrite_lead_number(lead: str | None, number: int) -> str | None:
    if not lead:
        return lead

    replacement = f"【第{int_to_chinese(number)}章"
    if LEAD_PREFIX_RE.match(lead):
        return LEAD_PREFIX_RE.sub(replacement, lead, count=1)
    return lead


def _review_reason(declared, previous_declared, next_declared, lead_declared):
    reasons = []

    if declared is not None:
        if declared == previous_declared or declared == next_declared:
            reasons.append("duplicate_neighbor")

        neighbors = [
            number for number in (previous_declared, next_declared)
            if number is not None
        ]
        if neighbors and all(abs(declared - number) > 2 for number in neighbors):
            reasons.append("suspicious_jump")

    if declared is not None and lead_declared is not None and declared != lead_declared:
        reasons.append("title_lead_disagree")

    return ",".join(dict.fromkeys(reasons)) or None


def _prepare_source_fields(chapter: dict[str, Any], source_position: int):
    item = copy.deepcopy(chapter)
    title = item.get("chapter_title")
    lead = item.get("chapter_lead")

    item["source_position"] = source_position
    item["source_declared_number"] = _declared_number(title)
    item["source_lead_declared_number"] = _lead_declared_number(lead)
    item["source_chapter_title"] = title
    item["source_chapter_lead"] = lead
    item["reference_override"] = False

    return item


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    reference = _load_reference()
    physical = reference["physical_book"]
    reference_map = physical.get("chapter_map", {})

    raw_chapters = data.get("chapters")
    if not isinstance(raw_chapters, list):
        raise JsonCorrectionError("JSON inválido: campo 'chapters' ausente.")

    chapters = [
        _prepare_source_fields(chapter, index)
        for index, chapter in enumerate(raw_chapters, start=1)
    ]

    reference_applied = []
    review = []

    max_reference_order = max(
        (int(entry["editorial_position"]) for entry in reference_map.values()),
        default=0,
    )

    for index, item in enumerate(chapters):
        url = item.get("source_url")
        declared = item["source_declared_number"]
        lead_declared = item["source_lead_declared_number"]
        mapped = reference_map.get(url)

        if mapped is not None:
            item["chapter_type"] = mapped["chapter_type"]
            item["story_chapter_number"] = mapped["story_chapter_number"]
            item["editorial_position"] = int(mapped["editorial_position"])
            item["_sort_key"] = item["editorial_position"]

            if mapped["chapter_type"] == "extra":
                item["numbering_status"] = "reference_confirmed_extra"
                item["numbering_reason"] = mapped["reason"]
                item["reference_override"] = True
                reference_applied.append({
                    "source_url": url,
                    "story_chapter_number": None,
                    "chapter_type": "extra",
                    "reason": mapped["reason"],
                })
                continue

            story_number = int(mapped["story_chapter_number"])
            item["numbering_status"] = "reference_confirmed"
            item["numbering_reason"] = "physical_book_reference"

            mismatch = declared != story_number
            lead_mismatch = lead_declared is not None and lead_declared != story_number

            if mismatch or lead_mismatch:
                item["reference_override"] = True
                item["chapter_title"] = _rewrite_title_number(
                    item.get("chapter_title"), story_number
                )
                item["chapter_lead"] = _rewrite_lead_number(
                    item.get("chapter_lead"), story_number
                )
                reference_applied.append({
                    "source_url": url,
                    "source_declared_number": declared,
                    "story_chapter_number": story_number,
                    "chapter_type": "chapter",
                    "reason": mapped["reason"],
                })
            continue

        # Fora da cobertura física, preservar a fonte.
        if _is_extra_marker(item):
            item["chapter_type"] = "extra"
            item["story_chapter_number"] = None
            item["numbering_status"] = "extra_preserved"
            item["numbering_reason"] = "extra_marker_detected"
        else:
            item["chapter_type"] = "chapter"
            item["story_chapter_number"] = declared
            item["numbering_status"] = "ok"
            item["numbering_reason"] = "source_preserved_outside_reference"

        item["_sort_key"] = max_reference_order + 10000 + item["source_position"]

        previous_declared = (
            chapters[index - 1]["source_declared_number"] if index > 0 else None
        )
        next_declared = (
            chapters[index + 1]["source_declared_number"]
            if index + 1 < len(chapters)
            else None
        )

        reason = _review_reason(
            declared, previous_declared, next_declared, lead_declared
        )
        if reason and item["chapter_type"] != "extra":
            item["numbering_status"] = "review"
            item["numbering_reason"] = reason
            review.append({
                "source_position": item["source_position"],
                "source_declared_number": declared,
                "source_lead_declared_number": lead_declared,
                "source_title": item.get("source_chapter_title"),
                "previous_declared_number": previous_declared,
                "next_declared_number": next_declared,
                "reason": reason,
            })

    # URLs cobertas seguem a ordem editorial confirmada.
    chapters.sort(key=lambda chapter: chapter["_sort_key"])

    for corrected_position, item in enumerate(chapters, start=1):
        item["corrected_position"] = corrected_position
        item.pop("_sort_key", None)

    result = copy.deepcopy(data)
    result["chapters"] = chapters
    result["chapter_count"] = len(chapters)

    reference_confirmed_count = sum(
        1 for chapter in chapters
        if chapter["numbering_status"].startswith("reference_confirmed")
    )
    extra_count = sum(
        1 for chapter in chapters
        if chapter["chapter_type"] == "extra"
    )
    ok_count = sum(
        1 for chapter in chapters
        if chapter["numbering_status"] == "ok"
    )

    result["normalization"] = {
        "version": 5,
        "strategy": "physical_book_explicit_editorial_position_1_154",
        "source_entry_count": len(chapters),
        "reference_name": physical["reference_name"],
        "reference_main_chapters": physical["last_main_chapter"],
        "reference_confirmed_count": reference_confirmed_count,
        "reference_override_count": len(reference_applied),
        "reference_overrides_applied": reference_applied,
        "extra_count": extra_count,
        "review_count": len(review),
        "ok_count": ok_count,
        "review": review,
    }

    return result


def correct_json_file(input_path: str | Path) -> dict[str, Any]:
    input_path = Path(input_path)
    data = json.loads(input_path.read_text(encoding="utf-8"))

    corrected = _normalize(data)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"{input_path.stem}_ajustado.json"
    output.write_text(
        json.dumps(corrected, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    normalization = corrected["normalization"]

    return {
        "output": output,
        "source_entry_count": normalization["source_entry_count"],
        "extra_count": normalization["extra_count"],
        "reference_override_count": normalization["reference_override_count"],
        "reference_confirmed_count": normalization["reference_confirmed_count"],
        "review_count": normalization["review_count"],
    }

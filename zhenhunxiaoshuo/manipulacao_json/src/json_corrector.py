import json
import re
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]
JSON_DIR = PROJECT_ROOT / "manipulacao_json" / "output" / "extraidos"
REVIEWED_JSON_DIR = PROJECT_ROOT / "manipulacao_json" / "output" / "revisados"
DEFAULT_REFERENCE_FILE = (
    PROJECT_ROOT
    / "manipulacao_json"
    / "input"
    / "referencias"
    / "physical_book_overrides.json"
)

_CN_DIGITS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2,
    "三": 3, "四": 4, "五": 5, "六": 6,
    "七": 7, "八": 8, "九": 9,
}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def chinese_to_int(text):
    text = (text or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)

    total = 0
    current = 0
    found = False

    for char in text:
        if char in _CN_DIGITS:
            current = _CN_DIGITS[char]
            found = True
        elif char in _CN_UNITS:
            found = True
            unit = _CN_UNITS[char]
            if current == 0:
                current = 1
            total += current * unit
            current = 0
        else:
            return None

    return total + current if found else None


def int_to_chinese(number):
    if number <= 0 or number >= 10000:
        return str(number)

    digits = "零一二三四五六七八九"
    units = [(1000, "千"), (100, "百"), (10, "十")]
    remainder = number
    parts = []
    zero_pending = False

    for value, unit in units:
        digit = remainder // value
        remainder %= value

        if digit:
            if zero_pending and parts:
                parts.append("零")
                zero_pending = False
            parts.append(digits[digit])
            parts.append(unit)
        elif parts and remainder:
            zero_pending = True

    if remainder:
        if zero_pending and parts:
            parts.append("零")
        parts.append(digits[remainder])

    result = "".join(parts)
    if result.startswith("一十"):
        result = result[1:]
    return result


def is_extra(chapter):
    title = str(chapter.get("chapter_title") or chapter.get("csv_title") or "")
    lead = str(chapter.get("chapter_lead") or "")
    return "番外" in title or "番外" in lead


def extract_declared_number(text):
    text = str(text or "").strip()
    match = re.match(
        r"^第\s*([0-9零〇一二两三四五六七八九十百千]+)\s*章",
        text,
    )
    if not match:
        return None
    return chinese_to_int(match.group(1))


def extract_lead_number(lead):
    lead = str(lead or "").strip()
    match = re.match(
        r"^【\s*第\s*([0-9零〇一二两三四五六七八九十百千]+)\s*章",
        lead,
    )
    if not match:
        return None
    return chinese_to_int(match.group(1))


def replace_title_number(title, number):
    chinese_number = int_to_chinese(number)
    return re.sub(
        r"^第\s*[0-9零〇一二两三四五六七八九十百千]+\s*章",
        f"第{chinese_number}章",
        str(title or ""),
        count=1,
    )


def replace_lead_number(lead, number):
    chinese_number = int_to_chinese(number)
    return re.sub(
        r"^(【\s*)第\s*[0-9零〇一二两三四五六七八九十百千]+\s*章",
        rf"\1第{chinese_number}章",
        str(lead or ""),
        count=1,
    )


def load_reference_overrides(reference_file=None):
    path = Path(reference_file) if reference_file else DEFAULT_REFERENCE_FILE
    if not path.is_file():
        return {"reference_name": None, "overrides": []}

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("overrides"), list):
        raise ValueError("Arquivo de referência inválido: 'overrides' deve ser uma lista.")
    return data


def _neighbor_declared_numbers(chapters, index):
    previous_number = None
    next_number = None

    for i in range(index - 1, -1, -1):
        if is_extra(chapters[i]):
            continue
        previous_number = extract_declared_number(chapters[i].get("chapter_title"))
        break

    for i in range(index + 1, len(chapters)):
        if is_extra(chapters[i]):
            continue
        next_number = extract_declared_number(chapters[i].get("chapter_title"))
        break

    return previous_number, next_number


def _apply_reference_overrides(chapters, reference_data):
    by_url = {
        item.get("source_url"): item
        for item in reference_data.get("overrides", [])
        if item.get("source_url")
    }

    applied = []

    for chapter in chapters:
        source_url = chapter.get("source_url")
        override = by_url.get(source_url)
        if not override:
            continue

        chapter["reference_override"] = True
        chapter["reference_reason"] = override.get("reason")
        chapter["chapter_type"] = override.get(
            "chapter_type",
            chapter.get("chapter_type"),
        )
        chapter["story_chapter_number"] = override.get("story_chapter_number")

        corrected_title = override.get("corrected_title")
        if corrected_title:
            chapter["chapter_title"] = corrected_title

        if (
            chapter.get("chapter_type") == "chapter"
            and chapter.get("story_chapter_number") is not None
        ):
            chapter["chapter_lead"] = replace_lead_number(
                chapter.get("chapter_lead"),
                chapter["story_chapter_number"],
            )
            chapter["numbering_status"] = "reference_confirmed"
            chapter["numbering_reason"] = "physical_book_reference"
        else:
            chapter["numbering_status"] = "reference_confirmed_extra"
            chapter["numbering_reason"] = "physical_book_reference"

        applied.append({
            "source_url": source_url,
            "story_chapter_number": chapter.get("story_chapter_number"),
            "chapter_type": chapter.get("chapter_type"),
            "reason": override.get("reason"),
        })

    # Reorder only when the physical reference explicitly asks for it.
    for override in reference_data.get("overrides", []):
        source_url = override.get("source_url")
        move_after = override.get("move_after_source_url")
        if not source_url or not move_after:
            continue

        source_idx = next(
            (i for i, ch in enumerate(chapters) if ch.get("source_url") == source_url),
            None,
        )
        target_idx = next(
            (i for i, ch in enumerate(chapters) if ch.get("source_url") == move_after),
            None,
        )

        if source_idx is None or target_idx is None:
            continue

        item = chapters.pop(source_idx)

        # Recalculate target after pop.
        target_idx = next(
            i for i, ch in enumerate(chapters)
            if ch.get("source_url") == move_after
        )
        chapters.insert(target_idx + 1, item)

    # Preserve the original physical source position and add the corrected order.
    for corrected_position, chapter in enumerate(chapters, start=1):
        chapter["corrected_position"] = corrected_position

    return applied


def normalize_book_json(data, reference_file=None):
    if not isinstance(data, dict):
        raise ValueError("JSON inválido: esperado objeto na raiz.")
    if not isinstance(data.get("chapters"), list):
        raise ValueError("JSON inválido: esperado campo 'chapters' como lista.")

    result = deepcopy(data)
    chapters = result["chapters"]

    extras = []
    review = []
    ok_count = 0

    # First pass: preserve the source exactly and only diagnose.
    for index, chapter in enumerate(chapters):
        source_position = index + 1
        original_title = str(chapter.get("chapter_title") or "")
        original_lead = str(chapter.get("chapter_lead") or "")
        declared_number = extract_declared_number(original_title)
        lead_number = extract_lead_number(original_lead)

        chapter["source_position"] = source_position
        chapter["source_declared_number"] = declared_number
        chapter["source_lead_declared_number"] = lead_number
        chapter["source_chapter_title"] = original_title
        chapter["source_chapter_lead"] = original_lead
        chapter["reference_override"] = False

        if is_extra(chapter):
            chapter["chapter_type"] = "extra"
            chapter["story_chapter_number"] = None
            chapter["numbering_status"] = "extra_preserved"
            chapter["numbering_reason"] = "extra_marker_detected"
            extras.append({
                "source_position": source_position,
                "source_declared_number": declared_number,
                "source_title": original_title,
            })
            continue

        chapter["chapter_type"] = "chapter"
        chapter["story_chapter_number"] = declared_number

        previous_number, next_number = _neighbor_declared_numbers(chapters, index)

        duplicate_neighbor = (
            declared_number is not None
            and declared_number in {previous_number, next_number}
        )
        lead_disagrees = (
            lead_number is not None
            and declared_number is not None
            and lead_number != declared_number
        )
        suspicious_jump = (
            previous_number is not None
            and declared_number is not None
            and abs(declared_number - previous_number) > 1
        )

        reasons = []
        if duplicate_neighbor:
            reasons.append("duplicate_neighbor")
        if lead_disagrees:
            reasons.append("title_lead_disagree")
        if suspicious_jump:
            reasons.append("suspicious_jump")

        if reasons:
            chapter["numbering_status"] = "review"
            chapter["numbering_reason"] = ",".join(reasons)
            review.append({
                "source_position": source_position,
                "source_declared_number": declared_number,
                "source_lead_declared_number": lead_number,
                "source_title": original_title,
                "previous_declared_number": previous_number,
                "next_declared_number": next_number,
                "reason": chapter["numbering_reason"],
            })
        else:
            chapter["numbering_status"] = "ok"
            chapter["numbering_reason"] = "source_preserved"
            ok_count += 1

    reference_data = load_reference_overrides(reference_file)
    applied_reference = _apply_reference_overrides(chapters, reference_data)

    # Remove resolved items from the review summary.
    resolved_urls = {item["source_url"] for item in applied_reference}
    review = [
        item for item in review
        if chapters[item["source_position"] - 1].get("source_url") not in resolved_urls
    ]

    result["chapter_count"] = len(chapters)
    result["normalization"] = {
        "version": 3,
        "strategy": "source_preserved_plus_physical_reference",
        "source_entry_count": len(chapters),
        "extra_count": len(extras),
        "reference_name": reference_data.get("reference_name"),
        "reference_override_count": len(applied_reference),
        "reference_overrides_applied": applied_reference,
        "review_count": len(review),
        "ok_count": ok_count,
        "review": review,
    }

    return result


def correct_json_file(json_path, output_path=None, reference_file=None):
    json_path = Path(json_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    corrected = normalize_book_json(data, reference_file=reference_file)

    if output_path is None:
        output_path = REVIEWED_JSON_DIR / f"{json_path.stem}_ajustado.json"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(corrected, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "output": output_path,
        **corrected["normalization"],
    }

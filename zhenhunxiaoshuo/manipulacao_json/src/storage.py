import json
from pathlib import Path

def save_book(chapters, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "chapter_count": len(chapters),
        "chapters": [chapter.to_dict() for chapter in chapters],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path

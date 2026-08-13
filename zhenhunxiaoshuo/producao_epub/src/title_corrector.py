from __future__ import annotations

from pathlib import Path

from zhenhunxiaoshuo.identity_contract import (
    IdentityContractError,
    correct_epub_titles_by_identity,
)

MODULE_ROOT = Path(__file__).resolve().parents[1]
# Compatibilidade com menu.py atual.
ORIGINAL_EPUB_DIR = MODULE_ROOT / "output" / "3_geracao"
TRANSLATED_EPUB_DIR = MODULE_ROOT / "input" / "traduzidos"
TITLE_CSV_DIR = MODULE_ROOT / "input" / "capitulos"
CORRECTED_EPUB_DIR = MODULE_ROOT / "output" / "4_pos_trad"


class StructuralMatchError(ValueError):
    pass


def correct_epub_titles(original_epub, translated_epub, csv_file):
    try:
        result = correct_epub_titles_by_identity(
            original_epub,
            translated_epub,
            csv_file,
        )
    except IdentityContractError as exc:
        raise StructuralMatchError(str(exc)) from exc

    return result

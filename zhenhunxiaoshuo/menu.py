import json
import os
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from .manipulacao_json.src.json_corrector import REVIEWED_JSON_DIR, correct_json_file
from .manipulacao_json.src.scraper import run as run_scraper
from .producao_epub.src.epub_builder import (
    MODE_NO_REDUNDANCY,
    MODE_STANDARD,
    build_epub,
    find_cover,
)
from .producao_epub.src.title_corrector import (
    ORIGINAL_EPUB_DIR,
    TITLE_CSV_DIR,
    TRANSLATED_EPUB_DIR,
    correct_epub_titles,
)
from .producao_epub.src.epub_validator import (
    FINAL_EPUB_DIR,
    REFERENCE_FILE,
    validate_final_epub,
)

ROOT = Path(__file__).resolve().parent
EXTRACTION_DIR = ROOT / "manipulacao_json" / "output" / "1_extracao"

HEX = {
    "text": "#2c3e50",
    "separator": "#ffd166",
    "sec_json": "#ef476f",
    "item_json": "#ff8a5c",
    "sec_epub": "#06d6a0",
    "item_epub": "#118ab2",
    "number": "#7209b7",
    "prompt": "#4361ee",
}


def _supports_color():
    return (
        os.environ.get("NO_COLOR") is None
        and sys.stdout.isatty()
        and os.environ.get("TERM", "") != "dumb"
    )


USE_COLOR = _supports_color()


def _ansi(hex_color, text, bold=False):
    if not USE_COLOR:
        return str(text)
    value = hex_color.lstrip("#")
    r, g, b = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    weight = "1;" if bold else ""
    return f"\033[{weight}38;2;{r};{g};{b}m{text}\033[0m"


def c(key, text, bold=False):
    return _ansi(HEX[key], text, bold=bold)


def ask_number(prompt, valid):
    while True:
        raw = input(c("prompt", prompt, bold=True)).strip()
        if raw.isdigit() and int(raw) in valid:
            return int(raw)
        print("Opção inválida.")


def _mtime(path):
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%d-%m-%y %H:%M:%S")


def _epub_title(path):
    try:
        with zipfile.ZipFile(path) as zf:
            container = ET.fromstring(zf.read("META-INF/container.xml"))
            rootfile = next(e for e in container.iter() if e.tag.endswith("rootfile"))
            opf = ET.fromstring(zf.read(rootfile.get("full-path")))
            for element in opf.iter():
                if element.tag.endswith("title") and element.text:
                    return element.text.strip()
    except Exception:
        pass
    return path.stem.replace("_", " ")


def select_file(files, heading, title_func=None, relative_base=None):
    files = list(files)
    if not files:
        print(f"\nNenhum arquivo encontrado para: {heading}")
        return None

    print(f"\n{heading}:")
    for idx, path in enumerate(files, 1):
        label = title_func(path) if title_func else path.stem.replace("_", " ").title()
        print(f"  {c('number', str(idx)+'.', bold=True)} {label}  [{_mtime(path)}]")
        if relative_base:
            try:
                shown = path.relative_to(relative_base)
            except ValueError:
                shown = path
            print(f"     └─ {shown}")
    print(f"\n  {c('number', '0.', bold=True)} Voltar")
    choice = ask_number("\nSelecione uma opção › ", set(range(len(files) + 1)))
    return None if choice == 0 else files[choice - 1]


def main_header():
    print()
    print(c("number", "ZHENHUNXIAOSHUO", bold=True))
    print(c("separator", "━" * 50))


def main_menu():
    main_header()
    print()
    print(c("sec_json", "● MANIPULAÇÃO DE JSON", bold=True))
    print()
    print(f"  {c('number','1.',bold=True)} {c('item_json','Extração')}       Extrair capítulos e gerar JSON")
    print()
    print(f"  {c('number','2.',bold=True)} {c('item_json','Revisão')}        Ajustar JSON com referência física")
    print("\n")
    print(c("sec_epub", "● PRODUÇÃO DE EPUB", bold=True))
    print()
    print(f"  {c('number','3.',bold=True)} {c('item_epub','Geração')}        Gerar EPUB final")
    print()
    print(f"  {c('number','4.',bold=True)} {c('item_epub','Pós-Trad')}       Ajustar títulos do EPUB traduzido")
    print()
    print(f"  {c('number','5.',bold=True)} {c('item_epub','Validação')}      Validar EPUB final com referência física")
    print("\n")
    print(c("separator", "━" * 50))
    print(f"  {c('number','0.',bold=True)} Sair")
    print()


def menu_extract():
    print("\nEXTRAÇÃO\n")
    print(f"  {c('number','1.',bold=True)} Todos os capítulos")
    print()
    print(f"  {c('number','2.',bold=True)} Informar quantidade")
    print()
    print(f"  {c('number','0.',bold=True)} Voltar")
    choice = ask_number("\nSelecione uma opção › ", {0,1,2})
    if choice == 0:
        return
    if choice == 1:
        output = run_scraper()
    else:
        while True:
            raw = input("Quantos capítulos deseja gerar? ").strip()
            if raw.isdigit() and int(raw) > 0:
                output = run_scraper(limit=int(raw))
                break
            print("Informe um inteiro maior que zero.")
    print(f"\nArquivo:\n  {output}")


def menu_review():
    files = sorted(EXTRACTION_DIR.glob("*.json"))
    selected = select_file(files, "JSONs extraídos disponíveis", relative_base=ROOT)
    if selected is None:
        return
    result = correct_json_file(selected)
    print(f"\nRevisão concluída.\n\nArquivo:\n  {result['output']}")


def menu_generate():
    files = sorted(REVIEWED_JSON_DIR.glob("*.json"))
    selected = select_file(files, "JSONs revisados disponíveis", relative_base=ROOT)
    if selected is None:
        return

    print("\nGERAÇÃO\n")
    print(f"  {c('number','1.',bold=True)} EPUB bruto")
    print()
    print(f"  {c('number','2.',bold=True)} EPUB polido")
    print()
    print(f"  {c('number','0.',bold=True)} Voltar")
    choice = ask_number("\nSelecione uma opção › ", {0,1,2})
    if choice == 0:
        return
    mode = MODE_STANDARD if choice == 1 else MODE_NO_REDUNDANCY
    output = build_epub(selected, mode=mode)
    print(f"\nGeração concluída.\n\nArquivo:\n  {output}")


def menu_post_translation():
    originals = sorted(ORIGINAL_EPUB_DIR.glob("*_polido.epub"))
    original = select_file(
        originals, "EPUB original em chinês",
        title_func=_epub_title, relative_base=ROOT / "producao_epub" / "output"
    )
    if original is None:
        return

    TRANSLATED_EPUB_DIR.mkdir(parents=True, exist_ok=True)
    translated = select_file(
        sorted(TRANSLATED_EPUB_DIR.glob("*.epub")),
        "EPUB traduzido",
        title_func=_epub_title, relative_base=ROOT / "producao_epub"
    )
    if translated is None:
        return

    csv_file = select_file(
        sorted(TITLE_CSV_DIR.glob("*.csv")),
        "Referência dos capítulos",
        relative_base=ROOT / "producao_epub"
    )
    if csv_file is None:
        return

    print("\nPÓS-TRADUÇÃO")
    print(c("separator", "─" * 50))
    print(f"\nOriginal em chinês:\n  └─ {original.relative_to(ROOT / 'producao_epub')}")
    print(f"\nTraduzido:\n  └─ {translated.relative_to(ROOT / 'producao_epub')}")
    print(f"\nCapítulos:\n  └─ {csv_file.relative_to(ROOT / 'producao_epub')}")
    print("\n" + c("separator", "─" * 50))
    print(f"  {c('number','1.',bold=True)} Validar e corrigir títulos")
    print(f"  {c('number','0.',bold=True)} Voltar")
    choice = ask_number("\nSelecione uma opção › ", {0,1})
    if choice == 0:
        return

    result = correct_epub_titles(original, translated, csv_file)
    print(f"\nPós-Trad concluída.\n\nArquivo:\n  {result['output']}")


def menu_validation():
    FINAL_EPUB_DIR.mkdir(parents=True, exist_ok=True)
    final_epub = select_file(
        sorted(FINAL_EPUB_DIR.glob("*.epub")),
        "EPUBs finais disponíveis",
        title_func=_epub_title,
        relative_base=ROOT / "producao_epub" / "output",
    )
    if final_epub is None:
        return

    print("\nVALIDAÇÃO DO EPUB")
    print(c("separator", "─" * 50))
    print(f"\nEPUB final:\n  └─ {final_epub.relative_to(ROOT / 'producao_epub')}")
    print(f"\nReferência física:\n  └─ {REFERENCE_FILE.relative_to(ROOT)}")
    print("\n" + c("separator", "─" * 50))
    print(f"  {c('number','1.',bold=True)} Validar")
    print(f"  {c('number','0.',bold=True)} Voltar")
    choice = ask_number("\nSelecione uma opção › ", {0,1})
    if choice == 0:
        return

    result = validate_final_epub(final_epub)
    print("\nVALIDAÇÃO CONCLUÍDA")
    print(f"\nStatus: {result['status']}")
    print(f"Erros: {len(result['errors'])}")
    print(f"Avisos: {len(result['warnings'])}")
    print(f"\nRelatório:\n  {result['report']}")


def main():
    while True:
        main_menu()
        choice = ask_number("Selecione uma opção › ", {0,1,2,3,4,5})
        if choice == 0:
            return
        if choice == 1:
            menu_extract()
        elif choice == 2:
            menu_review()
        elif choice == 3:
            menu_generate()
        elif choice == 4:
            menu_post_translation()
        elif choice == 5:
            menu_validation()


if __name__ == "__main__":
    main()

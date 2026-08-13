import json
import os
import sys
from pathlib import Path

from .manipulacao_json.src.json_corrector import (
    REVIEWED_JSON_DIR,
    correct_json_file,
)
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
    StructuralMatchError,
    correct_epub_titles,
)

ROOT = Path(__file__).resolve().parent


def _supports_color():
    if os.environ.get("NO_COLOR") is not None:
        return False
    if not sys.stdout.isatty():
        return False
    return os.environ.get("TERM", "") != "dumb"


USE_COLOR = _supports_color()


def color(text, code):
    if not USE_COLOR:
        return str(text)
    return f"\033[{code}m{text}\033[0m"


def bold(text):
    return color(text, "1")


def yellow(text):
    return color(text, "1;33")


def green(text):
    return color(text, "1;32")


def cyan(text):
    return color(text, "1;36")


def red(text):
    return color(text, "1;31")


def gray(text):
    return color(text, "90")


def load_config():
    return json.loads(
        (ROOT / "config_zhenhunxiaoshuo.json").read_text(
            encoding="utf-8"
        )
    )


def display_path(path):
    if not path:
        return "não encontrada"

    path = Path(path)

    try:
        index = path.parts.index("Fominha_de_Novel")
        return str(Path(*path.parts[index:]))
    except ValueError:
        return str(path)


def ask_number(prompt, valid_values):
    while True:
        raw = input(prompt).strip()

        if raw.isdigit():
            value = int(raw)
            if value in valid_values:
                return value

        print(red("Opção inválida. Escolha uma opção numerada."))


def option(number, icon, name, description=""):
    prefix = f"  {green(number)}. {icon} "
    if description:
        print(
            f"{prefix}{bold(name):<22} {description}"
        )
    else:
        print(f"{prefix}{name}")


def separator():
    print(gray("  " + "─" * 50))


def main_header():
    print()
    print(cyan(bold("  ZHENHUNXIAOSHUO")))
    separator()


def select_file(files, heading):
    files = list(files)

    if not files:
        print(f"\n{yellow('AVISO:')} nenhum arquivo encontrado.")
        return None

    print(f"\n{bold(heading)}:")
    for index, path in enumerate(files, start=1):
        print(f"  {green(index)}. {path.name}")
    print(f"  {green(0)}. Voltar")

    value = ask_number(
        "\nSelecione uma opção › ",
        set(range(0, len(files) + 1)),
    )

    if value == 0:
        return None

    return files[value - 1]


def json_files():
    config = load_config()
    directory = ROOT / config["output_dir"]
    directory.mkdir(parents=True, exist_ok=True)
    return sorted(directory.glob("*.json"))


def adjusted_json_files():
    REVIEWED_JSON_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(REVIEWED_JSON_DIR.glob("*_ajustado.json"))

    if not files:
        # Compatibilidade temporária com versões anteriores do corretor.
        files = sorted(REVIEWED_JSON_DIR.glob("*_corrigido.json"))

    return files


def menu_json():
    print()
    print(yellow(bold("  [🟡 EXTRAÇÃO DE JSON]")))
    print(f"  {green(1)}. Todos os capítulos")
    print(f"  {green(2)}. Informar quantidade")
    print(f"  {green(0)}. Voltar")

    choice = ask_number(
        "\nSelecione uma opção › ",
        {0, 1, 2},
    )

    if choice == 0:
        return

    if choice == 1:
        output = run_scraper()
        print(f"\n{green('OK:')} {display_path(output)}")
        return

    while True:
        raw = input("Quantos capítulos deseja gerar? ").strip()

        if raw.isdigit() and int(raw) > 0:
            output = run_scraper(limit=int(raw))
            print(f"\n{green('OK:')} {display_path(output)}")
            return

        print(red("Informe um número inteiro maior que zero."))


def generate_epub(mode):
    selected = select_file(
        adjusted_json_files(),
        "JSONs revisados disponíveis",
    )
    if selected is None:
        return

    config = load_config()
    data = json.loads(selected.read_text(encoding="utf-8"))
    book = config["book"]
    cover = find_cover(config)

    print()
    print(f"  {bold('JSON:')} {selected.name}")
    print(f"  {bold('Título:')} {book['title']}")
    print(f"  {bold('Autor:')} {book['author']}")
    print(f"  {bold('Idioma:')} {book['language']}")
    print(f"  {bold('Capítulos:')} {len(data.get('chapters') or [])}")
    print(f"  {bold('Capa:')} {display_path(cover)}")

    print()
    print(f"  {green(1)}. Gerar EPUB")
    print(f"  {green(0)}. Voltar")

    choice = ask_number(
        "\nSelecione uma opção › ",
        {0, 1},
    )

    if choice == 0:
        return

    output = build_epub(selected, mode=mode)
    print(f"\n{green('OK:')} {display_path(output)}")


def menu_epub():
    while True:
        print()
        print(green(bold("  [🟢 PRODUÇÃO DE EPUB]")))
        option(
            "1",
            "📘",
            "EPUB original",
            "Estrutura original da fonte",
        )
        option(
            "2",
            "📗",
            "EPUB sem redundância",
            "Título consolidado + frase destacada",
        )
        print(f"  {green(0)}. ↩️  Voltar")

        choice = ask_number(
            "\nSelecione uma opção › ",
            {0, 1, 2},
        )

        if choice == 0:
            return
        if choice == 1:
            generate_epub(MODE_STANDARD)
        elif choice == 2:
            generate_epub(MODE_NO_REDUNDANCY)


def menu_correct_json():
    print()
    print(yellow(bold("  [🟡 REVISÃO DE JSON]")))

    files = [
        path
        for path in json_files()
        if not path.stem.endswith("_ajustado")
        and not path.stem.endswith("_corrigido")
    ]

    selected = select_file(
        files,
        "JSONs disponíveis para ajuste",
    )
    if selected is None:
        return

    print()
    print("  • preserva a fonte original em campos source_*")
    print("  • aplica apenas referências físicas confirmadas")
    print("  • mantém casos duvidosos como review")
    print("  • gera um novo JSON sem sobrescrever o original")

    print()
    print(f"  {green(1)}. Gerar JSON ajustado")
    print(f"  {green(0)}. Voltar")

    choice = ask_number(
        "\nSelecione uma opção › ",
        {0, 1},
    )
    if choice == 0:
        return

    result = correct_json_file(selected)

    print(f"\n{green('OK:')} {display_path(result['output'])}")
    print(
        "  Ajustes confirmados: "
        f"{result['reference_override_count']}"
    )
    print(f"  Casos para revisão: {result['review_count']}")


def menu_correct_translated_titles():
    print()
    print(green(bold("  [🟢 PÓS-TRADUÇÃO]")))

    ORIGINAL_EPUB_DIR.mkdir(parents=True, exist_ok=True)
    TRANSLATED_EPUB_DIR.mkdir(parents=True, exist_ok=True)
    TITLE_CSV_DIR.mkdir(parents=True, exist_ok=True)

    original_epub = select_file(
        sorted(ORIGINAL_EPUB_DIR.glob("*.epub")),
        "EPUBs originais disponíveis",
    )
    if original_epub is None:
        return

    translated_epub = select_file(
        sorted(TRANSLATED_EPUB_DIR.glob("*.epub")),
        "EPUBs traduzidos disponíveis",
    )
    if translated_epub is None:
        return

    csv_file = select_file(
        sorted(TITLE_CSV_DIR.glob("*.csv")),
        "CSVs de títulos disponíveis",
    )
    if csv_file is None:
        return

    print()
    print(f"  {bold('EPUB original:')} {original_epub.name}")
    print(f"  {bold('EPUB traduzido:')} {translated_epub.name}")
    print(f"  {bold('CSV:')} {csv_file.name}")

    print()
    print(f"  {green(1)}. Validar estrutura e corrigir títulos")
    print(f"  {green(0)}. Voltar")

    choice = ask_number(
        "\nSelecione uma opção › ",
        {0, 1},
    )
    if choice == 0:
        return

    try:
        result = correct_epub_titles(
            original_epub,
            translated_epub,
            csv_file,
        )
    except StructuralMatchError as error:
        print(f"\n{red(str(error))}")
        return

    print()
    print(green(bold("  Correção concluída")))
    print(f"  Separador CSV: {repr(result['delimiter'])}")
    print(f"  Capítulos validados: {result['chapter_count']}")
    print(f"  Entradas estruturais: {result['mapped_entries']}")
    print(f"  Títulos alterados: {result['corrected_count']}")
    print(
        f"  Spine preservado: "
        f"{'sim' if result['spine_preserved'] else 'não'}"
    )
    print(
        f"  nav.xhtml atualizado: "
        f"{'sim' if result['nav_updated'] else 'não'}"
    )
    print(
        f"  toc.ncx atualizado: "
        f"{'sim' if result['ncx_updated'] else 'não'}"
    )
    print(f"  {green('Saída:')} {display_path(result['output'])}")


def main():
    while True:
        main_header()

        print()
        print(yellow(bold("  [🟡 MANIPULAÇÃO DE JSON]")))
        option(
            "1",
            "📂",
            "Extração",
            "Extrair capítulos e gerar JSON",
        )
        option(
            "2",
            "📝",
            "Revisão",
            "Ajustar JSON com referência física",
        )

        print()
        print(green(bold("  [🟢 PRODUÇÃO DE EPUB]")))
        option(
            "3",
            "📚",
            "Geração",
            "Gerar arquivo EPUB final",
        )
        option(
            "4",
            "🔧",
            "Pós-Trad",
            "Ajustar títulos do EPUB traduzido",
        )

        print()
        separator()
        print(f"  {green(0)}. 🚪 Sair")

        choice = ask_number(
            "  Selecione uma opção › ",
            {0, 1, 2, 3, 4},
        )

        if choice == 0:
            print(gray("\n  Encerrado."))
            return
        if choice == 1:
            menu_json()
        elif choice == 2:
            menu_correct_json()
        elif choice == 3:
            menu_epub()
        elif choice == 4:
            menu_correct_translated_titles()


if __name__ == "__main__":
    main()

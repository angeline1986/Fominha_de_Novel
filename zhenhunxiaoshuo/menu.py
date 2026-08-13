import json
from pathlib import Path

from .epub_builder import MODE_NO_REDUNDANCY, MODE_STANDARD, build_epub, find_cover
from .scraper import run as run_scraper
from .title_corrector import (
    TITLE_CSV_DIR,
    TRANSLATED_EPUB_DIR,
    correct_epub_titles,
)

ROOT = Path(__file__).resolve().parent


def load_config():
    return json.loads(
        (ROOT / "config_zhenhunxiaoshuo.json").read_text(encoding="utf-8")
    )


def display_path(path):
    if not path:
        return "não encontrada"

    path = Path(path)

    try:
        index = path.parts.index("Fominha_de_Novel")
        return str(Path(*path.parts[index:]))
    except ValueError:
        try:
            return str(path.relative_to(ROOT.parent.parent))
        except ValueError:
            return str(path)


def ask_number(prompt, valid_values):
    while True:
        raw = input(prompt).strip()

        if raw.isdigit():
            value = int(raw)
            if value in valid_values:
                return value

        print("Opção inválida. Digite uma das opções numeradas.")


def menu_json():
    while True:
        print("\n=== Gerar JSON ===")
        print("1. Todos os capítulos")
        print("2. Informar quantidade")
        print("0. Voltar")

        option = ask_number("\nEscolha uma opção: ", {0, 1, 2})

        if option == 0:
            return

        if option == 1:
            output = run_scraper()
            print(f"\nJSON: {display_path(output)}")
            return

        while True:
            raw = input("Quantos capítulos deseja gerar? ").strip()

            if raw.isdigit() and int(raw) > 0:
                output = run_scraper(limit=int(raw))
                print(f"\nJSON: {display_path(output)}")
                return

            print("Quantidade inválida. Informe um número inteiro maior que zero.")


def json_files():
    config = load_config()
    json_dir = ROOT / config["output_dir"] / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    return sorted(json_dir.glob("*.json"))


def select_file(files, heading):
    files = list(files)

    if not files:
        print(f"\nNenhum arquivo encontrado em {heading}.")
        return None

    print(f"\n{heading}:")
    for index, path in enumerate(files, start=1):
        print(f"{index}. {path.name}")
    print("0. Voltar")

    option = ask_number(
        "\nEscolha uma opção: ",
        set(range(0, len(files) + 1)),
    )

    if option == 0:
        return None

    return files[option - 1]


def select_json():
    return select_file(json_files(), "JSONs disponíveis")


def generate_epub(mode):
    config = load_config()
    selected = select_json()

    if selected is None:
        return

    data = json.loads(selected.read_text(encoding="utf-8"))
    book = config["book"]
    chapter_count = len(data.get("chapters") or [])
    cover = find_cover(config)

    label = "Gerar EPUB" if mode == MODE_STANDARD else "Gerar EPUB sem redundância"

    print(f"\n=== {label} ===")
    print(f"JSON: {selected.name}")
    print(f"Título: {book['title']}")
    print(f"Autor: {book['author']}")
    print(f"Idioma: {book['language']}")
    print(f"Capítulos: {chapter_count}")
    print(f"Capa: {display_path(cover)}")

    print("\n1. Gerar EPUB")
    print("0. Voltar")

    confirm = ask_number("\nEscolha uma opção: ", {0, 1})

    if confirm == 0:
        return

    output = build_epub(selected, mode=mode)
    print(f"\nOK: EPUB gerado em {display_path(output)}")

    if not cover:
        print("AVISO: EPUB gerado sem capa.")


def menu_correct_translated_titles():
    print("\n=== Ajustar títulos do EPUB traduzido ===")

    TRANSLATED_EPUB_DIR.mkdir(parents=True, exist_ok=True)
    TITLE_CSV_DIR.mkdir(parents=True, exist_ok=True)

    epub = select_file(
        sorted(TRANSLATED_EPUB_DIR.glob("*.epub")),
        "EPUBs traduzidos disponíveis",
    )

    if epub is None:
        return

    csv_file = select_file(
        sorted(TITLE_CSV_DIR.glob("*.csv")),
        "CSVs de títulos disponíveis",
    )

    if csv_file is None:
        return

    print("\nArquivos selecionados:")
    print(f"EPUB: {epub.name}")
    print(f"CSV: {csv_file.name}")

    print("\n1. Aplicar correção")
    print("0. Voltar")

    confirm = ask_number("\nEscolha uma opção: ", {0, 1})

    if confirm == 0:
        return

    result = correct_epub_titles(epub, csv_file)

    print("\n=== Resultado ===")
    print(f"Títulos disponíveis no CSV: {result['titles_in_csv']}")
    print(f"Capítulos alterados: {result['corrected_count']}")
    print(f"nav.xhtml atualizado: {'sim' if result['nav_updated'] else 'não'}")
    print(f"toc.ncx atualizado: {'sim' if result['ncx_updated'] else 'não'}")
    print(f"Saída: {display_path(result['output'])}")


def main():
    while True:
        print("\n=== Zhenhunxiaoshuo ===")
        print("1. Gerar JSON dos capítulos")
        print("2. Gerar EPUB")
        print("3. Gerar EPUB sem redundância")
        print("4. Ajustar títulos do EPUB traduzido")
        print("0. Sair")

        option = ask_number("\nEscolha uma opção: ", {0, 1, 2, 3, 4})

        if option == 0:
            print("Encerrado.")
            return

        if option == 1:
            menu_json()
        elif option == 2:
            generate_epub(MODE_STANDARD)
        elif option == 3:
            generate_epub(MODE_NO_REDUNDANCY)
        elif option == 4:
            menu_correct_translated_titles()


if __name__ == "__main__":
    main()

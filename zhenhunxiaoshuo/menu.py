import json
from pathlib import Path

from .epub_builder import build_epub
from .scraper import run as run_scraper

ROOT = Path(__file__).resolve().parent


def load_config():
    return json.loads((ROOT / "config_zhenhunxiaoshuo.json").read_text(encoding="utf-8"))


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
            run_scraper()
            return

        while True:
            raw = input("Quantos capítulos deseja gerar? ").strip()
            if raw.isdigit() and int(raw) > 0:
                run_scraper(limit=int(raw))
                return
            print("Quantidade inválida. Informe um número inteiro maior que zero.")


def json_files():
    config = load_config()
    json_dir = ROOT / config["output_dir"] / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    return sorted(json_dir.glob("*.json"))


def menu_epub():
    config = load_config()
    files = json_files()

    print("\n=== Gerar EPUB ===")

    if not files:
        print("Nenhum JSON encontrado em output/json.")
        print("Gere o JSON dos capítulos primeiro.")
        return

    print("\nJSONs disponíveis:")
    for index, path in enumerate(files, start=1):
        print(f"{index}. {path.name}")
    print("0. Voltar")

    option = ask_number("\nEscolha uma opção: ", set(range(0, len(files) + 1)))
    if option == 0:
        return

    selected = files[option - 1]
    data = json.loads(selected.read_text(encoding="utf-8"))
    book = config["book"]
    chapter_count = len(data.get("chapters") or [])

    print("\nLivro selecionado:")
    print(f"JSON: {selected.name}")
    print(f"Título: {book['title']}")
    print(f"Autor: {book['author']}")
    print(f"Idioma: {book['language']}")
    print(f"Capítulos: {chapter_count}")

    print("\n1. Gerar EPUB")
    print("0. Voltar")
    confirm = ask_number("\nEscolha uma opção: ", {0, 1})

    if confirm == 0:
        return

    output = build_epub(selected)
    print(f"\nOK: EPUB gerado em {output}")


def main():
    while True:
        print("\n=== Zhenhunxiaoshuo ===")
        print("1. Gerar JSON dos capítulos")
        print("2. Gerar EPUB")
        print("0. Sair")

        option = ask_number("\nEscolha uma opção: ", {0, 1, 2})

        if option == 0:
            print("Encerrado.")
            return
        if option == 1:
            menu_json()
        else:
            menu_epub()


if __name__ == "__main__":
    main()

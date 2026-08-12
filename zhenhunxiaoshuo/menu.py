import json
from pathlib import Path

from .epub_builder import MODE_NO_REDUNDANCY, MODE_STANDARD, build_epub, find_cover
from .scraper import run as run_scraper

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


def _select_json():
    files = json_files()
    if not files:
        print("Nenhum JSON encontrado em output/json.")
        print("Gere o JSON dos capítulos primeiro.")
        return None

    print("\nJSONs disponíveis:")
    for index, path in enumerate(files, start=1):
        print(f"{index}. {path.name}")
    print("0. Voltar")

    option = ask_number("\nEscolha uma opção: ", set(range(0, len(files) + 1)))
    if option == 0:
        return None
    return files[option - 1]


def _generate_epub(mode):
    config = load_config()
    print("\n=== Gerar EPUB ===" if mode == MODE_STANDARD else "\n=== Gerar EPUB sem redundância ===")

    selected = _select_json()
    if selected is None:
        return

    data = json.loads(selected.read_text(encoding="utf-8"))
    book = config["book"]
    chapter_count = len(data.get("chapters") or [])
    cover = find_cover(config)

    print("\nLivro selecionado:")
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
    print(f"\nOK: EPUB gerado em {output}")
    if not cover:
        print("AVISO: EPUB gerado sem capa. Coloque a imagem em Fominha_de_Novel/zhenhunxiaoshuo/input/cover.jpg.")


def main():
    while True:
        print("\n=== Zhenhunxiaoshuo ===")
        print("1. Gerar JSON dos capítulos")
        print("2. Gerar EPUB")
        print("3. Gerar EPUB sem redundância")
        print("0. Sair")

        option = ask_number("\nEscolha uma opção: ", {0, 1, 2, 3})
        if option == 0:
            print("Encerrado.")
            return
        if option == 1:
            menu_json()
        elif option == 2:
            _generate_epub(MODE_STANDARD)
        else:
            _generate_epub(MODE_NO_REDUNDANCY)


if __name__ == "__main__":
    main()

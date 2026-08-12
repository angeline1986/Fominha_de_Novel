import json
from pathlib import Path

from .generate_epub import run as generate_epub
from .scraper import run as scrape

ROOT = Path(__file__).resolve().parent


def load_config():
    return json.loads(
        (ROOT / "config_zhenhunxiaoshuo.json").read_text(encoding="utf-8")
    )


def main():
    while True:
        print("\n=== Zhenhunxiaoshuo ===")
        print("1. Gerar JSON dos capítulos")
        print("2. Gerar EPUB")
        print("0. Sair")

        choice = input("\nEscolha uma opção: ").strip()

        if choice == "1":
            _json_menu()
        elif choice == "2":
            _epub_menu()
        elif choice == "0":
            print("Encerrado.")
            return
        else:
            print("Opção inválida.")


def _json_menu():
    print("\n=== Gerar JSON ===")
    print("1. Todos os capítulos")
    print("2. Informar quantidade")
    print("0. Voltar")

    choice = input("\nEscolha uma opção: ").strip()

    if choice == "1":
        scrape()
        return

    if choice == "2":
        raw = input("Quantos capítulos deseja gerar? ").strip()
        try:
            limit = int(raw)
        except ValueError:
            print("Informe um número inteiro.")
            return

        if limit <= 0:
            print("A quantidade deve ser maior que zero.")
            return

        scrape(limit=limit)
        return

    if choice != "0":
        print("Opção inválida.")


def _epub_menu():
    config = load_config()
    json_dir = ROOT / config.get("json_output_dir", "output/json")
    json_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(
        json_dir.glob("*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )

    if not json_files:
        print(f"Nenhum JSON encontrado em {json_dir}.")
        return

    source = _choose_json(json_files)
    if source is None:
        return

    title = input("Título do livro: ").strip()
    if not title:
        print("O título é obrigatório.")
        return

    author = input("Autor (Enter para deixar vazio): ").strip()
    language = input("Idioma [zh-CN]: ").strip() or "zh-CN"

    cover = ROOT / config.get("cover_path", "input/assets/cover.jpg")
    if cover.is_file():
        print(f"Capa encontrada: {cover}")
    else:
        print(f"Sem capa: arquivo não encontrado em {cover}")
        cover = None

    confirm = input("Gerar EPUB? [s/N]: ").strip().lower()
    if confirm not in {"s", "sim", "y", "yes"}:
        print("Geração cancelada.")
        return

    generate_epub(
        json_path=source,
        title=title,
        author=author,
        language=language,
        cover=cover,
    )


def _choose_json(json_files):
    if len(json_files) == 1:
        print(f"JSON encontrado: {json_files[0].name}")
        return json_files[0]

    print("\nJSONs disponíveis:")
    for index, path in enumerate(json_files, start=1):
        print(f"{index}. {path.name}")
    print("0. Voltar")

    raw = input("Escolha o JSON: ").strip()
    try:
        selected = int(raw)
    except ValueError:
        print("Opção inválida.")
        return None

    if selected == 0:
        return None

    if not 1 <= selected <= len(json_files):
        print("Opção inválida.")
        return None

    return json_files[selected - 1]


if __name__ == "__main__":
    main()

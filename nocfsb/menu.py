from __future__ import annotations

import json
from pathlib import Path

from .src.epub_builder import build_epub
from .src.scraper import DEFAULT_CONFIG, load_config, run_scrape, validate_chapter_collection

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config_nocfsb.json"


def _print_menu() -> None:
    print()
    print("NOCFSB")
    print("─" * 60)
    print("  [🟡 EXTRAÇÃO]")
    print("  1. Coletar capítulos")
    print("  2. Validar coleta")
    print("  3. Gerar EPUB")
    print("  4. Ver configuração")
    print()
    print("  [🚪 SAIR]")
    print("  0. Sair")
    print("─" * 60)


def _print_config() -> None:
    config = load_config(CONFIG_PATH)
    print("\nConfiguração atual:")
    print(json.dumps(config, ensure_ascii=False, indent=2))


def _validate_collection_report(config) -> dict:
    validation = validate_chapter_collection(config)
    if validation["is_valid"]:
        print("\nValidação OK: sequência numérica coerente, com ordem lógica e sem capítulos faltando.")
    else:
        print("\nValidação falhou:")
        if validation["missing_numbers"]:
            print(f"  Capítulos faltando: {validation['missing_numbers']}")
        if validation["extra_numbers"]:
            print(f"  Capítulos fora do intervalo esperado: {validation['extra_numbers']}")
        if not validation["sequence_order"]:
            print(f"  Sequência fora da ordem lógica do site: {validation['order_issues']}")
        if not validation["missing_numbers"] and not validation["extra_numbers"] and not validation["sequence_order"]:
            print("  Possível gap ou quebra de coerência na progressão da obra.")
    return validation


def main() -> int:
    while True:
        _print_menu()
        choice = input("Selecione uma opção › ").strip()

        if choice == "1":
            config = load_config(CONFIG_PATH)
            summary = run_scrape(config)
            print(f"\nExtração concluída: {summary.items_found} capítulos coletados.")

        elif choice == "2":
            config = load_config(CONFIG_PATH)
            _validate_collection_report(config)

        elif choice == "3":
            config = load_config(CONFIG_PATH)
            validation = validate_chapter_collection(config)
            if not validation["is_valid"]:
                print("\nNão é possível gerar o EPUB enquanto a coleta estiver incompleta, fora da sequência esperada ou com gap de coerência.")
                if validation["missing_numbers"]:
                    print(f"  Faltantes: {validation['missing_numbers']}")
                if validation["extra_numbers"]:
                    print(f"  Extras: {validation['extra_numbers']}")
                if not validation["sequence_order"]:
                    print(f"  Ordem quebrada: {validation['order_issues']}")
                continue
            chapters = run_scrape(config).chapters
            output_path = build_epub(chapters, config)
            print(f"\nEPUB gerado em: {output_path}")

        elif choice == "4":
            _print_config()

        elif choice in {"0", "s", "S", "q", "Q"}:
            print("\nEncerrando NOCFSB...")
            return 0

        else:
            print("\nOpção inválida. Tente novamente.")


if __name__ == "__main__":
    raise SystemExit(main())

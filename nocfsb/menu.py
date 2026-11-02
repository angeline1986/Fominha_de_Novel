from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

from .src.epub_builder import build_epub
from .src.epub_validation import validate_epub
from .src.parser import build_book_urls
from .src.scraper import load_config, resolve_path, run_scrape, validate_chapter_collection
from .src.storage import atomic_write_json, load_json

ROOT = Path(__file__).resolve().parent


def _required_input(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Este campo é obrigatório.")


def _chapter_number(prompt: str, minimum: int = 0) -> int:
    while True:
        value = input(prompt).strip()
        if value.isdigit() and int(value) >= minimum:
            return int(value)
        print(f"Digite um número inteiro maior ou igual a {minimum}.")


def _volume_url() -> str:
    while True:
        value = _required_input("URL base do volume ou seção (sem /capitulo-01/) › ").rstrip("/")
        parsed = urlsplit(value)
        if parsed.scheme in {"http", "https"} and parsed.hostname in {"nocfsb.com", "www.nocfsb.com"} and parsed.path.startswith("/manga/") and not parsed.query and not parsed.fragment and not re.search(r"/(?:capitulo|spin-off)[-_]\d+$", parsed.path, re.IGNORECASE):
            return value
        print("Informe a URL do volume no nocfsb.com, sem o endereço de um capítulo.")


def _new_config() -> Path | None:
    print("\nNova obra no NOCFSB (Ctrl+C para cancelar)")
    try:
        title = _required_input("Título da obra › ")
        ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
        if not slug:
            print("Título inválido para nome de arquivo.")
            return None
        config_path = ROOT / f"config_{slug}.json"
        for existing_path in ROOT.glob("config_*.json"):
            if load_config(existing_path).get("book", {}).get("id") == slug or existing_path == config_path:
                print(f"Obra já cadastrada. Abrindo {existing_path.name}.")
                return existing_path

        author = input("Autor [Desconhecido] › ").strip() or "Desconhecido"
        volumes = []
        while True:
            print(f"\nConjunto de capítulos {len(volumes) + 1}:")
            base = _volume_url()
            mode = input("Formato: [I]ntervalo ou [L]ista exata de capítulos? [I] › ").strip().lower()
            if mode not in {"", "i", "intervalo", "l", "lista"}:
                print("Escolha I para intervalo ou L para lista exata.")
                continue
            if mode in {"l", "lista"}:
                prefix = input("Prefixo da URL [capitulo] › ").strip().strip("-") or "capitulo"
                slugs = [item.strip() for item in input("Sufixos na ordem do site (ex.: 01, 01-2, 02_1) › ").split(",") if item.strip()]
                if not slugs or any(not re.fullmatch(r"[a-zA-Z0-9_.-]+", item) for item in slugs):
                    print("Informe pelo menos um sufixo, usando apenas letras, números, ponto, hífen ou sublinhado.")
                    continue
                volume = {"base": base, "chapter_prefix": prefix, "chapters": slugs}
            else:
                start = _chapter_number("Primeiro capítulo › ")
                end = _chapter_number("Último capítulo › ", minimum=start)
                prefix = input("Prefixo da URL [capitulo] › ").strip().strip("-") or "capitulo"
                suffix = input("Sufixo comum após o número (ex.: _1) [nenhum] › ").strip()
                if suffix and not re.fullmatch(r"[_\-.][a-zA-Z0-9_-]+", suffix):
                    print("O sufixo deve começar com _, - ou . e conter apenas letras, números, hífen ou sublinhado.")
                    continue
                leading = [item.strip() for item in input("Capítulos extras antes do intervalo, separados por vírgula [nenhum] › ").split(",") if item.strip()]
                if any(not re.fullmatch(r"[a-zA-Z0-9_.-]+", item) for item in leading):
                    print("Capítulos extras devem conter apenas letras, números, ponto, hífen ou sublinhado.")
                    continue
                volume = {"base": base, "chapter_prefix": prefix, "start": start, "end": end}
                if suffix:
                    volume["chapter_suffix"] = suffix
                if leading:
                    volume["leading"] = leading
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", prefix):
                print("O prefixo deve conter apenas letras, números, hífen ou sublinhado.")
                continue
            candidate = volumes + [volume]
            urls = build_book_urls({"volumes": candidate})
            if len(urls) != len(set(urls)):
                print("Há URLs repetidas nesse conjunto. Revise o intervalo e os capítulos extras.")
                continue
            volumes.append(volume)
            if input("Adicionar outro volume ou seção? [s/N] › ").strip().lower() not in {"s", "sim"}:
                break
    except (KeyboardInterrupt, EOFError):
        print("\nCadastro cancelado; nenhum arquivo foi criado.")
        return None

    config = {
        "book": {"id": slug, "title": title, "author": author, "language": "pt-BR"},
        "site": "https://nocfsb.com",
        "output_dir": "output",
        "output_json": f"output/{slug}.json",
        "cache_file": f"output/{slug}_cache.json",
        "output_epub": f"output/{slug}.epub",
        "cover_source": f"cover_{slug}.jpg",
        "chapter_delay_min_ms": 4000,
        "chapter_delay_max_ms": 7000,
        "http": {"timeout": 30, "max_retries": 2, "retry_backoff": 2, "user_agent": "Mozilla/5.0 (compatible; FominhaDeNovel/1.0)"},
        "volumes": volumes,
    }
    atomic_write_json(config_path, config)
    print(f"\nConfiguração criada: {config_path}")
    urls = build_book_urls(config)
    print(f"URLs previstas: {len(urls)}")
    print(f"  Primeira: {urls[0]}")
    print(f"  Última: {urls[-1]}")
    print("Escolha 1 para iniciar a coleta.")
    return config_path


def _choose_config() -> Path | None:
    configs = sorted(ROOT.glob("config_*.json"))
    if not configs:
        return _new_config()
    if len(configs) == 1:
        return configs[0]

    print("\nEscolha a obra:")
    for index, path in enumerate(configs, start=1):
        title = load_config(path).get("book", {}).get("title", path.stem)
        print(f"  {index}. {title} ({path.name})")
    print("  N. Nova obra")
    print("  0. Sair")
    while True:
        try:
            choice = input("Obra › ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando NOCFSB...")
            return None
        if choice == "0":
            return None
        if choice.lower() == "n":
            return _new_config()
        if choice.isdigit() and 1 <= int(choice) <= len(configs):
            return configs[int(choice) - 1]
        print("Opção inválida. Escolha o número da obra.")


def _print_menu(config_path: str | Path) -> None:
    print()
    print("NOCFSB")
    print("─" * 60)
    print(f"  config: {config_path}")
    print("  [🟡 EXTRAÇÃO]")
    print("  1. Coletar capítulos")
    print("  2. Validar coleta")
    print("  3. Gerar EPUB")
    print("  4. Ver configuração")
    print("  5. Nova obra")
    print()
    print("  [🚪 SAIR]")
    print("  0. Sair")
    print("─" * 60)


def _print_config(config_path: str | Path) -> None:
    config = load_config(config_path)
    print("\nConfiguração atual:")
    print(json.dumps(config, ensure_ascii=False, indent=2))


def _validate_collection_report(config, chapters=None) -> dict:
    validation = validate_chapter_collection(config, chapters)
    print(f"\nURLs e ordem: {validation['collected_total']}/{validation['expected_total']} capítulos")
    print(f"Conteúdo examinado: {validation['content_checked_total']} capítulos; texto entre {validation['text_length_min']} e {validation['text_length_max']} caracteres")
    print(f"Grupos com texto repetido: {len(validation['duplicate_content_groups'])}")
    if validation["is_valid"]:
        print("Validação local OK: URLs, ordem, títulos, parágrafos e textos distintos.")
    else:
        print("Validação falhou:")
        for label, field in (
            ("Capítulos faltando", "missing_urls"),
            ("Capítulos inesperados", "extra_urls"),
            ("Capítulos duplicados", "duplicate_urls"),
            ("Fora de ordem", "order_issue_urls"),
            ("Títulos inválidos", "invalid_title_urls"),
            ("Parágrafos inválidos", "invalid_paragraph_urls"),
            ("Capítulos sem texto", "empty_content_urls"),
        ):
            if validation[field]:
                print(f"  {label}:")
                for url in validation[field]:
                    print(f"    {url}")
        for group in validation["duplicate_content_groups"]:
            print("  Mesmo texto em URLs diferentes:")
            for url in group:
                print(f"    {url}")
    return validation


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Coleta e monta EPUBs da obra NOCFSB.")
    parser.add_argument(
        "--config",
        type=Path,
        help="Caminho do arquivo JSON de configuração da obra.",
    )
    args = parser.parse_args(argv)
    config_path = args.config if args.config is not None else _choose_config()
    if config_path is None:
        return 0

    while True:
        _print_menu(config_path)
        try:
            choice = input("Selecione uma opção › ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando NOCFSB...")
            return 0

        if choice == "1":
            config = load_config(config_path)
            try:
                summary = run_scrape(config)
            except KeyboardInterrupt:
                print("\nColeta interrompida. Capítulos processados foram salvos; escolha 1 para retomar.")
                continue
            if summary.items_found == summary.urls_total:
                print(f"\nExtração concluída: {summary.items_found} capítulos coletados.")
            else:
                print(f"\nColeta parcial: {summary.items_found}/{summary.urls_total} capítulos. Escolha 1 para tentar os pendentes novamente.")

        elif choice == "2":
            config = load_config(config_path)
            _validate_collection_report(config)

        elif choice == "3":
            config = load_config(config_path)
            output_json = resolve_path(ROOT, config.get("output_json", "salt-society.json"), "salt-society.json")
            chapters = load_json(output_json, [])
            if not isinstance(chapters, list):
                chapters = []
            validation = _validate_collection_report(config, chapters)
            if not validation["is_valid"]:
                print("\nEPUB não gerado: corrija os problemas da coleta.")
                continue
            output_path = ROOT / config.get("output_epub", "output/salt-society.epub")
            candidate_path = output_path.with_name(f"{output_path.stem}.candidate.epub")
            candidate_config = {**config, "output_epub": str(candidate_path)}
            build_epub(chapters, candidate_config)
            epub_report = validate_epub(candidate_path, len(chapters))
            if not epub_report["is_valid"]:
                print("\nEPUB não publicado: o arquivo gerado falhou na verificação:")
                for issue in epub_report["issues"]:
                    print(f"  {issue}")
                continue
            candidate_path.replace(output_path)
            print(f"EPUB verificado: ZIP íntegro, {epub_report['chapters_checked']} capítulos, manifesto e índices completos.")
            print(f"\nEPUB gerado em: {output_path}")

        elif choice == "4":
            _print_config(config_path)

        elif choice == "5":
            new_path = _new_config()
            if new_path is not None:
                config_path = new_path

        elif choice in {"0", "s", "S", "q", "Q"}:
            print("\nEncerrando NOCFSB...")
            return 0

        else:
            print("\nOpção inválida. Tente novamente.")


if __name__ == "__main__":
    raise SystemExit(main())

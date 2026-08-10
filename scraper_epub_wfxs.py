import argparse
import json
import random
import re
import time
import uuid
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from ebooklib import epub


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36"
    )
}


def build_headers(extra_headers: dict | None = None) -> dict:
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    return headers


def build_request_headers(args: argparse.Namespace) -> dict:
    headers = build_headers(args.headers)
    if isinstance(args.cookies, str):
        headers["Cookie"] = args.cookies
    return headers


def configure_session(session: requests.Session, args: argparse.Namespace) -> None:
    session.headers.update(build_request_headers(args))

    if args.cookies:
        if isinstance(args.cookies, dict):
            session.cookies.update(args.cookies)
        elif isinstance(args.cookies, str):
            pass
        else:
            raise ValueError("O campo cookies precisa ser um objeto JSON ou uma string.")


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def html_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def create_url_range(first_url: str, last_url: str) -> list[str]:
    first_numbers = list(re.finditer(r"\d+", first_url))
    last_numbers = list(re.finditer(r"\d+", last_url))

    if len(first_numbers) != len(last_numbers):
        raise ValueError("A primeira e a última URL possuem estruturas numéricas diferentes.")

    changed_positions = [
        index
        for index, (first_match, last_match) in enumerate(zip(first_numbers, last_numbers))
        if first_match.group() != last_match.group()
    ]

    if not changed_positions:
        if first_url == last_url:
            return [first_url]
        raise ValueError("Não foi possível identificar qual número muda entre as URLs.")

    if len(changed_positions) > 1:
        raise ValueError(
            "Mais de uma parte numérica muda entre as URLs. "
            "Não é possível determinar automaticamente qual representa o capítulo."
        )

    changed_index = changed_positions[0]
    first_match = first_numbers[changed_index]
    last_match = last_numbers[changed_index]
    start_number = int(first_match.group())
    end_number = int(last_match.group())

    if end_number < start_number:
        raise ValueError("O número identificado na última URL é menor que o da primeira URL.")

    expected_first_url = (
        last_url[: last_match.start()]
        + first_match.group()
        + last_url[last_match.end() :]
    )
    if expected_first_url != first_url:
        raise ValueError("As URLs possuem outras diferenças além do número do capítulo.")

    prefix = first_url[: first_match.start()]
    suffix = first_url[first_match.end() :]
    number_width = len(first_match.group())

    return [
        f"{prefix}{str(number).zfill(number_width)}{suffix}"
        for number in range(start_number, end_number + 1)
    ]


def remove_unwanted_elements(content_element) -> None:
    unwanted_selectors = [
        "script",
        "style",
        "noscript",
        "iframe",
        "form",
        "button",
        "nav",
        "footer",
        ".advertisement",
        ".ads",
        ".ad",
        ".share",
        ".social",
    ]

    for selector in unwanted_selectors:
        for element in content_element.select(selector):
            element.decompose()


def extract_text_from_element(element) -> str:
    return clean_text(
        element.get("content")
        or element.get("title")
        or element.get("alt")
        or element.get_text(" ", strip=True)
    )


def extract_paragraphs(content_element) -> list[str]:
    text_elements = content_element.select("p, div, section, blockquote")
    paragraphs = []

    for element in text_elements:
        if element.find(["p", "div", "section", "blockquote"], recursive=False):
            continue

        text = clean_text(element.get_text(" ", strip=True))
        if text and text not in paragraphs:
            paragraphs.append(text)

    if paragraphs:
        return paragraphs

    raw_text = content_element.get_text("\n", strip=True)
    for line in raw_text.splitlines():
        text = clean_text(line)
        if text and text not in paragraphs:
            paragraphs.append(text)

    return paragraphs


def fetch_soup(
    session: requests.Session,
    url: str,
    encoding: str | None = None,
    timeout_seconds: float = 30.0,
) -> BeautifulSoup:
    response = session.get(url, timeout=timeout_seconds)
    response.raise_for_status()

    if encoding:
        response.encoding = encoding
    else:
        response.encoding = response.apparent_encoding

    return BeautifulSoup(response.text, "lxml")


def extract_title(soup: BeautifulSoup, selector: str, label: str) -> str:
    title_element = soup.select_one(selector)
    if title_element is None:
        raise ValueError(f"Seletor de {label} não encontrado: {selector}")

    title = extract_text_from_element(title_element)
    if not title:
        raise ValueError(f"O {label} encontrado está vazio.")

    return title


def fetch_page(
    session: requests.Session,
    url: str,
    chapter_title_selector: str,
    content_selector: str,
    encoding: str | None = None,
    timeout_seconds: float = 30.0,
) -> tuple[str, list[str]]:
    soup = fetch_soup(session, url, encoding, timeout_seconds)
    return parse_page_soup(soup, chapter_title_selector, content_selector)


def parse_page_soup(
    soup: BeautifulSoup,
    chapter_title_selector: str,
    content_selector: str,
) -> tuple[str, list[str]]:
    title = extract_title(soup, chapter_title_selector, "título do capítulo")

    content_element = soup.select_one(content_selector)
    if content_element is None:
        raise ValueError(f"Seletor de conteúdo não encontrado: {content_selector}")

    remove_unwanted_elements(content_element)
    paragraphs = extract_paragraphs(content_element)
    if not paragraphs:
        raise ValueError("O conteúdo encontrado está vazio.")

    return title, paragraphs


def fetch_page_with_playwright(
    page,
    url: str,
    chapter_title_selector: str,
    content_selector: str,
    timeout_seconds: float,
    referer: str | None = None,
) -> tuple[str, list[str]]:
    timeout_ms = int(timeout_seconds * 1000)
    goto_options = {"wait_until": "domcontentloaded", "timeout": timeout_ms}
    if referer:
        goto_options["referer"] = referer

    response = page.goto(url, **goto_options)
    if response is not None and response.status >= 400:
        raise RuntimeError(f"{response.status} ao abrir a página com Playwright: {url}")

    page.wait_for_selector(content_selector, timeout=timeout_ms)
    soup = BeautifulSoup(page.content(), "lxml")
    return parse_page_soup(soup, chapter_title_selector, content_selector)


def click_next_with_playwright(
    page,
    chapter_title_selector: str,
    content_selector: str,
    next_selector: str,
    timeout_seconds: float,
) -> tuple[str, list[str]]:
    timeout_ms = int(timeout_seconds * 1000)
    page.locator(next_selector).first.click(timeout=timeout_ms)
    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    page.wait_for_selector(content_selector, timeout=timeout_ms)
    soup = BeautifulSoup(page.content(), "lxml")
    return parse_page_soup(soup, chapter_title_selector, content_selector)


def advance_next_with_playwright(
    page,
    content_selector: str,
    next_selector: str,
    timeout_seconds: float,
) -> None:
    timeout_ms = int(timeout_seconds * 1000)
    page.locator(next_selector).first.click(timeout=timeout_ms)
    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    page.wait_for_selector(content_selector, timeout=timeout_ms)


def load_chapter_cache(cache_path: str | None) -> dict[int, dict]:
    if not cache_path:
        return {}

    path = Path(cache_path)
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    chapters = data.get("chapters", [])
    if not isinstance(chapters, list):
        raise ValueError(f"Cache inválido: {path}")

    cache = {}
    for chapter in chapters:
        number = chapter.get("number")
        title = chapter.get("title")
        paragraphs = chapter.get("paragraphs")
        if isinstance(number, int) and title and isinstance(paragraphs, list):
            cache[number] = chapter

    return cache


def save_chapter_cache(cache_path: str | None, chapters: list[dict]) -> None:
    if not cache_path:
        return

    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"chapters": sorted(chapters, key=lambda chapter: chapter["number"])}
    temp_path = path.with_suffix(path.suffix + ".tmp")

    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    temp_path.replace(path)


def get_contiguous_cached_chapters(
    cached_chapters: dict[int, dict],
    total_chapters: int,
) -> list[dict]:
    chapters = []
    for chapter_number in range(1, total_chapters + 1):
        chapter = cached_chapters.get(chapter_number)
        if not chapter:
            break
        chapters.append(chapter)
    return chapters


def build_epub(
    chapters: list[dict],
    output_path: str,
    book_title: str,
    book_author: str,
    language: str,
    cover_path: str | None = None,
) -> None:
    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(book_title)
    book.set_language(language)
    book.add_author(book_author)

    if cover_path:
        add_cover(book, Path(cover_path))

    style = """
    body {
        font-family: serif;
        line-height: 1.5;
        margin: 5%;
    }
    h1 {
        text-align: center;
        margin-bottom: 1.5em;
    }
    p {
        text-indent: 1.5em;
        margin: 0.6em 0;
    }
    """

    css_item = epub.EpubItem(
        uid="style_css",
        file_name="style/style.css",
        media_type="text/css",
        content=style.encode("utf-8"),
    )
    book.add_item(css_item)

    epub_chapters = []
    for chapter_data in chapters:
        number = chapter_data["number"]
        raw_title = chapter_data["title"]
        escaped_title = html_escape(raw_title)

        chapter = epub.EpubHtml(
            title=raw_title,
            file_name=f"chapter_{number:04}.xhtml",
            lang=language,
        )
        chapter.add_item(css_item)

        body_parts = [f"<h1>{escaped_title}</h1>"]
        for paragraph in chapter_data["paragraphs"]:
            body_parts.append(f"<p>{html_escape(paragraph)}</p>")

        chapter.set_content(
            (
                '<html xmlns="http://www.w3.org/1999/xhtml" '
                f'xml:lang="{language}" lang="{language}">'
                "<head>"
                f"<title>{escaped_title}</title>"
                '<link rel="stylesheet" type="text/css" href="style/style.css"/>'
                "</head>"
                "<body>"
                + "".join(body_parts)
                + "</body></html>"
            ).encode("utf-8")
        )

        book.add_item(chapter)
        epub_chapters.append(chapter)

    if not epub_chapters:
        raise RuntimeError("Nenhum capítulo válido foi adicionado ao EPUB.")

    book.toc = tuple(epub_chapters)
    book.spine = ["nav"] + epub_chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(output_path, book, {})


def add_cover(book: epub.EpubBook, cover_path: Path) -> None:
    if not cover_path.exists():
        raise FileNotFoundError(f"Capa não encontrada: {cover_path.resolve()}")

    extension = cover_path.suffix.lower()
    if extension in {".jpg", ".jpeg"}:
        cover_name = "cover.jpg"
    elif extension == ".png":
        cover_name = "cover.png"
    else:
        raise ValueError("A capa precisa ser .jpg, .jpeg ou .png.")

    with cover_path.open("rb") as file:
        book.set_cover(cover_name, file.read())


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrai capítulos de páginas web e gera um EPUB."
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Arquivo JSON com os parâmetros da extração.",
    )
    parser.add_argument("--primeira-url", default=None, help="URL da primeira página.")
    parser.add_argument("--ultima-url", default=None, help="URL da última página.")
    parser.add_argument(
        "--seletor-titulo-capitulo",
        default=None,
        help="Seletor CSS do título de cada capítulo.",
    )
    parser.add_argument(
        "--seletor-conteudo",
        default=None,
        help="Seletor CSS do conteúdo principal de cada capítulo.",
    )
    parser.add_argument(
        "--seletor-titulo",
        default=None,
        help="Seletor CSS do título do livro na primeira página.",
    )
    parser.add_argument(
        "--titulo-livro",
        default=None,
        help="Título manual do livro. Tem prioridade sobre --seletor-titulo.",
    )
    parser.add_argument("--autor", default=None, help="Autor usado no EPUB.")
    parser.add_argument("--idioma", default=None, help="Idioma do EPUB.")
    parser.add_argument("--saida", default=None, help="Arquivo EPUB de saída.")
    parser.add_argument("--capa", default=None, help="Caminho da imagem de capa do EPUB.")
    parser.add_argument(
        "--intervalo",
        type=float,
        default=None,
        help="Segundos de espera entre as requisições.",
    )
    parser.add_argument(
        "--encoding",
        default=None,
        help="Encoding manual, como utf-8 ou gb18030.",
    )
    parser.add_argument(
        "--motor",
        choices=["requests", "playwright"],
        default=None,
        help="Motor de extração. Use playwright quando o site bloquear requests.",
    )
    parser.add_argument(
        "--navegacao",
        choices=["direta", "proximo"],
        default=None,
        help="No Playwright, use direta para abrir cada URL ou proximo para clicar no link de próximo capítulo.",
    )
    parser.add_argument(
        "--seletor-proximo",
        default=None,
        help="Seletor do link/botão de próximo capítulo usado com navegacao=proximo.",
    )
    parser.add_argument(
        "--parar-em-erro",
        action="store_true",
        default=None,
        help="Interrompe a extração no primeiro capítulo com erro.",
    )
    parser.add_argument(
        "--max-erros-consecutivos",
        type=int,
        default=None,
        help="Interrompe após esta quantidade de erros consecutivos. Use 0 para desativar.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout em segundos para cada requisição ou navegação.",
    )
    parser.add_argument(
        "--intervalo-max",
        type=float,
        default=None,
        help="Intervalo máximo entre páginas. Se informado, usa espera aleatória entre intervalo e intervalo_max.",
    )
    parser.add_argument(
        "--min-capitulos",
        type=int,
        default=None,
        help="Quantidade mínima de capítulos exigida para gerar o EPUB. Use 0 para desativar.",
    )
    parser.add_argument(
        "--cache",
        default=None,
        help="Arquivo JSON usado para salvar progresso e retomar a extração.",
    )
    parser.add_argument(
        "--pausa-a-cada",
        type=int,
        default=None,
        help="Faz uma pausa longa após esta quantidade de capítulos baixados. Use 0 para desativar.",
    )
    parser.add_argument(
        "--pausa-lote",
        type=float,
        default=None,
        help="Pausa longa mínima, em segundos, usada com pausa_a_cada.",
    )
    parser.add_argument(
        "--pausa-lote-max",
        type=float,
        default=None,
        help="Pausa longa máxima, em segundos. Se informada, usa pausa aleatória.",
    )
    parser.add_argument(
        "--pausa-erro",
        type=float,
        default=None,
        help="Pausa, em segundos, multiplicada pela quantidade de erros consecutivos.",
    )
    parser.add_argument(
        "--sincronizar-do-inicio",
        action="store_true",
        default=None,
        help="Se a sincronização direta no último capítulo salvo falhar, avança desde o capítulo 1 por cliques.",
    )
    parser.add_argument(
        "--intervalo-sincronizacao",
        type=float,
        default=None,
        help="Espera mínima entre cliques usados apenas para sincronizar capítulos em cache.",
    )
    parser.add_argument(
        "--intervalo-sincronizacao-max",
        type=float,
        default=None,
        help="Espera máxima entre cliques usados apenas para sincronizar capítulos em cache.",
    )
    parser.add_argument(
        "--somente-cache",
        action="store_true",
        default=None,
        help="Gera o EPUB usando apenas capítulos salvos no cache, sem acessar o site.",
    )
    args = parser.parse_args()
    return merge_config_with_args(args)


def load_config(config_path: str | None) -> dict:
    if not config_path:
        return {}

    path = Path(config_path)
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config, dict):
        raise ValueError("O arquivo de configuração precisa conter um objeto JSON.")

    return config


def merge_config_with_args(args: argparse.Namespace) -> argparse.Namespace:
    config = load_config(args.config)
    defaults = {
        "autor": "Desconhecido",
        "idioma": "pt-BR",
        "saida": "livro_extraido.epub",
        "intervalo": 1.0,
        "encoding": None,
        "capa": None,
        "cookies": None,
        "headers": None,
        "motor": "requests",
        "navegacao": "direta",
        "seletor_proximo": "a:has-text('Next Chapter')",
        "parar_em_erro": False,
        "max_erros_consecutivos": 3,
        "timeout": 30.0,
        "intervalo_max": None,
        "min_capitulos": 1,
        "cache": None,
        "pausa_a_cada": 0,
        "pausa_lote": 0.0,
        "pausa_lote_max": None,
        "pausa_erro": 0.0,
        "sincronizar_do_inicio": True,
        "intervalo_sincronizacao": 1.0,
        "intervalo_sincronizacao_max": 3.0,
        "somente_cache": False,
        "seletor_titulo": None,
        "titulo_livro": None,
    }

    values = {**defaults, **config}
    for key, value in vars(args).items():
        if key == "config":
            values[key] = value
        elif value is not None:
            values[key] = value

    required_fields = [
        "primeira_url",
        "ultima_url",
        "seletor_titulo_capitulo",
        "seletor_conteudo",
    ]
    missing_fields = [field for field in required_fields if not values.get(field)]
    if missing_fields:
        formatted = ", ".join(missing_fields)
        raise ValueError(
            f"Parâmetros obrigatórios ausentes: {formatted}. "
            "Informe pelo JSON ou por argumentos de linha de comando."
        )

    return argparse.Namespace(**values)


def resolve_book_title(args: argparse.Namespace, session: requests.Session) -> str:
    if args.titulo_livro:
        return args.titulo_livro

    if args.seletor_titulo:
        soup = fetch_soup(session, args.primeira_url, args.encoding, args.timeout)
        return extract_title(soup, args.seletor_titulo, "título do livro")

    return "Livro extraído"


def wait_between_pages(args: argparse.Namespace) -> None:
    if args.intervalo_max is None:
        delay = args.intervalo
    else:
        delay = random.uniform(args.intervalo, args.intervalo_max)

    if delay > 0:
        time.sleep(delay)


def wait_after_batch(args: argparse.Namespace, downloaded_count: int) -> None:
    if not args.pausa_a_cada or downloaded_count <= 0:
        return

    if downloaded_count % args.pausa_a_cada != 0:
        return

    delay = args.pausa_lote
    if args.pausa_lote_max is not None:
        delay = random.uniform(args.pausa_lote, args.pausa_lote_max)

    if delay > 0:
        print(f"Pausa de lote: aguardando {delay:.1f}s...")
        time.sleep(delay)


def wait_after_error(args: argparse.Namespace, consecutive_errors: int) -> None:
    delay = args.pausa_erro * consecutive_errors
    if delay > 0:
        print(f"Pausa após erro: aguardando {delay:.1f}s...")
        time.sleep(delay)


def wait_during_sync(args: argparse.Namespace) -> None:
    if args.intervalo_sincronizacao_max is None:
        delay = args.intervalo_sincronizacao
    else:
        delay = random.uniform(args.intervalo_sincronizacao, args.intervalo_sincronizacao_max)

    if delay > 0:
        time.sleep(delay)


def resolve_book_title_from_page(args: argparse.Namespace, page) -> str:
    if args.titulo_livro:
        return args.titulo_livro

    if args.seletor_titulo:
        response = page.goto(
            args.primeira_url,
            wait_until="domcontentloaded",
            timeout=int(args.timeout * 1000),
        )
        if response is not None and response.status >= 400:
            raise RuntimeError(
                f"{response.status} ao abrir a primeira página com Playwright: "
                f"{args.primeira_url}"
            )
        soup = BeautifulSoup(page.content(), "lxml")
        return extract_title(soup, args.seletor_titulo, "título do livro")

    return "Livro extraído"


def extract_with_requests(
    args: argparse.Namespace,
    urls: list[str],
    cached_chapters: dict[int, dict],
) -> tuple[str, list[dict]]:
    session = requests.Session()
    configure_session(session, args)
    book_title = resolve_book_title(args, session)
    chapters = []
    consecutive_errors = 0
    downloaded_count = 0

    for chapter_number, url in enumerate(urls, start=1):
        if chapter_number in cached_chapters:
            chapter_data = cached_chapters[chapter_number]
            chapters.append(chapter_data)
            print(f"\n[{chapter_number}/{len(urls)}] Cache: {chapter_data['title']}")
            continue

        print(f"\n[{chapter_number}/{len(urls)}] Baixando: {url}")

        try:
            title, paragraphs = fetch_page(
                session=session,
                url=url,
                chapter_title_selector=args.seletor_titulo_capitulo,
                content_selector=args.seletor_conteudo,
                encoding=args.encoding,
                timeout_seconds=args.timeout,
            )
        except Exception as exc:
            consecutive_errors += 1
            print(f"ERRO: {exc}")
            wait_after_error(args, consecutive_errors)

            if args.parar_em_erro:
                print("Extração interrompida porque parar_em_erro está ativado.")
                break

            if args.max_erros_consecutivos and consecutive_errors >= args.max_erros_consecutivos:
                print(
                    "Extração interrompida após "
                    f"{consecutive_errors} erro(s) consecutivo(s)."
                )
                break
        else:
            consecutive_errors = 0
            chapters.append(
                {
                    "number": chapter_number,
                    "url": url,
                    "title": title,
                    "paragraphs": paragraphs,
                }
            )
            print(f"OK: {title}")
            print(f"Parágrafos capturados: {len(paragraphs)}")
            save_chapter_cache(args.cache, chapters)
            downloaded_count += 1
            wait_after_batch(args, downloaded_count)

        if chapter_number < len(urls):
            wait_between_pages(args)

    return book_title, chapters


def advance_cached_chapter_with_playwright(
    page,
    args: argparse.Namespace,
    chapter_number: int,
    url: str,
    previous_url: str,
) -> None:
    if args.navegacao == "proximo" and chapter_number > 1:
        click_next_with_playwright(
            page=page,
            chapter_title_selector=args.seletor_titulo_capitulo,
            content_selector=args.seletor_conteudo,
            next_selector=args.seletor_proximo,
            timeout_seconds=args.timeout,
        )
    else:
        fetch_page_with_playwright(
            page=page,
            url=url,
            chapter_title_selector=args.seletor_titulo_capitulo,
            content_selector=args.seletor_conteudo,
            timeout_seconds=args.timeout,
            referer=previous_url,
        )


def sync_playwright_to_cached_position(
    page,
    args: argparse.Namespace,
    urls: list[str],
    start_index: int,
) -> str:
    if start_index <= 0:
        return args.primeira_url

    target_url = urls[start_index - 1]
    referer = urls[start_index - 2] if start_index > 1 else args.primeira_url
    print(f"Sincronizando navegador no último capítulo em cache: {target_url}")

    try:
        fetch_page_with_playwright(
            page=page,
            url=target_url,
            chapter_title_selector=args.seletor_titulo_capitulo,
            content_selector=args.seletor_conteudo,
            timeout_seconds=args.timeout,
            referer=referer,
        )
        return target_url
    except Exception as exc:
        if not args.sincronizar_do_inicio:
            raise

        print(f"Sincronização direta falhou: {exc}")
        print("Tentando sincronizar pelo fluxo de cliques desde o capítulo 1.")

    try:
        fetch_page_with_playwright(
            page=page,
            url=args.primeira_url,
            chapter_title_selector=args.seletor_titulo_capitulo,
            content_selector=args.seletor_conteudo,
            timeout_seconds=args.timeout,
        )
    except Exception as exc:
        raise RuntimeError(
            "Não consegui abrir nem o capítulo 1 durante a sincronização. "
            "Isso normalmente significa que o cookie/sessão não está válido para "
            "o Playwright ou já expirou. Atualize o campo cookies no JSON e tente novamente."
        ) from exc

    current_url = args.primeira_url
    for chapter_number in range(2, start_index + 1):
        advance_next_with_playwright(
            page=page,
            content_selector=args.seletor_conteudo,
            next_selector=args.seletor_proximo,
            timeout_seconds=args.timeout,
        )
        current_url = urls[chapter_number - 1]

        if chapter_number % 10 == 0 or chapter_number == start_index:
            print(f"  Sincronizado até o capítulo {chapter_number}/{start_index}.")

        if chapter_number < start_index:
            wait_during_sync(args)

    return current_url


def extract_with_playwright(
    args: argparse.Namespace,
    urls: list[str],
    cached_chapters: dict[int, dict],
) -> tuple[str, list[dict]]:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright não está instalado. Instale com: "
            "pip install playwright && python -m playwright install chromium"
        ) from exc

    chapters = []
    consecutive_errors = 0
    downloaded_count = 0
    cached_prefix = get_contiguous_cached_chapters(cached_chapters, len(urls))
    chapters.extend(cached_prefix)
    start_index = len(cached_prefix)

    if cached_prefix:
        print(f"Retomando após capítulo {start_index}.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            extra_http_headers=build_request_headers(args),
            user_agent=build_request_headers(args)["User-Agent"],
        )
        page = context.new_page()

        try:
            book_title = resolve_book_title_from_page(args, page)
            previous_url = args.primeira_url

            if start_index > 0:
                previous_url = sync_playwright_to_cached_position(page, args, urls, start_index)

            for chapter_number, url in enumerate(urls[start_index:], start=start_index + 1):

                print(f"\n[{chapter_number}/{len(urls)}] Baixando com Playwright: {url}")

                try:
                    if args.navegacao == "proximo" and chapter_number > 1:
                        title, paragraphs = click_next_with_playwright(
                            page=page,
                            chapter_title_selector=args.seletor_titulo_capitulo,
                            content_selector=args.seletor_conteudo,
                            next_selector=args.seletor_proximo,
                            timeout_seconds=args.timeout,
                        )
                    else:
                        title, paragraphs = fetch_page_with_playwright(
                            page=page,
                            url=url,
                            chapter_title_selector=args.seletor_titulo_capitulo,
                            content_selector=args.seletor_conteudo,
                            timeout_seconds=args.timeout,
                            referer=previous_url,
                        )
                except Exception as exc:
                    consecutive_errors += 1
                    print(f"ERRO: {exc}")
                    wait_after_error(args, consecutive_errors)

                    if args.parar_em_erro:
                        print("Extração interrompida porque parar_em_erro está ativado.")
                        break

                    if args.max_erros_consecutivos and consecutive_errors >= args.max_erros_consecutivos:
                        print(
                            "Extração interrompida após "
                            f"{consecutive_errors} erro(s) consecutivo(s)."
                        )
                        break
                else:
                    consecutive_errors = 0
                    chapters.append(
                        {
                            "number": chapter_number,
                            "url": url,
                            "title": title,
                            "paragraphs": paragraphs,
                        }
                    )
                    print(f"OK: {title}")
                    print(f"Parágrafos capturados: {len(paragraphs)}")
                    save_chapter_cache(args.cache, chapters)
                    downloaded_count += 1
                    wait_after_batch(args, downloaded_count)
                    previous_url = url

                if chapter_number < len(urls):
                    wait_between_pages(args)
        finally:
            browser.close()

    return book_title, chapters


def main() -> None:
    args = parse_arguments()
    urls = create_url_range(args.primeira_url, args.ultima_url)
    print(f"{len(urls)} página(s) identificada(s).")
    cached_chapters = load_chapter_cache(args.cache)
    if cached_chapters:
        print(f"{len(cached_chapters)} capítulo(s) carregado(s) do cache.")

    if args.somente_cache:
        book_title = args.titulo_livro or "Livro extraído"
        chapters = get_contiguous_cached_chapters(cached_chapters, len(urls))
        print(f"Gerando EPUB somente com cache: {len(chapters)} capítulo(s).")
    elif args.motor == "playwright":
        book_title, chapters = extract_with_playwright(args, urls, cached_chapters)
    else:
        book_title, chapters = extract_with_requests(args, urls, cached_chapters)

    if not chapters:
        raise RuntimeError("Nenhuma página foi extraída. O EPUB não foi gerado.")

    if args.min_capitulos and len(chapters) < args.min_capitulos:
        raise RuntimeError(
            f"Apenas {len(chapters)} capítulo(s) foram extraídos. "
            f"O mínimo configurado é {args.min_capitulos}. EPUB não foi gerado."
        )

    build_epub(
        chapters=chapters,
        output_path=args.saida,
        book_title=book_title,
        book_author=args.autor,
        language=args.idioma,
        cover_path=args.capa,
    )
    print(f"\nEPUB gerado com sucesso: {Path(args.saida).resolve()}")


if __name__ == "__main__":
    main()

# zhenhunxiaoshuo

Módulo independente para extrair capítulos de `zhenhunxiaoshuo.com`.
Não depende de `novellive` nem de `oceanofpdf`.

## Dados extraídos

- Título: `h1.article-title`
- Título + frase de efeito: `article.article-content > p:first-child`
- História: `article.article-content > p:not(:first-child)`

O CSV de entrada deve possuir as colunas `Título` e `Link`.

## Instalação

A partir da raiz de `Fominha_de_Novel`:

    python -m pip install -r zhenhunxiaoshuo/requirements.txt

## Teste pequeno

    python -m zhenhunxiaoshuo.scraper --limit 3

## Execução completa

    python -m zhenhunxiaoshuo.scraper

## Testes

    python -m unittest discover -s zhenhunxiaoshuo/tests

## Saída inicial

O M1 gera:

    zhenhunxiaoshuo/output/di_wang_gong_lue.json

Cada capítulo preserva separadamente `csv_title`, `chapter_title`,
`chapter_lead` e `paragraphs`, permitindo detectar divergências entre
o índice CSV e o título real da página.

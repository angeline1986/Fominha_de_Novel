# Patch: menu numerado para gerar EPUB

Este pacote altera somente o módulo `zhenhunxiaoshuo`.

## Alterações

- remove a pergunta livre `Título do livro:`;
- adiciona `book.id`, `book.title`, `book.author` e `book.language` à configuração;
- lista os JSONs disponíveis em `output/json/` por número;
- mostra os metadados do livro antes de gerar;
- confirmação também é numerada;
- `scraper.py` passa a usar `book.id` no nome do JSON;
- JSON: `output/json/<book.id>.json`;
- EPUB: `output/epub/<book.id>.epub`.

## Instalação do patch

Copie a pasta `zhenhunxiaoshuo/` deste ZIP sobre a pasta
`zhenhunxiaoshuo/` do repositório.

Arquivos incluídos:

- `config_zhenhunxiaoshuo.json`
- `scraper.py`
- `menu.py`
- `epub_builder.py`

## Execução

Na raiz de `Fominha_de_Novel`:

```bash
python -m zhenhunxiaoshuo.menu
```

O fluxo do EPUB passa a ser:

```text
=== Gerar EPUB ===

JSONs disponíveis:
1. di_wang_gong_lue.json
0. Voltar

Escolha uma opção: 1

Livro selecionado:
JSON: di_wang_gong_lue.json
Título: 帝王攻略
Autor: 语笑阑珊
Idioma: zh-CN
Capítulos: 3

1. Gerar EPUB
0. Voltar
```

Não existe mais entrada de texto livre para o título.

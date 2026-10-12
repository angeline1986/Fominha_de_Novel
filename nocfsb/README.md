# NOCFSB

Módulo independente do projeto **Fominha_de_Novel** para extrair capítulos e
montar um EPUB a partir do site NOCFSB.

## Arquitetura

Este módulo segue o mesmo padrão dos demais módulos do projeto:

- configuração em `config_nocfsb.json`;
- coleta em `src/scraper.py`;
- parsing em `src/parser.py`;
- cliente HTTP em `src/http_client.py`;
- modelos em `src/models.py`;
- persistência em `src/storage.py`;
- geração EPUB em `src/epub_builder.py`;
- menu em `menu.py`.

## Execução

A partir da raiz do repositório:

```bash
python -m nocfsb.menu
```

## Estrutura relevante

```text
nocfsb/
├── __init__.py
├── README.md
├── config_nocfsb.json
├── menu.py
├── output/
├── src/
│   ├── __init__.py
│   ├── epub_builder.py
│   ├── http_client.py
│   ├── models.py
│   ├── parser.py
│   ├── scraper.py
│   └── storage.py
└── tests/
    └── test_nocfsb_urls.py
```

## Mapeamento e URLs

O módulo usa as URLs de capítulo do tipo:

```text
https://nocfsb.com/manga/salt-society/volume-01/capitulo-00_1/
https://nocfsb.com/manga/salt-society/volume-01/capitulo-0/
https://nocfsb.com/manga/salt-society/volume-01/capitulo-1/
```

A lista completa é gerada a partir dos volumes definidos em
`config_nocfsb.json`, com `leading` e intervalos de capítulos.

## Capas e metadados da obra

Os metadados da obra ficam em `config_nocfsb.json`, e o autor pode ser ajustado em:

```json
"book": {
  "title": "Salt Society",
  "author": "ARGON18",
  "language": "pt-BR"
}
```

A capa do EPUB deve ficar na raiz do módulo, no mesmo diretório do arquivo de configuração:

```text
nocfsb/cover.jpg
```

Se você quiser trocar a capa, substitua esse arquivo por outra imagem JPG. O módulo usa o valor `cover_source` em `config_nocfsb.json` e resolve o caminho a partir da pasta do módulo.

## Validação

Antes de gerar o EPUB, o módulo descarta capítulos vazios, duplicados e títulos genéricos sem conteúdo útil, reduzindo o risco de páginas como `Capítulo sem conteúdo`.

## Saída

Ao rodar a extração e a geração EPUB, o módulo salva arquivos em:

```text
nocfsb/output/
```

Incluindo o JSON bruto dos capítulos e o arquivo EPUB final.

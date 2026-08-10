# oceanofpdf

Módulo independente para extrair metadados das páginas de categoria do OceanOfPDF.

## Escopo

O scraper coleta somente metadados disponíveis na listagem da categoria:

- título da obra;
- autor;
- gêneros;
- URL de origem;
- página de origem.

Ele **não baixa PDF, EPUB ou outros arquivos de livros**.

## Estrutura

```text
oceanofpdf_project/
├── README.md
├── requirements.txt
└── oceanofpdf/
    ├── __init__.py
    ├── config_oceanofpdf.json
    ├── http_client.py
    ├── models.py
    ├── pagination.py
    ├── parser.py
    ├── scraper.py
    ├── storage.py
    └── tests/
        ├── __init__.py
        ├── test_pagination.py
        ├── test_parser.py
        └── fixtures/
            └── omegaverse_page_1.html
```

## Instalação

A partir da pasta `oceanofpdf_project`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Testes offline

A fixture em `tests/fixtures/omegaverse_page_1.html` é a página fornecida para análise e permite validar o parser sem acessar o site.

```bash
python -m unittest discover -s oceanofpdf/tests -p 'test_*.py' -v
```

Os testes confirmam a extração das 7 obras da fixture e a geração correta das URLs das páginas 1, 2 e 452.

## Execução

Por padrão, a configuração aponta para a categoria `omegaverse`, páginas 1 a 452:

```bash
python -m oceanofpdf.scraper
```

Para validar primeiro um intervalo pequeno:

```bash
python -m oceanofpdf.scraper --start-page 1 --end-page 2
```

## Política de navegação e pausas

A configuração padrão evita uma varredura agressiva:

- espera aleatória de `1.5` a `3.5` segundos entre páginas;
- a cada `25` requisições realizadas na execução, faz uma pausa adicional aleatória de `10` a `20` segundos;
- falhas HTTP usam retry com backoff (`max_retries=2`, `retry_backoff=2`);
- após `5` erros consecutivos, a execução é interrompida e pode ser retomada depois usando o cache;
- páginas já concluídas não contam para o lote porque não geram nova requisição.

Esses valores ficam em `config_oceanofpdf.json` e podem ser ajustados sem alterar o código.

## Saídas

O módulo cria, quando executado:

```text
oceanofpdf/output/omegaverse.json
oceanofpdf/output/omegaverse.csv
oceanofpdf/output/omegaverse_cache.json
```

O cache registra páginas concluídas e registros já coletados. Se a execução for interrompida, uma nova execução ignora páginas já concluídas.

## Regras importantes

- página 1: `.../category/genres/omegaverse/`;
- página 2 em diante: `.../category/genres/omegaverse/page/{n}/`;
- uma página pode conter vários `article.post`;
- `Genre` é armazenado como lista;
- gêneros vazios causados por vírgulas duplicadas são ignorados;
- o título é preservado como aparece no HTML (`title_raw`), sem correção automática de sequências como `u0026`;
- cada registro guarda `source_url` e `source_page` para rastreabilidade;
- o scraper faz escrita atômica de JSON/CSV para reduzir risco de arquivo parcialmente gravado.

## Integração futura com o restante do Fominha_de_Novel

O módulo foi mantido isolado de `novellive`. Depois de estabilizado, componentes realmente compartilhados, como cliente HTTP, normalização de texto e política de retry, podem ser extraídos para uma camada `common/` sem alterar prematuramente o módulo existente.

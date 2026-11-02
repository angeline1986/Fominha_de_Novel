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

A partir da raiz do repositório, escolha a obra no menu inicial:

```bash
python -m nocfsb.menu
```

Para cadastrar outra obra do NOCFSB, escolha **N. Nova obra** na lista inicial
ou **5. Nova obra** dentro do menu. Informe o título, o autor e a URL base de cada
volume ou seção (sem o trecho do capítulo). Para uma sequência regular, informe
o primeiro e o último número. Se os endereços tiverem
sufixo comum, como `_1` em todos os capítulos de um volume, informe-o no campo
correspondente. Para sufixos diferentes entre capítulos, como `01-2` e `03_1`,
escolha **Lista exata** e informe os sufixos na
ordem em que aparecem no site. O programa cria uma
configuração, um cache e nomes de saída próprios para a obra e a deixa ativa
para a opção 1.

Para coletar **7 Minutes of Heaven**:

```bash
python -m nocfsb.menu --config nocfsb/config_7_minutes_of_heaven.json
```

A opção 1 salva o cache e o JSON após cada capítulo. Se a coleta for interrompida
com Ctrl+C, escolha 1 novamente para continuar das URLs pendentes. A opção 2
confere as URLs, a ordem, os títulos, os parágrafos e textos idênticos em
capítulos diferentes. A opção 3 repete essa validação local e, após montar o
EPUB, confere o ZIP, os arquivos dos capítulos, o manifesto e os índices antes
de publicar o arquivo final.

Para incluir uma capa própria nessa obra, coloque a imagem em
`nocfsb/cover_7_minutes_of_heaven.jpg`. Sem esse arquivo, o EPUB é gerado sem capa.

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

A validação local identifica capítulos ausentes, inesperados, repetidos ou fora
de ordem, títulos genéricos, parágrafos vazios ou inválidos e textos idênticos
em URLs diferentes. Ela é rápida porque lê os arquivos já coletados. Ela não
compara cada capítulo com o site em tempo real nem julga a qualidade da tradução.
Após a montagem, o EPUB também passa por verificação de integridade e estrutura.

## Saída

Ao rodar a extração e a geração EPUB, o módulo salva arquivos em:

```text
nocfsb/output/
```

Incluindo o JSON bruto dos capítulos e o arquivo EPUB final.

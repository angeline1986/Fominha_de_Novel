# Zhenhunxiaoshuo

Módulo independente do projeto **Fominha_de_Novel** para extrair capítulos de
`zhenhunxiaoshuo.com`, estruturar os dados em JSON, aplicar referências físicas
confirmadas, gerar EPUB e corrigir estruturalmente títulos depois da tradução.

## Execução

A partir da raiz do repositório:

```bash
python -m zhenhunxiaoshuo.menu
```

## Menu

```text
  ZHENHUNXIAOSHUO
  ──────────────────────────────────────────────────

  [🟡 MANIPULAÇÃO DE JSON]
  1. 📂 Extração       Extrair capítulos e gerar JSON
  2. 📝 Revisão        Ajustar JSON com referência física

  [🟢 PRODUÇÃO DE EPUB]
  3. 📚 Geração        Gerar arquivo EPUB final
  4. 🔧 Pós-Trad       Ajustar títulos do EPUB traduzido

  ──────────────────────────────────────────────────
  0. 🚪 Sair
  Selecione uma opção ›
```

As cores usam ANSI quando o terminal oferece suporte. Para desativá-las:

```bash
NO_COLOR=1 python -m zhenhunxiaoshuo.menu
```

## Fluxo

```text
Site + chapters.csv
        ↓
1. Extração
        ↓
JSON original
        ↓
2. Revisão com referência física
        ↓
JSON ajustado
        ↓
3. Geração de EPUB
        ↓
Tradução / Calibre
        ↓
4. Pós-Trad
        ├── EPUB original sem redundância
        ├── EPUB traduzido
        └── CSV de comparação
        ↓
EPUB traduzido corrigido
```

## Correção estrutural pós-tradução

A opção **4. Pós-Trad** exige três entradas:

```text
producao_epub/output/3_geracao/*.epub
producao_epub/input/traduzidos/*.epub
producao_epub/input/capitulos/comparacao_capitulos.csv
```

O CSV pode usar `;` ou `,`; o separador é detectado automaticamente.

O JSON ajustado não participa da Pós-Trad. Ele continua sendo usado na etapa
anterior, para gerar o EPUB original. Depois da tradução externa, a
correspondência física é validada comparando o EPUB original com o EPUB
traduzido.

O corretor usa:

```text
EPUB original
    → referência estrutural física dos XHTMLs e do spine

EPUB traduzido
    → conteúdo traduzido a preservar

CSV de comparação
    → referência editorial para os títulos
```

Se os EPUBs não tiverem correspondência estrutural 1:1, a correção é abortada
sem gerar EPUB parcial.

A correção atualiza:

- `<h1>` e `<title>` dos XHTMLs quando há título editorial no CSV;
- `nav.xhtml`;
- `toc.ncx`.

O spine é validado e preservado; a Pós-Trad não move capítulos nem renumera
arquivos.

Quando `Título no DOCX` está vazio, o título traduzido existente é preservado.
Isso é importante para capítulos que ainda não possuem título editorial de
referência e para extras.

## Estrutura relevante

```text
zhenhunxiaoshuo/
├── manipulacao_json/
│   ├── input/
│   │   ├── capitulos/
│   │   └── referencias/
│   ├── output/
│   │   ├── extraidos/
│   │   └── revisados/
│   └── src/
├── producao_epub/
│   ├── input/
│   │   ├── capas/
│   │   ├── capitulos/
│   │   └── traduzidos/
│   ├── output/
│   │   ├── gerados/
│   │   └── pos_traducao/
│   └── src/
├── menu.py
├── config_zhenhunxiaoshuo.json
└── README.md
```

## Segurança dos dados

O JSON original não é sobrescrito. A referência física gera um novo
`*_ajustado.json`.

Na pós-tradução, o EPUB traduzido também não é sobrescrito. O resultado é salvo
em:

```text
zhenhunxiaoshuo/producao_epub/output/4_pos_trad/
```

> Importante: o EPUB traduzido deve ter sido gerado a partir do JSON ajustado.

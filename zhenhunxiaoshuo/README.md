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
        ├── EPUB traduzido
        ├── CSV de títulos
        └── JSON ajustado
        ↓
EPUB traduzido corrigido
```

## Correção estrutural pós-tradução

A opção **4. Pós-Trad** exige três entradas:

```text
producao_epub/input/traduzidos/*.epub
producao_epub/input/capitulos/comparacao_capitulos.csv
manipulacao_json/output/revisados/*_ajustado.json
```

O CSV pode usar `;` ou `,`; o separador é detectado automaticamente.

O JSON ajustado é obrigatório porque a correspondência correta não pode ser
feita apenas por número de capítulo. A obra possui extras, duplicidades e
numerações inconsistentes na fonte.

O corretor usa:

```text
corrected_position
    → identifica qual XHTML contém aquele conteúdo no EPUB traduzido

story_chapter_number
    → identifica qual título editorial do CSV pertence ao capítulo

source_position
    → preserva a posição original do site para auditoria
```

Isso permite, por exemplo, que o capítulo narrativo 154 esteja fisicamente em
`chapter_155.xhtml`, enquanto o Extra de 20 de maio ocupa `chapter_156.xhtml`,
sem que o título editorial seja aplicado ao conteúdo errado.

A correção atualiza:

- `<h1>` e `<title>` dos XHTMLs quando há título editorial no CSV;
- `spine` do OPF;
- `nav.xhtml`;
- `toc.ncx`.

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
zhenhunxiaoshuo/producao_epub/output/pos_traducao/
```

> Importante: o EPUB traduzido deve ter sido gerado a partir do JSON ajustado.

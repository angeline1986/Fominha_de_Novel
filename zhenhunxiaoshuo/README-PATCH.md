# Atualização — menu + pastas de saída + capa

## Estrutura final

```text
zhenhunxiaoshuo/
├── input/
│   ├── chapters.csv
│   └── assets/
│       └── cover.jpg
├── output/
│   ├── json/
│   │   └── di_wang_gong_lue.json
│   └── epub/
│       └── <livro>.epub
├── epub/
│   ├── __init__.py
│   ├── models.py
│   ├── loader.py
│   ├── builder.py
│   └── validator.py
├── scraper.py
├── generate_epub.py
└── menu.py
```

## Onde colocar a capa

Use exatamente:

```text
zhenhunxiaoshuo/input/assets/cover.jpg
```

O menu procura esse caminho automaticamente. Se a imagem não existir,
o EPUB é gerado sem capa.

## Menu interativo

Na raiz do repositório:

```bash
python -m zhenhunxiaoshuo.menu
```

Menu:

```text
1. Gerar JSON dos capítulos
2. Gerar EPUB
0. Sair
```

Em "Gerar JSON":

```text
1. Todos os capítulos
2. Informar quantidade
0. Voltar
```

O JSON sempre é salvo em:

```text
zhenhunxiaoshuo/output/json/
```

O EPUB sempre é salvo em:

```text
zhenhunxiaoshuo/output/epub/
```

O builder usa apenas o JSON escolhido na execução atual.
Reports são somente saída e nunca são usados como fonte.

## CLI direta continua funcionando

```bash
python -m zhenhunxiaoshuo.scraper
python -m zhenhunxiaoshuo.scraper --limit 10
```

e:

```bash
python -m zhenhunxiaoshuo.generate_epub   --json zhenhunxiaoshuo/output/json/di_wang_gong_lue.json   --title "Título do livro"   --author "Autor"   --language zh-CN
```

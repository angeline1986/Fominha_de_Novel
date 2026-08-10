# Fominha de Novel

Scripts para extrair capítulos de novels pela web e gerar arquivos EPUB ou DOCX.

O fluxo principal atual usa o `scraper_epub_wfxs.py`, que recebe uma configuração em JSON com as URLs, seletores CSS, metadados do livro e capa.

## Requisitos

- Python 3.10 ou superior
- Dependências Python:

```bash
pip install requests beautifulsoup4 lxml ebooklib python-docx
```

## Uso Rápido

Para gerar o EPUB usando a configuração já criada:

```bash
python scraper_epub_wfxs.py --config config_novellive.json
```

O arquivo será gerado com o nome definido no campo `saida` do JSON.

## Configuração JSON

Exemplo usado em `config_novellive.json`:

```json
{
  "primeira_url": "https://novellive.app/book/the-editor-is-the-novels-extra/chapter-1",
  "ultima_url": "https://novellive.app/book/the-editor-is-the-novels-extra/chapter-192",
  "seletor_titulo": "h1.tit a",
  "seletor_titulo_capitulo": "span.chapter",
  "seletor_conteudo": ".txt",
  "titulo_livro": "The Editor Is the Novel's Extra",
  "autor": "Jongsuil",
  "saida": "The_Editor_Is_the_Novels_Extra-EN.epub",
  "capa": "input/Capa.jpg",
  "intervalo": 20,
  "intervalo_max": 45,
  "pausa_a_cada": 2,
  "pausa_lote": 180,
  "pausa_lote_max": 300,
  "pausa_erro": 120,
  "sincronizar_do_inicio": true,
  "intervalo_sincronizacao": 1,
  "intervalo_sincronizacao_max": 3,
  "timeout": 30,
  "motor": "playwright",
  "navegacao": "proximo",
  "seletor_proximo": "a:has-text('Next Chapter')",
  "max_erros_consecutivos": 3,
  "min_capitulos": 192,
  "cache": "cache/The_Editor_Is_the_Novels_Extra-EN.json",
  "parar_em_erro": false,
  "headers": {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
    "Referer": "https://novellive.app/book/the-editor-is-the-novels-extra",
    "Upgrade-Insecure-Requests": "1"
  }
}
```

### Campos

| Campo | Obrigatório | Descrição |
| --- | --- | --- |
| `primeira_url` | Sim | URL do primeiro capítulo. |
| `ultima_url` | Sim | URL do último capítulo. |
| `seletor_titulo_capitulo` | Sim | Seletor CSS que captura o título de cada capítulo. |
| `seletor_conteudo` | Sim | Seletor CSS que captura o bloco principal do texto. |
| `seletor_titulo` | Não | Seletor CSS para capturar o título do livro na primeira página. |
| `titulo_livro` | Não | Título manual do livro. Tem prioridade sobre `seletor_titulo`. |
| `autor` | Não | Autor usado nos metadados do EPUB. |
| `idioma` | Não | Idioma do EPUB. Padrão: `pt-BR`. |
| `saida` | Não | Nome do arquivo EPUB gerado. |
| `capa` | Não | Caminho da imagem de capa. Aceita `.jpg`, `.jpeg` e `.png`. |
| `intervalo` | Não | Tempo de espera, em segundos, entre requisições. |
| `intervalo_max` | Não | Se informado, usa espera aleatória entre `intervalo` e `intervalo_max`. |
| `pausa_a_cada` | Não | Faz uma pausa longa após esta quantidade de capítulos baixados. Use `0` para desativar. |
| `pausa_lote` | Não | Pausa longa mínima, em segundos, usada com `pausa_a_cada`. |
| `pausa_lote_max` | Não | Pausa longa máxima, em segundos. Se informada, usa pausa aleatória. |
| `pausa_erro` | Não | Pausa, em segundos, multiplicada pela quantidade de erros consecutivos. |
| `sincronizar_do_inicio` | Não | Se a abertura direta do último capítulo em cache falhar, sincroniza clicando desde o capítulo 1. |
| `intervalo_sincronizacao` | Não | Espera mínima entre cliques usados apenas para sincronizar capítulos em cache. |
| `intervalo_sincronizacao_max` | Não | Espera máxima entre cliques usados apenas para sincronizar capítulos em cache. |
| `timeout` | Não | Timeout, em segundos, para cada requisição ou navegação. |
| `encoding` | Não | Encoding manual, por exemplo `utf-8` ou `gb18030`. |
| `headers` | Não | Headers HTTP extras enviados nas requisições. |
| `cookies` | Não | Cookies como objeto JSON ou string do header `Cookie`. |
| `motor` | Não | Motor de extração: `requests` ou `playwright`. Padrão: `requests`. |
| `navegacao` | Não | No Playwright: `direta` abre cada URL; `proximo` clica no link do próximo capítulo. |
| `seletor_proximo` | Não | Seletor do link/botão de próximo capítulo usado com `navegacao: "proximo"`. |
| `parar_em_erro` | Não | Se `true`, interrompe no primeiro capítulo com erro. |
| `max_erros_consecutivos` | Não | Interrompe após esta quantidade de erros seguidos. Padrão: `3`. |
| `min_capitulos` | Não | Quantidade mínima de capítulos para permitir gerar o EPUB. Use `0` para desativar. |
| `cache` | Não | Arquivo JSON usado para salvar capítulos extraídos e retomar depois. |

## Capa

A capa pode ser configurada assim:

```json
"capa": "input/Capa.jpg"
```

Também é possível informar um caminho absoluto:

```json
"capa": "/Users/alinesouza/Documents/TI/Projetos/Fominha_de_Novel/input/Capa.jpg"
```

Se a capa for informada e o arquivo não existir, o script interrompe a execução com erro.

## Como o Intervalo de URLs Funciona

O script identifica a parte numérica que muda entre `primeira_url` e `ultima_url`.

Exemplo:

```text
https://site.com/capitulo/100/
https://site.com/capitulo/120/
```

Nesse caso, ele gera automaticamente:

```text
100, 101, 102 ... 120
```

No caso da Novellive:

```text
chapter-1
chapter-192
```

Ele gera de `chapter-1` até `chapter-192`.

Importante: as URLs precisam ter a mesma estrutura. Apenas uma parte numérica deve mudar.

## Usando Argumentos Sem JSON

O JSON é o jeito recomendado, mas também é possível passar tudo pela linha de comando:

```bash
python scraper_epub_wfxs.py \
  --primeira-url "https://novellive.app/book/the-editor-is-the-novels-extra/chapter-1" \
  --ultima-url "https://novellive.app/book/the-editor-is-the-novels-extra/chapter-192" \
  --seletor-titulo "h1.tit a" \
  --seletor-titulo-capitulo "span.chapter" \
  --seletor-conteudo ".txt" \
  --titulo-livro "The Editor Is the Novel's Extra" \
  --autor "Jongsuil" \
  --saida "The_Editor_Is_the_Novels_Extra-EN.epub" \
  --capa "input/Capa.jpg" \
  --intervalo 1
```

Também dá para misturar JSON com argumentos. Os argumentos da linha de comando sobrescrevem o JSON:

```bash
python scraper_epub_wfxs.py --config config_novellive.json --saida teste.epub
```

## Erro 403 Forbidden

Se o script mostrar erro como este logo no primeiro capítulo:

```text
403 Client Error: Forbidden
```

isso normalmente indica que o site recusou o acesso automatizado. Nesse caso, aumentar o `intervalo` pode não resolver, porque o bloqueio aconteceu antes de existir volume de requisições.

O projeto já envia headers de navegador no `config_novellive.json` e interrompe após `max_erros_consecutivos` para não tentar todos os capítulos inutilmente.

Se o site continuar bloqueando `requests`, teste o modo Playwright:

```bash
pip install playwright
python -m playwright install chromium
python scraper_epub_wfxs.py --config config_novellive.json --motor playwright
```

Também é possível fixar no JSON:

```json
"motor": "playwright"
```

Se mesmo com Playwright continuar retornando `403`, o site provavelmente exige uma sessão válida do navegador. Nesse caso, copie o valor do header `Cookie` do navegador e adicione ao JSON:

```json
"cookies": "cookie_1=valor; cookie_2=valor; cookie_3=valor"
```

Cookies expiram. Quando isso acontecer, copie novamente do navegador.

## Retomando Progresso

Use o campo `cache` para salvar cada capítulo assim que ele for extraído:

```json
"cache": "cache/The_Editor_Is_the_Novels_Extra-EN.json"
```

Se a execução cair no meio, rode o mesmo comando novamente:

```bash
python scraper_epub_wfxs.py --config config_novellive.json
```

O script carrega os capítulos já salvos no cache, reaproveita esse conteúdo e continua a extração. No modo `navegacao: "proximo"`, ele tenta abrir o último capítulo salvo no navegador e continua clicando em próximo a partir dele. Assim, os capítulos já extraídos não são baixados novamente.

Se o site bloquear a abertura direta do último capítulo salvo com `403`, e `sincronizar_do_inicio` estiver `true`, o script abre o capítulo 1 e avança por cliques até o último capítulo salvo. Ele não reextrai nem sobrescreve os capítulos em cache; esse passo serve só para posicionar o navegador no fluxo aceito pelo site.

Se precisar gerar um EPUB parcial para conferência, sobrescreva o mínimo pela linha de comando:

```bash
python scraper_epub_wfxs.py --config config_novellive.json --min-capitulos 0
```

## Saída EPUB

O EPUB gerado usa estrutura EPUB 3.0. O arquivo interno `EPUB/content.opf` é criado com `version="3.0"` e inclui `nav.xhtml`.

O script também adiciona `toc.ncx` para compatibilidade com leitores mais antigos.

## Scripts do Projeto

| Arquivo | Função |
| --- | --- |
| `scraper_epub_wfxs.py` | Extrai capítulos da web e gera EPUB. |
| `config_novellive.json` | Configuração de exemplo para Novellive. |
| `scraper_docx_wfxs.py` | Extrai capítulos e gera DOCX em lotes. |
| `gerar_epub_novel_traduzida.py` | Gera EPUB a partir de arquivos DOCX já traduzidos. |

## Observações

- Use seletores CSS específicos para evitar capturar menus, comentários ou anúncios.
- Ajuste `intervalo` para evitar muitas requisições seguidas ao site.
- Erro `403 Forbidden` normalmente indica bloqueio do site contra scripts, sessão/cookie ausente ou proteção anti-bot. Delay pode ajudar em bloqueio por volume, mas não resolve quando o primeiro capítulo já retorna 403.
- Se o texto vier com caracteres estranhos, teste informar `encoding`.
- O conteúdo extraído deve respeitar os termos de uso do site de origem.

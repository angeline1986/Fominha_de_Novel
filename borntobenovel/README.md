# Born to Be Novel

Módulo independente para coletar os capítulos 77 a 140 de **Mind the Gap** e
gerar JSON e EPUB. O intervalo e os caminhos de saída estão em
`config_mind_the_gap.json`.

## Uso

Na raiz do projeto:

```bash
pip install -r borntobenovel/requirements.txt
python -m borntobenovel.menu all
```

Também é possível executar as etapas separadamente:

```bash
python -m borntobenovel.menu collect
python -m borntobenovel.menu validate
python -m borntobenovel.menu epub
```

O módulo salva `output/mind-the-gap-77-140.json` e um cache após cada capítulo.
Os arquivos de `output/` são gerados localmente e ignorados pelo Git.
Se a coleta for interrompida, execute `collect` ou `all` novamente para
continuar apenas com os capítulos pendentes. O EPUB só é criado quando os 64
capítulos, seus títulos e seus parágrafos passam na validação.

O texto vem de `contentData`, codificado em base64 no HTML inicial. O leitor do
site preenche `#chapterContent` com JavaScript; por isso, selecionar apenas os
`p` na resposta HTTP não retorna os parágrafos. O parser também aceita o HTML
depois de renderizado pelo navegador.

## EPUB completo, capítulos 1 a 140

Use `merge_epubs.py` para juntar o EPUB antigo dos capítulos 1 a 76 ao JSON
coletado dos capítulos 77 a 140:

```bash
python -m borntobenovel.merge_epubs "/Volumes/Seagate2T/old/Check_Epub/Nao_Encontrados/73887_Mind the Gap - BornToBeNovel   Novel Translations.epub"
```

O resultado é `output/mind-the-gap-1-140.epub`. O script preserva a capa e a
página de informações, retira anúncios repetidos do EPUB antigo, recria o
índice e confere os 140 arquivos de capítulo. O EPUB de origem não é alterado.

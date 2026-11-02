# Backlog NOCFSB

## Pendente: separar a validação minuciosa da geração do EPUB

A opção **2. Validar coleta** deve ser a responsável pela conferência minuciosa dos capítulos. A opção **3. Gerar EPUB** deve se concentrar na geração e não repetir essa validação.

Critérios para retomar:

- A opção 2 verifica URLs esperadas, ordem, títulos, parágrafos vazios ou inválidos e textos repetidos entre capítulos, com relatório claro dos problemas.
- O resultado da validação fica associado à configuração e ao JSON examinados, para não ser reutilizado se a coleta mudar.
- A opção 3 consulta esse resultado; se estiver ausente ou desatualizado, orienta a executar a opção 2. Ela não executa novamente a conferência minuciosa da coleta.

Estado atual: a opção 3 ainda executa a validação local antes de gerar o EPUB. Nenhuma alteração de comportamento foi feita nesta tarefa.

# Contrato de interface — delta da 014

Nenhuma API HTTP muda. O contrato do shell (`specs/011-dashboard-v2/contracts/v2-ui-shell.md`, seção "Exportação") ganha:

## Exportar slide (página)

- **Onde**: barra de filtros de `/v2/instituicao`, à direita, ao lado de "Exportar CSV" (`.v2-fb-actions`). Rótulo "Exportar slide"; `title`: "Baixar o perfil da instituição como slide (imagem 16:9)". Alvo de toque ≥ 44 px. Desativado enquanto não houver dados.
- **Saída**: PNG 1600×900, nome `opf-instituicao-<instituição>-slide-<AAAA-MM-DD>.png`.
- **Quadro**: igual ao das imagens por bloco — subtítulo, título (instituição, período e comparação), rodapé com "Fonte: dashboard Open Finance Brasil · dados até DD/MM/AAAA".
- **Conteúdo**: 4 indicadores; evolução e transmissores empilhados numa coluna; "Quais dados busca" em coluna inteira, completo. Fora: alertas, taxa de erro de API e chamadas por grupo.
- **Texto**: nunca abaixo de `--text-caption`; só os transmissores são cortados nos maiores itens com "+N"; "Quais dados busca" nunca é cortado (se não couber, a exportação avisa).
- **Estado**: reproduz a tela (instituição, comparação, período, métrica da evolução, unidade, visão por grupo ou endpoint).

## Shell (`window.V2`)

- `V2.exportSlide(opts)`: `{ title, subtitle, note, filename, rows: [{ weight, cells: [cell | { weight, stack: [cell, …] }] }] }`, com `cell = { el, weight, title?, more?, chart? }`. Compõe a grade, ajusta as listas e baixa o PNG. Erros iguais aos de `V2.exportImage` (rejeita a promessa).
- `V2.exportImage(card, opts)`: contrato inalterado.

## Renomeação

O bloco "Para que usa os dados" de `/v2/instituicao` passa a se chamar **"Quais dados busca"** (título na página, nas imagens por bloco e no slide). Só o título muda.

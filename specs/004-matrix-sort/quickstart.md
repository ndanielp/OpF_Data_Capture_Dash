# Quickstart — Validação Manual: Matriz Ordenável

**Servidor**: `cd dashboard && uvicorn server:app --reload --port 8000`  
**Página**: `http://localhost:8000/active-consents`

## Cenário 1 — Ordenação padrão ao carregar

1. Abrir a página Ativos.
2. Aguardar a matriz carregar (loading sweep desaparece).
3. **Verificar**: a primeira linha (receptor) tem o maior total de consentimentos.
4. **Verificar**: a primeira coluna (transmissor) tem o maior total de consentimentos.
5. **Verificar**: não há nenhum `<th>` com `.sort-active`.
6. **Verificar**: botão "↺ Redefinir" está oculto.

## Cenário 2 — Reordenar colunas clicando em receptor

1. Com a matriz carregada, clicar no nome de um receptor (texto na primeira coluna de uma linha).
2. **Verificar**: as colunas de transmissores se reordenam imediatamente (< 200ms, sem chamada de rede).
3. **Verificar**: o receptor clicado tem o `<th>` de linha com sublinhado pontilhado + negrito (`.sort-active`).
4. **Verificar**: botão "↺ Redefinir" aparece.
5. Clicar em outro receptor diferente.
6. **Verificar**: colunas se reordenam novamente; `.sort-active` move para o novo receptor.

## Cenário 3 — Reordenar linhas clicando em transmissor

1. Clicar no nome de um transmissor (cabeçalho de coluna no `<thead>`).
2. **Verificar**: as linhas de receptores se reordenam imediatamente.
3. **Verificar**: o transmissor clicado tem o `<th>` com `.sort-active`.
4. **Verificar**: botão "↺ Redefinir" aparece.
5. **Verificar**: nenhum receptor está com `.sort-active` (critério anterior cancelado).

## Cenário 4 — Redefinir ordenação

1. Após clicar em qualquer receptor ou transmissor, clicar em "↺ Redefinir".
2. **Verificar**: a matriz volta à ordenação padrão (Cenário 1).
3. **Verificar**: nenhum `<th>` tem `.sort-active`.
4. **Verificar**: botão "↺ Redefinir" some (fica oculto).

## Cenário 5 — Filtro redefine ordenação automaticamente

1. Clicar em um receptor para reordenar as colunas.
2. Alterar o período via quick-range (ex.: clicar em "3m").
3. **Verificar**: após a matriz recarregar, a ordenação está no padrão (sem `.sort-active`, sem botão reset visível).

## Cenário 6 — Receptor com todos os valores zero

1. Identificar (via inspeção do console) um receptor com linha totalmente zerada.
2. Clicar nesse receptor.
3. **Verificar**: as colunas ficam ordenadas pela ordem padrão (nenhum erro no console).

## Cenário 7 — Layout sem scroll horizontal

1. Executar qualquer cenário acima com viewport 1280 × 800.
2. **Verificar**: a tabela usa scroll horizontal interno (`.matrix-scroll`) e não causa scroll horizontal na página.

## Checklist rápido de console

- Abrir DevTools → Console antes de iniciar os cenários.
- Nenhum erro `TypeError`, `ReferenceError` ou `Uncaught` deve aparecer.
- Requests de rede na aba Network: apenas 1 chamada a `/api/active-consents/matrix` por mudança de filtro; cliques no cabeçalho não disparam requests.

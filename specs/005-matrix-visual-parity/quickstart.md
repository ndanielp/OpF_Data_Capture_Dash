# Quickstart — Validação Manual: Visual Parity da Matriz

**Servidor**: `cd dashboard && uvicorn server:app --reload --port 8000`  
**Página Ativos**: `http://localhost:8000/active-consents`  
**Página Ecossistema** (para comparação): `http://localhost:8000`

## Cenário 1 — Células com cantos arredondados e espaçamento

1. Abrir a página Ativos e aguardar a matriz carregar.
2. **Verificar**: as células de dados da matriz têm cantos arredondados (não quadrados).
3. **Verificar**: há um espaçamento visível entre células adjacentes (não separadas por linhas de borda, mas por gap).
4. Abrir a página Ecossistema e comparar visualmente com o heatmap "Intensidade de Uso das APIs".
5. **Verificar**: o aspecto visual das células é equivalente entre as duas tabelas.

## Cenário 2 — Efeito de hover nas células

1. Na página Ativos com a matriz carregada, passar o mouse sobre uma célula de dados com valor > 0.
2. **Verificar**: a célula aumenta ligeiramente de tamanho (escala) e fica levemente transparente.
3. **Verificar**: o efeito é suave (transição animada), não abrupto.
4. **Verificar**: o efeito é identicamente ao hover das células do heatmap no Ecossistema.

## Cenário 3 — Células com valor zero

1. Identificar (via inspeção ou observação) células da matriz com valor 0.
2. **Verificar**: células zero exibem `—` (traço).
3. **Verificar**: o fundo dessas células usa a cor de superfície elevada (não aplica o gradiente de calor).
4. **Verificar**: sem erro no console ao renderizar células zero.

## Cenário 4 — Paleta de cores da escala de calor

1. Comparar visualmente a graduação de cores das células da matriz (Ativos) com o heatmap (Ecossistema).
2. **Verificar**: células de baixa intensidade têm fundo azul claro/pastel (não azul escuro ou preto).
3. **Verificar**: células de alta intensidade têm fundo azul médio (não azul brilhante/neon).
4. **Verificar**: o valor de texto em células escuras é claro (branco/creme); em células claras é escuro.

## Cenário 5 — Tipografia das células

1. Observar os valores numéricos dentro das células da matriz.
2. **Verificar**: os valores usam fonte proporcional (não monoespaçada como JetBrains Mono).
3. **Verificar**: o tamanho e peso da fonte são visualmente equivalentes às células do heatmap.

## Cenário 6 — Indicadores de cor nos receptores

1. Com a matriz carregada, observar a coluna esquerda (nomes dos receptores).
2. **Verificar**: receptores com cor de marca definida exibem um pequeno ponto colorido à esquerda do nome.
3. **Verificar**: a cor do ponto corresponde à cor usada no sidebar (`.receptor-dot`) para o mesmo receptor.
4. **Verificar**: receptores sem cor de marca definida renderizam sem ponto, sem erro visual.
5. Comparar com o heatmap do Ecossistema — os mesmos pontos coloridos devem aparecer para os mesmos receptores.

## Cenário 7 — Tipografia dos cabeçalhos de transmissores

1. Observar a linha de cabeçalho da tabela (nomes dos transmissores).
2. **Verificar**: os cabeçalhos de transmissores têm texto muted/suavizado (menos contrastante que os dados).
3. **Verificar**: o estilo tipográfico é equivalente aos cabeçalhos de coluna do heatmap do Ecossistema.

## Cenário 8 — Retrocompatibilidade com feature 004 (ordenação)

1. Com a matriz carregada, clicar no nome de um receptor.
2. **Verificar**: as colunas se reordenam imediatamente (feature 004 intacta).
3. **Verificar**: os indicadores de cor permanecem visíveis após a reordenação.
4. **Verificar**: o botão "↺ Redefinir" aparece.
5. Clicar em um cabeçalho de transmissor → verificar reordenação das linhas.
6. Clicar em "↺ Redefinir" → verificar retorno à ordem padrão.

## Cenário 9 — Temas claro e escuro

1. Com a matriz visível, alternar entre o tema escuro e claro via botão de tema.
2. **Verificar**: a paleta de calor das células permanece legível nos dois temas.
3. **Verificar**: os indicadores de cor dos receptores permanecem visíveis nos dois temas.
4. **Verificar**: zero erro de console durante a troca de tema.

## Cenário 10 — Layout sem scroll horizontal

1. Com viewport 1280 × 800, verificar que a tabela usa scroll interno (`.matrix-scroll`) e não causa scroll horizontal na página.

## Checklist rápido de console

- Abrir DevTools → Console antes de iniciar os cenários.
- Nenhum erro `TypeError`, `ReferenceError` ou `Uncaught` deve aparecer.
- Cliques nos cabeçalhos e na tabela NÃO devem disparar requests de rede.
- Apenas mudanças de filtro disparam request para `/api/active-consents/matrix`.

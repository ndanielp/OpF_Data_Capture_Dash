# Feature Specification: Melhorias no Dashboard de Consentimentos Ativos

**Feature Branch**: `007-active-consents-improvements`

**Created**: 2026-05-26

**Status**: Draft

**Input**: User description: "1. Quero ver os top receptores e transmissores de consentimento ativo como um gráfico tornado ordenado pelo receptores. 2. Quero trocar o nome de ativos para Consentimento Ativo. 3. Quero que a evolução de consentimentos ativos apareça lado a lado com o tornado a depender do tamanho da janela. 4. Quero ajustar a ordem das Tab: Ecosistema, Consentimentos Ativos, Perfil Receptor. 5. Quero que na tab ecosistema o quadro Evolução Consentimento chame Evolução Consentimentos Únicos. 6. Quero que na Matriz receptor × transmissor da tab Consentimentos Ativos a primeira linha e primeira coluna seja o total. 7. Quero que os números apareçam na matriz de forma resumida, por exemplo, 1514 aparece como 1,51 k."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Gráfico Tornado de Top Receptores e Transmissores (Priority: P1)

O analista abre a aba "Consentimentos Ativos" e visualiza imediatamente um gráfico tornado que compara lado a lado os maiores receptores (barras para a esquerda) e os maiores transmissores (barras para a direita) por volume de consentimentos ativos. As linhas do gráfico são ordenadas pelo total do receptor correspondente, do maior para o menor. Em janelas largas, o gráfico tornado aparece lado a lado com o gráfico de evolução temporal dos consentimentos ativos. Em janelas estreitas, cada um ocupa a largura total da tela empilhados verticalmente.

**Why this priority**: É a visualização nova mais valiosa — permite comparar instantaneamente quais instituições têm mais consentimentos como receptoras vs. como transmissoras, revelando desequilíbrios no ecossistema.

**Independent Test**: Pode ser testado abrindo a aba "Consentimentos Ativos" sem nenhuma outra mudança e verificando se o gráfico tornado é renderizado com barras simétricas, ordenado por receptor, com layout responsivo correto.

**Acceptance Scenarios**:

1. **Given** a aba "Consentimentos Ativos" está aberta e dados estão carregados, **When** o usuário observa o painel de top instituições, **Then** vê um gráfico tornado com os top N receptores/transmissores em pares de barras horizontais — barras de receptor à esquerda do eixo central, barras de transmissor à direita — ordenadas decrescentemente pelo total do receptor.
2. **Given** o gráfico tornado está visível, **When** o usuário passa o mouse sobre uma barra, **Then** vê tooltip com o nome completo da instituição e o valor numérico (já abreviado) de consentimentos ativos.
3. **Given** uma janela com largura ≥ 900 px, **When** o usuário acessa a aba "Consentimentos Ativos", **Then** o gráfico tornado e o gráfico de evolução temporal ficam lado a lado (colunas iguais ou proporcionais).
4. **Given** uma janela com largura < 900 px, **When** o usuário acessa a aba "Consentimentos Ativos", **Then** o gráfico tornado e o de evolução aparecem empilhados verticalmente (cada um ocupa 100% da largura).
5. **Given** os filtros de receptor ou período são alterados, **When** os dados são recarregados, **Then** o gráfico tornado atualiza com os novos dados mantendo o mesmo layout.

---

### User Story 2 — Linha e Coluna de Totais na Matriz + Números Abreviados (Priority: P2)

O analista visualiza a matriz receptor × transmissor e agora pode ler, na primeira linha (cabeçalho de receptor) e na primeira coluna (nome do transmissor posicionada como header), o total consolidado de cada receptor e cada transmissor. Além disso, todos os números na matriz aparecem em formato compacto e legível: valores ≥ 1000 são exibidos como "X,XX k" (com vírgula como separador decimal, em português-BR).

**Why this priority**: Facilita a leitura rápida dos maiores players sem precisar somar mentalmente as linhas/colunas; o formato abreviado reduz o ruído visual especialmente em matrizes densas.

**Independent Test**: Pode ser testado isoladamente na matriz existente: verificar se a primeira linha exibe somas por transmissor, se a primeira coluna exibe somas por receptor, e se "1514" aparece como "1,51 k".

**Acceptance Scenarios**:

1. **Given** a matriz receptor × transmissor está carregada, **When** o usuário observa a linha de cabeçalho dos transmissores, **Then** a primeira célula dessa linha exibe o rótulo "Total" e cada célula subsequente mostra a soma total de consentimentos ativos daquele transmissor (sobre todos os receptores visíveis).
2. **Given** a matriz está carregada, **When** o usuário observa a coluna de rótulos dos receptores, **Then** a primeira célula (após o cabeçalho de colunas) exibe o rótulo "Total" e cada célula abaixo mostra a soma total daquele receptor (sobre todos os transmissores visíveis).
3. **Given** a linha/coluna de totais está visível, **When** o usuário aplica filtros que alteram os dados da matriz, **Then** os totais são recalculados corretamente.
4. **Given** um valor na matriz é 1514, **When** a matriz é renderizada, **Then** esse valor aparece como "1,51 k".
5. **Given** um valor na matriz é 999, **When** a matriz é renderizada, **Then** esse valor aparece como "999" (sem abreviação para valores < 1000).
6. **Given** uma célula de total tem valor zero, **When** a matriz é renderizada, **Then** essa célula exibe "—" (mesma convenção das células de dados zero).
7. **Given** a ordenação interativa (feature 004) está ativa, **When** o usuário clica para reordenar por transmissor ou receptor, **Then** a linha/coluna de totais permanece fixada na primeira posição (não entra na permutação de ordenação).

---

### User Story 3 — Renomeações e Reordenação de Navegação (Priority: P3)

O usuário navega pelo dashboard e encontra a aba com o nome correto "Consentimentos Ativos" (em vez de "Ativos"), as abas na ordem correta (Ecosistema → Consentimentos Ativos → Perfil Receptor), e o quadro de evolução no Ecossistema com o nome preciso "Evolução Consentimentos Únicos".

**Why this priority**: Melhoria cosmética e de clareza — não adiciona funcionalidade nova mas elimina ambiguidade nos nomes. Implementação rápida e sem risco.

**Independent Test**: Pode ser testado sem nenhuma outra mudança verificando o texto das abas na navegação e o título do gráfico na aba Ecossistema.

**Acceptance Scenarios**:

1. **Given** o dashboard está aberto, **When** o usuário observa as abas de navegação, **Then** vê exatamente três abas na ordem: "Ecosistema", "Consentimentos Ativos", "Perfil Receptor".
2. **Given** o usuário clica na aba "Consentimentos Ativos", **Then** é redirecionado para a página que antes se chamava "Ativos".
3. **Given** o usuário está na aba "Ecosistema", **When** observa o quadro de evolução temporal de consentimentos, **Then** vê o título "Evolução Consentimentos Únicos" (e não "Evolução Consentimento" sem o "s" e sem "Únicos").

---

### Edge Cases

- O que acontece quando há empate no total de receptores na ordenação do tornado — deve haver critério de desempate alfabético.
- O que acontece quando há menos de 10 receptores/transmissores — o tornado exibe todos os disponíveis (não força N mínimo).
- O que acontece quando um receptor tem consentimentos mas nenhum transmissor correspondente na matriz — aparece no tornado de receptor mas não no de transmissor (barra de transmissor com valor 0 ou omitida).
- O que acontece com o formato abreviado para valores ≥ 1.000.000 — exibir como "X,XX M" para manter consistência (ex.: 1.514.000 → "1,51 M").
- A linha/coluna de totais deve ser excluída da lógica de ordenação interativa (feature 004) — sempre permanece na posição fixa.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE exibir na aba "Consentimentos Ativos" um gráfico tornado com barras horizontais simétricas representando os top receptores (esquerda) e top transmissores (direita) por volume de consentimentos ativos.
- **FR-002**: O gráfico tornado DEVE ser ordenado decrescentemente pelo total do receptor, com desempate alfabético.
- **FR-003**: O gráfico tornado e o gráfico de evolução temporal de consentimentos ativos DEVEM aparecer lado a lado em janelas ≥ 900 px e empilhados verticalmente em janelas < 900 px.
- **FR-004**: Cada barra do tornado DEVE exibir tooltip com nome completo e valor abreviado ao ser hoverada.
- **FR-005**: A matriz receptor × transmissor DEVE exibir uma linha de totais fixada no topo (primeira linha do corpo da tabela) com a soma de cada transmissor sobre todos os receptores visíveis.
- **FR-006**: A matriz receptor × transmissor DEVE exibir uma coluna de totais fixada à esquerda (primeira célula de cada linha de receptor) com a soma de cada receptor sobre todos os transmissores visíveis.
- **FR-007**: A linha e coluna de totais DEVEM permanecer fixadas na posição original durante ordenações interativas (feature 004 intacta).
- **FR-008**: Todos os valores numéricos na matriz DEVEM ser exibidos em formato abreviado: valores < 1.000 sem abreviação; ≥ 1.000 e < 1.000.000 como "X,XX k"; ≥ 1.000.000 como "X,XX M" (separador decimal: vírgula, em português-BR).
- **FR-009**: Células de total com valor zero DEVEM exibir "—" (mesma convenção das células de dados).
- **FR-010**: A navegação DEVE exibir as abas na ordem: "Ecosistema", "Consentimentos Ativos", "Perfil Receptor".
- **FR-011**: A aba anteriormente chamada "Ativos" DEVE ser renomeada para "Consentimentos Ativos" em todos os pontos visíveis da interface (título da aba, título da página, breadcrumbs se houver).
- **FR-012**: O quadro de evolução temporal na aba "Ecosistema" DEVE ser renomeado de "Evolução Consentimento" para "Evolução Consentimentos Únicos".
- **FR-013**: O gráfico tornado DEVE respeitar os filtros ativos (período, receptor selecionado) e atualizar automaticamente quando os filtros forem alterados.
- **FR-014**: Os totais da linha/coluna da matriz DEVEM ser recalculados após mudança de filtros.

### Key Entities

- **Consentimento Ativo**: Registro de consentimento vigente agrupado por receptor e transmissor com contagem total.
- **Tornado de Participantes**: Visualização comparativa de top receptores (esquerda) × top transmissores (direita), ordenada por volume de receptor.
- **Linha/Coluna de Totais**: Linha adicional no topo e coluna adicional à esquerda da matriz com somas marginais por transmissor e por receptor, respectivamente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O gráfico tornado renderiza e fica interativo em menos de 1 segundo após o carregamento dos dados da aba "Consentimentos Ativos".
- **SC-002**: 100% das células da matriz com valor ≥ 1000 exibem o formato abreviado correto (X,XX k / X,XX M).
- **SC-003**: A linha e coluna de totais exibem valores consistentes com a soma das linhas/colunas visíveis da matriz em 100% dos cenários testados (incluindo após filtros e reordenação).
- **SC-004**: O layout lado a lado do tornado + evolução é exibido corretamente em janelas ≥ 900 px e o layout empilhado em janelas < 900 px, sem scroll horizontal.
- **SC-005**: As três abas aparecem na ordem correta e com os nomes corretos em 100% dos acessos, sem regressão nas funcionalidades existentes.

## Assumptions

- O número de "top" receptores/transmissores exibidos no tornado usa o mesmo limite já configurado nos rankings existentes da página (padrão assumido: 10).
- O formato de abreviação usa vírgula como separador decimal (padrão pt-BR): "1,51 k" e não "1.51k".
- A linha de totais da matriz usa rótulo "Total" na coluna de nome do receptor; a célula de intersecção (canto superior esquerdo) exibe "Total" em ambos os eixos.
- O gráfico de evolução temporal já existente na aba "Consentimentos Ativos" não tem seu conteúdo ou dados alterados — apenas o posicionamento no layout responsivo.
- A feature 004 (ordenação interativa da matriz) permanece funcional: a linha/coluna de totais é excluída da permutação de ordenação.
- A feature 005 (visual parity da matriz) permanece intacta: formato abreviado substitui apenas o texto, não o estilo visual das células.
- "Perfil Receptor" é a terceira aba e já existe (`receptor_profile.html`); nenhuma mudança de conteúdo é necessária, apenas reordenação se houver.

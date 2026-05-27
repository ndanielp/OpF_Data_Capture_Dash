# Feature Specification: Ordenação Interativa da Matriz Receptor × Transmissor (Ativos)

**Feature Branch**: `004-matrix-sort`

**Created**: 2026-05-26

**Status**: Draft

**Input**: User description: "Quero que em ativos, na matriz receptor x transmissor seja ordenado. Para receptor colocar quem mais recebe no topo. Para transmissor colocar quem mais transmite a esquerda. Quero a opção de clicar em uma linha de receptor e reordenar as colunas de transmissores. O mesmo para a coluna de transmissor. Tb quero uma opção para voltar a ordenação inicial."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Ordenação padrão por volume total (Priority: P1)

Ao carregar a página Ativos, a matriz receptor × transmissor já aparece ordenada de forma útil: receptores com mais consentimentos ativos estão no topo e transmissores com mais consentimentos ativos estão à esquerda. O analista enxerga imediatamente os pares mais relevantes sem precisar escanear a tabela manualmente.

**Why this priority**: É o comportamento mínimo viável — resolver a dor principal de ter que "adivinhar" qual receptor/transmissor é mais relevante. Entrega valor mesmo sem a interatividade de clique.

**Independent Test**: Pode ser testado abrindo a página Ativos e verificando que o receptor com maior soma de consentimentos aparece na primeira linha e o transmissor com maior soma aparece na primeira coluna.

**Acceptance Scenarios**:

1. **Given** a matriz carregada com dados do período selecionado, **When** o usuário não realiza nenhuma ação, **Then** os receptores aparecem ordenados de forma decrescente pelo total de consentimentos recebidos de todos os transmissores no período.
2. **Given** a matriz carregada, **When** o usuário não realiza nenhuma ação, **Then** os transmissores aparecem ordenados de forma decrescente pelo total de consentimentos enviados para todos os receptores no período.
3. **Given** o usuário altera o período (data start/end ou quick-range), **When** a matriz recarrega, **Then** a ordenação padrão é reaplicada com base nos novos totais.
4. **Given** a matriz carregada, **When** há empate em volume total, **Then** os itens empatados são ordenados alfabeticamente pelo nome.

---

### User Story 2 — Reordenar transmissores clicando em um receptor (Priority: P2)

O analista quer entender quais transmissores mais contribuem para um receptor específico. Ao clicar no nome de um receptor na tabela, as colunas de transmissores são reordenadas de forma decrescente pelo volume desse receptor. O receptor clicado fica visualmente destacado para indicar que está sendo usado como critério de ordenação.

**Why this priority**: Permite análise focada em um receptor sem precisar exportar dados. Agrega valor analítico real após a ordenação padrão (P1) já estar funcionando.

**Independent Test**: Pode ser testado clicando em qualquer linha de receptor e verificando que as colunas se reordenam imediatamente com o transmissor de maior valor para aquele receptor na posição mais à esquerda.

**Acceptance Scenarios**:

1. **Given** a matriz carregada, **When** o usuário clica no nome de um receptor (célula de cabeçalho de linha), **Then** as colunas de transmissores são reordenadas de forma decrescente pelo número de consentimentos daquele receptor.
2. **Given** o usuário clicou em um receptor, **When** a reordenação é aplicada, **Then** o receptor clicado aparece visualmente destacado (ex.: texto em negrito ou sublinhado) indicando que é o critério ativo.
3. **Given** o usuário clicou em um receptor, **When** clica em outro receptor diferente, **Then** as colunas são reordenadas pelo novo receptor e o destaque muda para o novo.
4. **Given** o usuário clicou em um receptor, **When** o receptor tem valor zero para todos os transmissores, **Then** a ordenação das colunas é mantida na ordem padrão (decrescente por total geral) sem erro.

---

### User Story 3 — Reordenar receptores clicando em um transmissor (Priority: P2)

Simetricamente ao US2, o analista pode clicar no nome de um transmissor (cabeçalho de coluna) para reordenar as linhas de receptores de forma decrescente pelo volume daquele transmissor. O transmissor clicado fica destacado.

**Why this priority**: Mesma prioridade que US2 — são comportamentos simétricos e complementares. O analista pode querer responder "quais receptores são mais ativos para o Bradesco?" tanto quanto "quais transmissores mais atendem o Nubank?".

**Independent Test**: Pode ser testado clicando em qualquer cabeçalho de coluna de transmissor e verificando que as linhas de receptores se reordenam imediatamente.

**Acceptance Scenarios**:

1. **Given** a matriz carregada, **When** o usuário clica no nome de um transmissor (célula de cabeçalho de coluna), **Then** as linhas de receptores são reordenadas de forma decrescente pelo número de consentimentos daquele transmissor.
2. **Given** o usuário clicou em um transmissor, **When** a reordenação é aplicada, **Then** o transmissor clicado aparece visualmente destacado.
3. **Given** o usuário clicou em um transmissor e depois clica em um receptor, **Then** o sistema usa o receptor como novo critério e remove o destaque do transmissor.

---

### User Story 4 — Botão "Redefinir ordenação" (Priority: P3)

O analista realizou várias reordenações por clique e quer voltar ao estado inicial (ordenação padrão por total geral). Um botão ou link "Redefinir ordenação" restaura a ordem padrão e remove todos os destaques de receptor/transmissor selecionado.

**Why this priority**: É funcionalidade de conveniência — o usuário pode recarregar a página para o mesmo efeito. Agrega polimento à experiência, mas não bloqueia o uso.

**Independent Test**: Pode ser testado clicando em um receptor, depois no botão de redefinir, e verificando que a matriz volta à ordenação padrão (P1) sem necessidade de recarregar a página.

**Acceptance Scenarios**:

1. **Given** o usuário realizou uma reordenação por clique (receptor ou transmissor), **When** clica em "Redefinir ordenação", **Then** a matriz retorna à ordenação padrão por total decrescente e todos os destaques são removidos.
2. **Given** a matriz está na ordenação padrão (nenhum clique aplicado), **When** o botão "Redefinir ordenação" está presente, **Then** ele aparece desabilitado ou oculto para não criar confusão.
3. **Given** o usuário aplica um novo filtro de data ou receptor na barra de filtros, **When** a matriz recarrega, **Then** a ordenação é redefinida automaticamente para o padrão (como se "Redefinir" tivesse sido clicado).

---

### Edge Cases

- O que acontece quando a matriz tem apenas 1 receptor ou 1 transmissor? A reordenação é aplicada normalmente (sem erro), mas sem efeito visual perceptível nas linhas/colunas.
- O que acontece quando a matriz está vazia (sem dados para o período)? Nenhuma ordenação é aplicada; a mensagem de "sem dados" existente é mantida.
- O que acontece quando a célula de um par receptor/transmissor é zero ou ausente? Valores zero/ausente são tratados como 0 para fins de ordenação (aparecem no final).
- O que acontece se o usuário clicar rapidamente em vários receptores/transmissores? Cada clique aplica a ordenação para o item clicado, sem animações pendentes ou estados inconsistentes.
- O que acontece ao trocar o filtro "Evolução por Receptor / Transmissor"? A reordenação por clique é independente desse toggle (que controla outro gráfico); a matriz não é afetada.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A matriz DEVE exibir receptores ordenados de forma decrescente pelo total de consentimentos recebidos de todos os transmissores, ao carregar ou recarregar os dados.
- **FR-002**: A matriz DEVE exibir transmissores ordenados de forma decrescente pelo total de consentimentos enviados para todos os receptores, ao carregar ou recarregar os dados.
- **FR-003**: Em caso de empate em volume total, os itens DEVEM ser ordenados alfabeticamente pelo nome como critério de desempate.
- **FR-004**: O usuário DEVE poder clicar no nome de qualquer receptor para reordenar as colunas de transmissores de forma decrescente pelo valor daquele receptor.
- **FR-005**: O usuário DEVE poder clicar no nome de qualquer transmissor para reordenar as linhas de receptores de forma decrescente pelo valor daquele transmissor.
- **FR-006**: O receptor ou transmissor usado como critério de ordenação por clique DEVE ser visualmente destacado na tabela enquanto a ordenação estiver ativa.
- **FR-007**: Apenas um critério de ordenação por clique pode estar ativo por vez (clicar em um receptor cancela o destaque de qualquer transmissor selecionado, e vice-versa).
- **FR-008**: O usuário DEVE ter acesso a um controle ("Redefinir ordenação") para restaurar a ordenação padrão (FR-001 + FR-002) e remover destaques.
- **FR-009**: O controle "Redefinir ordenação" DEVE ficar desabilitado ou oculto quando a ordenação já está no estado padrão.
- **FR-010**: Quando o usuário altera qualquer filtro (período, receptores na sidebar), a ordenação DEVE ser redefinida automaticamente para o padrão ao recarregar a matriz.
- **FR-011**: A reordenação DEVE ser realizada no lado cliente (sem nova chamada à API), usando os dados já carregados na tabela.

### Key Entities

- **Matriz receptor × transmissor**: Tabela com receptores nas linhas e transmissores nas colunas; cada célula contém o número de consentimentos ativos para aquele par no período selecionado.
- **Critério de ordenação ativo**: Estado da UI indicando qual receptor ou transmissor foi clicado para reordenação, ou "padrão" se nenhum clique foi aplicado.
- **Total por receptor**: Soma dos valores de todas as colunas (transmissores) para uma linha (receptor).
- **Total por transmissor**: Soma dos valores de todas as linhas (receptores) para uma coluna (transmissor).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Ao carregar a matriz, o receptor com maior volume aparece na primeira linha em 100% dos carregamentos com dados disponíveis.
- **SC-002**: Ao carregar a matriz, o transmissor com maior volume aparece na primeira coluna em 100% dos carregamentos com dados disponíveis.
- **SC-003**: Após clicar em um receptor, as colunas se reordenam visualmente em menos de 200ms (sem chamada à rede).
- **SC-004**: Após clicar em "Redefinir ordenação", a matriz retorna ao estado padrão em menos de 200ms.
- **SC-005**: A matriz permanece utilizável (sem erros visuais ou de layout) em viewport de 1280 × 800 após qualquer reordenação.
- **SC-006**: O critério de ordenação ativo (destaque no receptor/transmissor clicado) é visualmente distinguível sem dependência de cor como único indicador (acessibilidade mínima).

## Assumptions

- A reordenação é inteiramente client-side — os dados da matriz já estão na DOM/memória quando o clique ocorre; nenhuma nova chamada à API é necessária.
- O controle "Redefinir ordenação" é posicionado no cabeçalho ou próximo da matriz (ex.: botão no `.chart-head` do card da matriz), não em um local global de filtros.
- A ordenação por clique não é persistida em `sessionStorage` — ao navegar para outra página e voltar, a ordem padrão é restaurada.
- O comportamento de destaque visual (FR-006) utiliza os mecanismos CSS já disponíveis no sistema de design (bold, sublinhado ou classe CSS), sem introduzir novas dependências visuais.
- A feature é restrita à página Ativos (`active_consents.html`); as matrizes de outras páginas (se existirem) não são afetadas.

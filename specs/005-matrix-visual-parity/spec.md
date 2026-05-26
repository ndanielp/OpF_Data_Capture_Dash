# Feature Specification: Visual Parity — Matriz Receptor × Transmissor

**Feature Branch**: `005-matrix-visual-parity`

**Created**: 2026-05-26

**Status**: Draft

**Input**: User description: "Quero que em ativos o grupo Matriz receptor x transmissor seja semelhante ao grupo intensidade de uso Api em Ecossistema (look and feel, cores, visual dos receptores e transmissores)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Células da Matriz com Visual Idêntico ao Heatmap (Priority: P1)

Como analista que usa as páginas Ativos e Ecossistema, quero que as células da Matriz Receptor × Transmissor tenham o mesmo aspecto visual das células do heatmap "Intensidade de Uso das APIs", para que a experiência seja consistente entre as duas páginas e eu reconheça imediatamente o padrão de representação de intensidade.

**Why this priority**: É a mudança mais visível e abrangente; impacta todos os usuários na primeira olhada. Estabelece a base visual sobre a qual as demais melhorias se apoiam.

**Independent Test**: Abrir as duas páginas lado a lado e comparar visualmente as células — cantos, espaçamento, paleta de cores, hover, tratamento de zeros.

**Acceptance Scenarios**:

1. **Given** a matriz está carregada com dados, **When** o usuário observa as células, **Then** cada célula tem cantos arredondados e há espaçamento visível entre células adjacentes, igual ao heatmap do Ecossistema.

2. **Given** uma célula tem valor maior que zero, **When** o usuário passa o mouse sobre ela, **Then** a célula cresce ligeiramente e reduz a opacidade (mesmo efeito do heatmap), sem aplicar filtro de brilho.

3. **Given** uma célula tem valor zero, **When** o usuário observa a célula, **Then** ela exibe `—` com fundo na cor de superfície elevada (sem aplicar escala de calor), igual às células vazias do heatmap.

4. **Given** a página Ativos e a página Ecossistema estão abertas, **When** o usuário compara a cor de uma célula de alta intensidade nas duas tabelas, **Then** a paleta de calor (gradiente de azul claro a azul médio) é visualmente equivalente.

5. **Given** as células da matriz e do heatmap estão visíveis, **When** o usuário compara a tipografia dos valores, **Then** ambas usam a mesma família de fonte (não monoespaçada) com tamanho e peso equivalentes.

---

### User Story 2 — Indicadores de Cor de Marca nas Instituições (Priority: P2)

Como analista, quero que os nomes de receptores e transmissores na matriz exibam indicadores coloridos de marca — da mesma forma que o heatmap do Ecossistema identifica receptores com cores institucionais — para que eu reconheça as instituições visualmente sem precisar ler o nome completo.

**Why this priority**: Agrega identidade visual às instituições, mas é secundário ao visual geral das células. Depende de US1 para contexto visual coerente.

**Independent Test**: Carregar a matriz com dados e verificar que receptores com cor de marca definida exibem ponto ou marcador colorido ao lado do nome.

**Acceptance Scenarios**:

1. **Given** a matriz está carregada, **When** o usuário observa os labels de receptor (coluna esquerda de cada linha), **Then** cada receptor com cor de marca definida exibe um indicador visual colorido (ex: ponto ou barra lateral) idêntico ao exibido no heatmap do Ecossistema.

2. **Given** a matriz está carregada, **When** o usuário observa os cabeçalhos de transmissores (linha de topo), **Then** o estilo tipográfico dos cabeçalhos (tamanho, cor, peso) é equivalente ao dos cabeçalhos de coluna do heatmap — texto muted, mais compacto.

3. **Given** uma instituição não tem cor de marca definida, **When** a matriz renderiza seu label, **Then** o label é exibido sem indicador de cor, sem erro visual e sem erro no console.

4. **Given** a funcionalidade de ordenação interativa (feature 004) está ativa, **When** o usuário clica em um receptor para reordenar colunas, **Then** o indicador de cor de marca permanece visível e o comportamento de ordenação não é afetado.

---

### Edge Cases

- O que acontece quando `max_value` é zero? (divisão por zero na escala de calor — células devem exibir `—` sem erro)
- O que acontece no tema claro? (paleta de calor e indicadores de cor devem ser legíveis nos dois temas)
- O que acontece com nomes muito longos? (truncamento com reticências deve ser mantido)
- O que acontece quando a API de cores não retorna dados? (matriz renderiza normalmente, sem indicadores — graceful degradation)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: As células de dados da matriz DEVEM ter cantos arredondados e espaçamento entre si (gap visível), igual ao estilo das células do heatmap "Intensidade de Uso das APIs" em Ecossistema.
- **FR-002**: O efeito de hover nas células de dados DEVE usar escala e variação de opacidade, igual ao heatmap — sem filtro de brilho.
- **FR-003**: Células com valor zero DEVEM exibir o símbolo `—` com fundo de superfície elevada, sem aplicar a escala de calor.
- **FR-004**: A paleta de cores da escala de calor (gradiente de intensidade) DEVE ser visualmente equivalente à usada no heatmap do Ecossistema (gradiente de azul claro a azul médio).
- **FR-005**: A tipografia dos valores nas células (família, tamanho e peso de fonte) DEVE ser equivalente à das células do heatmap — fonte do sistema (não monoespaçada).
- **FR-006**: Os labels de receptor (coluna esquerda) DEVEM exibir um indicador de cor de marca ao lado do nome para cada instituição que tenha cor definida, usando o mesmo sistema de cores do heatmap do Ecossistema.
- **FR-007**: Os cabeçalhos de transmissores (linha de cabeçalho) DEVEM ter estilo tipográfico equivalente ao dos cabeçalhos de coluna do heatmap (texto muted, tamanho e peso de fonte equivalentes).
- **FR-008**: Quando uma instituição não possui cor de marca definida, o indicador de cor DEVE ser omitido sem causar erro visual ou de console.
- **FR-009**: Todas as alterações visuais DEVEM funcionar corretamente nos temas claro e escuro.
- **FR-010**: As funcionalidades existentes (ordenação interativa por clique, botão "↺ Redefinir", tooltip ao hover) DEVEM continuar funcionando sem alteração.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Avaliação visual lado a lado das duas páginas mostra equivalência em 100% dos elementos comparáveis: cantos arredondados, espaçamento entre células, paleta de calor, efeito de hover, tratamento de zero.
- **SC-002**: Todos os receptores com cor de marca definida exibem o indicador correto em 100% das renderizações da matriz.
- **SC-003**: Nenhum erro de `TypeError`, `ReferenceError` ou `Uncaught` ocorre no console ao carregar ou interagir com a matriz após as mudanças.
- **SC-004**: O tempo de re-renderização da matriz após troca de filtro permanece abaixo de 200ms (sem regressão de performance da feature 004).
- **SC-005**: A validação manual nos 7 cenários do quickstart da feature 004 continua passando após as mudanças visuais.

## Assumptions

- A mudança é restrita ao arquivo `dashboard/gui/active_consents.html` — nenhuma alteração de backend é necessária.
- A cor de marca de cada instituição é obtida via o endpoint ou mecanismo já existente no projeto (usado pelo heatmap do Ecossistema), sem necessidade de novo endpoint.
- Transmissores não possuem necessariamente cores institucionais individuais; se não houver cor disponível, o cabeçalho é renderizado sem indicador de cor.
- A feature 004 (ordenação interativa da matriz) já está implementada e mergeada; as mudanças visuais desta feature são aplicadas sobre ela.
- A escala de calor para intensidade zero (`value = 0`) deve sempre resultar em célula vazia (`—`) independentemente de `max_value`.

# Feature Specification: Filtro de Grupos de Instituições (Incumbentes, ITPs, Neo Banks)

**Feature Branch**: `009-filtro-grupos-instituicoes`

**Created**: 2026-09-05

**Status**: Draft

**Input**: User description: "Filtro de grupos: incumbentes, ITPs, Neo Banks — permitir filtrar receptores/transmissores por categoria no dashboard, com dados (matriz, gráficos, rankings) recalculados de acordo com a seleção. Instituições sem classificação conhecida caem em um grupo 'Outros/Não classificado'."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Focar análise em um único grupo de instituições (Priority: P1)

Como analista do ecossistema Open Finance, quero filtrar o dashboard para exibir dados de apenas um grupo de instituições (ex.: só Incumbentes, ou só Neo Banks), para entender o comportamento e a evolução desse segmento isoladamente, sem o ruído dos demais.

**Why this priority**: É o caso de uso central do pedido — sem essa capacidade básica de segmentação, a feature não entrega valor algum. Todo o resto (multi-seleção, indicação de não classificados) é incremento sobre essa base.

**Independent Test**: Selecionar o grupo "Incumbentes" no filtro e verificar que a matriz, os gráficos e os rankings do dashboard passam a exibir apenas dados de receptores/transmissores classificados como Incumbentes — os totais mudam de forma consistente com a soma dos dados apenas desse grupo.

**Acceptance Scenarios**:

1. **Given** o dashboard exibindo dados de todas as instituições, **When** o usuário seleciona o grupo "Neo Banks" no filtro de grupos, **Then** todas as visões afetadas (matriz receptor×transmissor, gráficos, rankings) passam a considerar somente instituições do grupo Neo Banks.
2. **Given** um grupo selecionado no filtro, **When** o usuário remove a seleção (limpa o filtro), **Then** o dashboard volta a exibir dados de todas as instituições, como no comportamento padrão atual.

---

### User Story 2 - Comparar múltiplos grupos simultaneamente (Priority: P2)

Como analista, quero selecionar mais de um grupo ao mesmo tempo (ex.: Incumbentes + Neo Banks), para comparar segmentos entre si sem precisar alternar o filtro repetidamente.

**Why this priority**: Aumenta o valor analítico do filtro (comparação de segmentos), mas depende da capacidade básica de filtrar por grupo (US1) já estar funcionando.

**Independent Test**: Selecionar dois grupos simultaneamente e verificar que os dados exibidos correspondem à união das instituições dos grupos selecionados (validável comparando com a soma dos dados de cada grupo filtrado individualmente).

**Acceptance Scenarios**:

1. **Given** o filtro de grupos vazio, **When** o usuário seleciona "Incumbentes" e depois adiciona "ITPs" à seleção, **Then** o dashboard exibe a união dos dados de ambos os grupos.
2. **Given** dois grupos selecionados, **When** o usuário desmarca um deles, **Then** o dashboard recalcula as visões considerando apenas o grupo remanescente.

---

### User Story 3 - Identificar instituições não classificadas (Priority: P3)

Como analista, quero que instituições ainda não categorizadas apareçam agrupadas como "Outros/Não classificado" (em vez de somem do filtro ou quebrem a visualização), para que eu perceba quando novos participantes do ecossistema ainda não foram mapeados e possa sinalizar a atualização da classificação.

**Why this priority**: É importante para a integridade dos dados e para não esconder participantes relevantes, mas não impede o uso do filtro pelos grupos já conhecidos — por isso fica em terceiro lugar.

**Independent Test**: Com uma instituição fictícia/nova sem classificação nos dados de teste, verificar que ela aparece no grupo "Outros/Não classificado" quando esse grupo é selecionado, e que o total de instituições em todos os grupos (incluindo "Outros") corresponde ao total de instituições presentes na base.

**Acceptance Scenarios**:

1. **Given** uma instituição presente nos dados mas sem grupo atribuído, **When** o usuário seleciona o grupo "Outros/Não classificado", **Then** essa instituição aparece nos resultados filtrados.
2. **Given** o filtro de grupos com todos os grupos selecionados (incluindo "Outros/Não classificado"), **When** o usuário compara com o dashboard sem nenhum filtro de grupo aplicado, **Then** os totais são idênticos (nenhuma instituição fica de fora).

---

### Edge Cases

- O que acontece quando nenhum grupo está selecionado? O dashboard deve se comportar como hoje, exibindo dados de todas as instituições (nenhum filtro de grupo é equivalente a "todos os grupos").
- O que acontece quando um grupo selecionado não possui nenhuma instituição com dados no período filtrado? As visões devem exibir estado vazio (zero/sem dados) para esse recorte, sem erro.
- O que acontece quando uma instituição nova aparece na coleta de dados e ainda não foi classificada manualmente? Ela deve cair automaticamente em "Outros/Não classificado" até ser categorizada.
- Como o filtro de grupo interage com os filtros já existentes (período, busca textual de receptor/transmissor)? Devem ser combináveis — o resultado é a interseção de todos os filtros ativos.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE classificar cada instituição (receptor e transmissor) conhecida em um dos grupos: Incumbentes, ITPs (Iniciadores de Transação de Pagamento) ou Neo Banks.
- **FR-002**: O sistema DEVE atribuir automaticamente o grupo "Outros/Não classificado" a qualquer instituição presente nos dados que não tenha classificação explícita nos três grupos acima.
- **FR-003**: O usuário DEVE poder selecionar um ou mais grupos (Incumbentes, ITPs, Neo Banks, Outros/Não classificado) como filtro no dashboard.
- **FR-004**: Quando um filtro de grupo estiver ativo, todas as visões relevantes do dashboard (matriz receptor×transmissor, gráficos temporais, rankings/totais) DEVEM recalcular seus dados considerando apenas instituições dos grupos selecionados.
- **FR-005**: Quando nenhum grupo estiver selecionado, o sistema DEVE exibir dados de todas as instituições (comportamento equivalente a "todos os grupos"), preservando o comportamento atual do dashboard.
- **FR-006**: O filtro de grupos DEVE ser combinável com os filtros já existentes (período, busca de receptor/transmissor), aplicando a interseção dos critérios.
- **FR-007**: O sistema DEVE exibir de forma visível ao usuário quais grupos estão atualmente selecionados no filtro.
- **FR-008**: O sistema DEVE permitir que a lista de instituições associadas a cada grupo seja atualizada por um mantenedor do projeto conforme novos participantes entram no ecossistema, sem exigir uma recarga completa dos dados históricos.

### Key Entities

- **Grupo de Instituição**: categoria atribuída a uma instituição (receptor ou transmissor). Valores possíveis: Incumbentes, ITPs, Neo Banks, Outros/Não classificado. Cada instituição pertence a exatamente um grupo.
- **Instituição (Receptor/Transmissor)**: entidade já existente no sistema (identificada por UUID e nome), que passa a ter um Grupo de Instituição associado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Usuários conseguem restringir a visualização do dashboard a um grupo específico de instituições em até 2 cliques/seleções.
- **SC-002**: 100% das instituições presentes nos dados coletados possuem um grupo atribuído (explícito ou "Outros/Não classificado") — nenhuma instituição fica sem categoria ou é omitida do filtro.
- **SC-003**: Ao selecionar todos os grupos simultaneamente, os totais exibidos são idênticos aos totais exibidos sem nenhum filtro de grupo aplicado (nenhuma perda de dados).
- **SC-004**: Usuários identificam em até 5 segundos, olhando a tela, quais grupos estão atualmente filtrando a visão (clareza do estado do filtro).

## Assumptions

- A classificação de cada instituição em Incumbente, ITP ou Neo Bank é definida por uma lista de referência mantida pela equipe do projeto (análogo ao padrão já existente de mapeamento de cores de marca por nome de instituição), e não depende de um campo já existente na fonte de dados original.
- Instituições cuja classificação ainda não foi definida manualmente são tratadas como "Outros/Não classificado" até serem categorizadas — isso é o comportamento padrão esperado, não um erro.
- O filtro de grupos se aplica igualmente a receptores e a transmissores (ambos os lados de uma relação podem ser filtrados pelo grupo a que pertencem).
- Este ajuste é uma extensão da experiência atual do dashboard (filtros existentes de período e busca por nome continuam funcionando como hoje) — não há remoção de funcionalidade existente.

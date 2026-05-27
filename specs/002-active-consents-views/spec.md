# Feature Specification: Visões de Consentimentos Ativos no Dashboard

**Feature Branch**: `002-active-consents-views`

**Created**: 2026-05-25

**Status**: Draft

**Input**: Quero criar novas visões no Dashboard para mostrar a evolução dos consentimentos ativos capturados. Visões de evolução no tempo por receptor e transmissor, matriz de cruzamento receptor × transmissor, rankings, variação semanal e intensidade de uso.

---

## Glossário

> Termos com significados específicos neste contexto:

- **Consentimento Ativo**: total de consentimentos vigentes em uma data para um par receptor × transmissor. Um mesmo cliente pode ter múltiplos consentimentos ativos com o mesmo par.
- **Consentimento Único**: clientes únicos (pessoa física ou jurídica) de um receptor que possuem pelo menos 1 consentimento na data. Granularidade: somente por receptor, sem breakdown por transmissor.
- **Intensidade de Uso**: razão entre consentimentos ativos totais e clientes únicos de um receptor — representa quantos consentimentos ativos, em média, cada cliente único gera naquele receptor.
- **Receptor**: instituição que recebe dados compartilhados pelo cliente (ex.: fintechs, bancos receptores).
- **Transmissor**: instituição que envia/compartilha os dados (ex.: banco onde o cliente tem conta).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Evolução Temporal de Consentimentos Ativos (Priority: P1)

Como analista do ecossistema Open Finance Brasil, quero visualizar a evolução semanal do total de consentimentos ativos por receptor ou por transmissor, para entender quem está crescendo ou perdendo consentimentos vigentes ao longo do tempo.

**Why this priority**: É a visão mais direta do valor da nova base de dados — responde "como o ecossistema de compartilhamento ativo está evoluindo?" sem depender de outras visões.

**Independent Test**: Pode ser testada de forma isolada: dado um intervalo de datas com dados coletados, o gráfico de linha mostra séries semanais por receptor (ou transmissor) com totais corretos. Entrega valor imediato mesmo sem as demais visões.

**Acceptance Scenarios**:

1. **Given** que existem dados de `active_consents` para as últimas 4 semanas, **When** o analista acessa a página e seleciona "por receptor", **Then** vê um gráfico de linhas com uma série por receptor, eixo X = semana, eixo Y = total de consentimentos ativos.
2. **Given** o mesmo conjunto de dados, **When** o analista alterna para "por transmissor", **Then** o gráfico muda para séries por transmissor, mantendo o mesmo período.
3. **Given** o analista aplica o filtro de período (ex.: últimas 8 semanas), **When** o gráfico é atualizado, **Then** apenas os dados do intervalo selecionado são exibidos.
4. **Given** o analista seleciona um receptor específico no filtro, **When** o gráfico é atualizado, **Then** apenas as séries daquele receptor (ou somente aquele receptor) são exibidas.

---

### User Story 2 — Matriz Receptor × Transmissor (Priority: P2)

Como analista, quero visualizar uma matriz de calor (heatmap) mostrando o volume de consentimentos ativos para cada combinação receptor × transmissor na semana mais recente, para identificar os pares com maior volume de compartilhamento e detectar dependências de mercado.

**Why this priority**: Revela a estrutura do mercado de forma que gráficos de linha não conseguem — mostra concentração, pares dominantes e lacunas de compartilhamento.

**Independent Test**: Pode ser testada isoladamente: dado um conjunto de dados com múltiplos receptores e transmissores, a matriz exibe células coloridas proporcionais ao total de cada par. Entrega valor mesmo sem as visões temporais.

**Acceptance Scenarios**:

1. **Given** dados de `active_consents` para a semana mais recente, **When** o analista acessa a matriz, **Then** vê uma grade com receptores nas linhas, transmissores nas colunas, e cor/intensidade proporcional ao total de consentimentos ativos.
2. **Given** a matriz renderizada, **When** o analista passa o cursor sobre uma célula, **Then** vê o nome do receptor, nome do transmissor e o total exato de consentimentos ativos.
3. **Given** a matriz, **When** o analista aplica filtro de receptor (ex.: apenas "Bradesco"), **Then** a matriz exibe somente as linhas daquele receptor.
4. **Given** um par receptor × transmissor com zero consentimentos ativos, **When** a matriz é exibida, **Then** a célula aparece em branco ou cor neutra (não oculta o par).

---

### User Story 3 — Ranking de Receptores e Transmissores (Priority: P2)

Como analista, quero ver um ranking dos principais receptores e transmissores por volume total de consentimentos ativos na semana mais recente, para identificar rapidamente quem lidera o ecossistema.

**Why this priority**: Responde "quem são os maiores players?" com uma única olhada — complementa a visão temporal e a matriz.

**Independent Test**: Pode ser testada de forma isolada com um conjunto de dados estático: top-10 receptores e top-10 transmissores por total de ativos, com barras proporcionais aos valores.

**Acceptance Scenarios**:

1. **Given** dados da semana mais recente, **When** o analista acessa o ranking, **Then** vê os top-10 receptores ordenados por total de consentimentos ativos (decrescente), com barras proporcionais.
2. **Given** o mesmo conjunto, **When** o analista alterna para "transmissores", **Then** vê os top-10 transmissores ordenados da mesma forma.
3. **Given** o analista aplica filtro de período diferente, **When** o ranking é atualizado, **Then** reflete os totais do período selecionado (última semana dentro do intervalo).

---

### User Story 4 — Variação Semanal (Δ%) (Priority: P3)

Como analista, quero ver a variação percentual de consentimentos ativos entre a semana atual e a semana anterior, por receptor e por transmissor, para detectar crescimentos relevantes ou quedas anômalas.

**Why this priority**: Agrega contexto de tendência ao ranking — sem ela, não é possível distinguir quem está crescendo de quem está estável no topo.

**Independent Test**: Pode ser testada com dados de 2 semanas: o Δ% calculado corretamente (semana N vs. semana N-1) exibido ao lado do total no ranking ou em cartões de destaque.

**Acceptance Scenarios**:

1. **Given** dados de pelo menos 2 semanas, **When** o analista acessa o ranking, **Then** vê o Δ% semana a semana ao lado do total de cada receptor/transmissor.
2. **Given** um receptor que passou de 1.000 para 1.200 ativos, **When** o Δ% é exibido, **Then** mostra `+20,0%`.
3. **Given** um receptor com dados apenas na semana mais recente (sem semana anterior), **When** o Δ% é exibido, **Then** mostra "—" ou "novo" em vez de um valor calculado.

---

### User Story 5 — Intensidade de Uso por Receptor (Priority: P3)

Como analista, quero ver a intensidade de uso por receptor — razão entre consentimentos ativos totais e clientes únicos —, para entender se um receptor tem muitos consentimentos porque tem muitos clientes ou porque cada cliente mantém muitos consentimentos vigentes.

**Why this priority**: Adiciona uma dimensão qualitativa ao volume bruto. Somente possível porque possuímos tanto `active_consents` quanto `unique_consents` na base.

**Independent Test**: Pode ser testada isoladamente: dado receptor A com 10.000 ativos e 2.000 únicos → intensidade 5,0; receptor B com 3.000 ativos e 3.000 únicos → intensidade 1,0. A visão exibe ambos corretamente ordenados.

**Acceptance Scenarios**:

1. **Given** dados de `active_consents` e `unique_consents` para a mesma semana, **When** o analista acessa a visão de intensidade, **Then** vê cada receptor com seu valor de intensidade (ativos ÷ únicos) formatado com 1 casa decimal.
2. **Given** um receptor sem dados em `unique_consents` para a semana, **When** a intensidade é calculada, **Then** o valor aparece como "—" (divisor zero não gera erro).
3. **Given** a lista ordenada por intensidade (decrescente), **When** o analista identifica outliers, **Then** os receptores com intensidade > 2,0 estão visivelmente destacados do restante.

---

### Edge Cases

- O que acontece se não houver dados de `active_consents` para o período selecionado? → Exibir mensagem informativa ("Nenhum dado disponível para o período") sem quebrar a página.
- O que acontece se apenas 1 semana de dados existir (sem semana anterior)? → Variação Δ% exibe "—" ou "N/D".
- O que acontece se `unique_consents` não tiver dados para a semana mais recente de `active_consents`? → Intensidade de uso exibe "—" para os receptores sem correspondência.
- O que acontece se a matriz tiver >50 transmissores? → A matriz deve ter scroll horizontal ou truncar transmissores menos relevantes (< 1% do total), com opção de expandir.
- O que acontece com nomes de receptores/transmissores muito longos? → Truncar com reticências e exibir nome completo no tooltip.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE exibir gráfico de evolução semanal do total de consentimentos ativos, alternável entre agrupamento por receptor e por transmissor.
- **FR-002**: O sistema DEVE permitir filtrar a evolução temporal por período (data início / data fim) usando o mesmo seletor de datas já existente no dashboard.
- **FR-003**: O sistema DEVE permitir filtrar a evolução temporal por receptor específico (ou conjunto de receptores), reduzindo as séries exibidas.
- **FR-004**: O sistema DEVE exibir uma matriz receptor × transmissor com intensidade de cor proporcional ao volume de consentimentos ativos para a semana mais recente disponível no período selecionado.
- **FR-005**: O sistema DEVE exibir tooltip na matriz com receptor, transmissor e total exato ao passar o cursor sobre uma célula.
- **FR-006**: O sistema DEVE exibir ranking dos top-10 receptores por total de consentimentos ativos (semana mais recente do período), com barras proporcionais.
- **FR-007**: O sistema DEVE exibir ranking dos top-10 transmissores por total de consentimentos ativos (semana mais recente do período), com barras proporcionais.
- **FR-008**: O sistema DEVE calcular e exibir a variação Δ% semana a semana para cada receptor e transmissor no ranking (comparando semana mais recente vs. semana imediatamente anterior).
- **FR-009**: O sistema DEVE calcular e exibir a intensidade de uso por receptor (total de consentimentos ativos ÷ total de clientes únicos), para a semana mais recente disponível.
- **FR-010**: O sistema DEVE exibir mensagem informativa quando não houver dados disponíveis para o período ou filtro selecionado, sem causar erro ou tela em branco.
- **FR-011**: O sistema DEVE exibir "—" (não disponível) quando a variação Δ% ou a intensidade de uso não puderem ser calculadas (dados insuficientes ou divisor zero).
- **FR-012**: Todas as visões DEVEM responder ao mesmo filtro de período já existente no dashboard, sem necessidade de filtros independentes por visão.

### Key Entities

- **Consentimento Ativo**: representa o total de consentimentos vigentes em uma data para um par receptor × transmissor. Atributos relevantes: receptor (nome), transmissor (nome), semana (data), total (contagem inteira).
- **Consentimento Único**: representa os clientes únicos de um receptor com pelo menos 1 consentimento na data. Atributos relevantes: receptor (nome), semana (data), total (PF + PJ combinados).
- **Intensidade de Uso**: métrica derivada por receptor — `active_consents.total ÷ unique_consents.total` para a mesma semana. Não é uma entidade armazenada, é calculada na camada de apresentação.
- **Par Receptor × Transmissor**: unidade atômica dos dados de ativos; cada combinação tem sua própria série temporal.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O analista consegue identificar os 3 principais receptores por volume de consentimentos ativos em menos de 10 segundos após abrir a página.
- **SC-002**: O analista consegue visualizar a evolução de qualquer receptor específico nos últimos 12 meses sem necessidade de exportar dados.
- **SC-003**: A página carrega todas as visões com até 52 semanas de dados em menos de 5 segundos.
- **SC-004**: A matriz receptor × transmissor exibe corretamente até 50 receptores × 100 transmissores sem erros de renderização.
- **SC-005**: 100% das visões respondem ao filtro de período sem recarregar a página.
- **SC-006**: O analista consegue identificar outliers de intensidade de uso (receptores com intensidade > 2,0) sem precisar fazer cálculos manuais.
- **SC-007**: Nenhuma das visões exibe erro ou quebra ao ser acessada com dados de apenas 1 semana disponível.

---

## Assumptions

- O dashboard já possui infraestrutura de filtro por período (data início / data fim) e por receptor — as novas visões reutilizam esses controles sem criar filtros próprios.
- Os dados de `active_consents` e `unique_consents` estão disponíveis na mesma base de dados acessada pelo dashboard, sem necessidade de sincronização adicional.
- A comparação entre `active_consents` e `unique_consents` é feita por receptor e semana — não há breakdown de `unique_consents` por transmissor.
- O período de dados disponível é semanal (granularidade de semana, conforme a coleta existente).
- As novas visões serão agrupadas em uma nova seção ou página do dashboard, sem substituir as visões existentes de consentimentos únicos e requisições de API.
- A matriz será exibida para a semana mais recente dentro do período selecionado (não acumulada).
- Top-N padrão é top-10; pode ser ajustado para top-5 ou top-20 como configuração de interface, mas 10 é o valor inicial.
- Suporte mobile está fora do escopo desta versão — o dashboard já é desktop-first.

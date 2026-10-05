# Feature Specification: Dashboard 2.0 — painel organizado por pergunta, com o atual mantido como legado

**Feature Branch**: `011-dashboard-v2`

**Created**: 2026-10-05

**Status**: Draft

**Input**: User description: "Dashboard 2.0 — nova versão do painel Open Finance Brasil organizada por pergunta analítica, mantendo o painel atual (Ecossistema, Perfil Receptores, Ativos) funcionando como legado acessível, sem remoção." Design aprovado no canvas https://claude.ai/artifact/LZivcKNMg2z43daC2arfWv (página "Versão final — para aprovação"), resultado de entrevista e revisões com o responsável do produto em 2026-10-05.

## Clarifications

### Session 2026-10-05

- Q: Qual versão fica no endereço principal? → A: O legado continua no endereço principal e nos endereços atuais; o 2.0 ganha endereço próprio até a virada, feita depois, num passo separado.
- Q: Qual é a primeira entrega? → A: "Quem lidera?", já com a estrutura completa do 2.0 (abas, barra de filtros, cabeçalho, acesso ao legado).

### Session 2026-10-05 — revisão da aba "Como opera uma instituição?"

Revisão bloco a bloco com o responsável do produto, depois de ver a aba com dados reais.

- Q: Filtros (instituição, comparar com, período, CSV)? → A: Mantidos. "Média do grupo" é a soma do grupo (média ponderada pelo tamanho).
- Q: Cabeçalho? → A: A frase de posições mostra sempre as 4 métricas (PF, PJ, ativos, API); antes cortava em 3 posições diferentes.
- Q: Cards de indicadores? → A: Ganham o ritmo por dia das últimas 4 semanas, com seta ↑↓ contra as 4 anteriores, como na aba 1.
- Q: Gráfico de evolução? → A: Seletor PF · PJ · PF + PJ · Ativos · API · API/(PF + PJ), padrão PF + PJ. API/(PF + PJ) = chamadas por consentimento/mês (abaixo); sem participação; referência sempre desenhada (mesma escala) e título de intensidade ("Usa mais/menos dados por cliente"). Nas contagens, a referência só é desenhada contra outra instituição.
- Q: Mix de API? → A: Seletor % · API total · API/(PF + PJ), padrão API/(PF + PJ), normalizado pelas últimas 4 semanas para 30 dias: chamadas das 4 semanas ÷ 28 × 30; por consentimento = esse total ÷ média de consentimentos únicos (PF + PJ) das mesmas 4 semanas. A mesma conta vale para o card de API.
- Q: Chamadas por grupo de API? → A: Seguem a unidade do seletor do mix; minilinha mensal e crescimento como antes (em %, a variação é em pontos percentuais).
- Q: Transmissores? → A: Linha "Outros (N transmissores)" fecha os 100%; coluna de crescimento no período por transmissor.
- Q: Taxa de erro? → A: Valor atual e lista por transmissor sobre as últimas 4 semanas; série com todos os meses do período (mês = soma das semanas do mês).
- Q: Alertas da instituição? → A: Como na aba 3: eventos por mês com oscilação agrupada e reincidência, "em observação" da instituição e link que abre "O que mudou?" filtrado por ela.

## Contexto de uso

Os dados são semanais e a base é atualizada uma vez por mês. O responsável do produto abre o painel 1 a 2 vezes por mês, analisa o que mudou desde a última atualização e leva prints e dados exportados para slides. O painel atual é organizado por fonte de dados (Ecossistema, Perfil Receptores, Ativos); o 2.0 é organizado pelas perguntas que ele responde.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver quem lidera e quanto (Priority: P1)

Como analista, ao abrir o painel quero ver de imediato quem lidera o ecossistema na última semana, quanto cada instituição representa e em que ritmo está crescendo, nas três métricas (consentimentos únicos, consentimentos ativos e chamadas de API), sempre com o Bradesco à vista e sem as instituições que eu escolhi deixar de fora.

**Why this priority**: É a aba de abertura e a pergunta mais frequente. Sozinha, já entrega o novo painel com valor: estrutura de abas, barra de filtros, cabeçalho com a data dos dados e o legado acessível.

**Independent Test**: Abrir o painel 2.0, conferir o Top 15 de cada métrica contra a base para a semana mais recente (participação, total, ritmo e crescimento), fixar e excluir instituições e verificar que as escolhas persistem ao recarregar e ao trocar de métrica.

**Acceptance Scenarios**:

1. **Given** a base com dados até a semana mais recente, **When** o usuário abre o painel 2.0, **Then** a aba "Quem lidera?" aparece com a métrica "Consentimentos únicos", rankings Top 15 de pessoa física e de pessoa jurídica lado a lado, totais do ecossistema com a fatia de cada grupo e a data dos dados no cabeçalho.
2. **Given** a aba "Quem lidera?", **When** o usuário troca a métrica para "Consentimentos ativos" ou "Chamadas de API", **Then** aparece um único ranking Top 15 em largura total, com as mesmas regras de fixar, excluir e ordenar.
3. **Given** uma instituição em "Sempre mostrar" que está fora do Top 15, **When** o ranking é exibido, **Then** ela aparece abaixo de uma linha tracejada com sua posição real no ecossistema e destaque visual.
4. **Given** uma instituição em "Excluir do ranking", **When** o ranking é exibido, **Then** ela não aparece, a instituição seguinte completa as 15 linhas, as posições exibidas continuam sendo as do ecossistema e o rodapé informa a exclusão.
5. **Given** o primeiro acesso de um navegador, **When** o ranking é exibido, **Then** o Bradesco já está em "Sempre mostrar".
6. **Given** a métrica "Chamadas de API", **When** o usuário escolhe "Escala: por consentimento/mês" ou "Status: Erros", **Then** a ordem, as barras e as colunas passam a refletir a escolha; esses controles não aparecem nas outras métricas.
7. **Given** o painel 2.0 aberto, **When** o usuário escolhe o acesso ao painel legado, **Then** as três abas atuais abrem e funcionam como antes.

---

### User Story 2 - Saber o que mudou desde a última atualização (Priority: P2)

Como analista, a cada atualização mensal quero ver numa só lista tudo o que mudou de relevante no mês — quedas, altas, oscilações e novos entrantes —, com o detalhe de cada alerta, para saber o que investigar sem consultar semana por semana.

**Why this priority**: É o motivo da visita mensal. Reaproveita os alertas já calculados (feature 010), mudando a forma de apresentar e ajustando uma regra.

**Independent Test**: Selecionar agosto/2026 e conferir que a lista mostra 12 alertas em 6 instituições, com o Banco do Nordeste como uma única oscilação, o Banco Safra marcado como "2º mês seguido" e o Santander Investimentos em observação.

**Acceptance Scenarios**:

1. **Given** alertas calculados para os últimos 12 meses, **When** o usuário abre "O que mudou?", **Then** vê uma barra com o número de alertas por mês (por tipo) e a lista do mês mais recente com dados, uma linha por instituição, ordenada pela maior variação.
2. **Given** uma instituição com queda em uma semana e alta na semana seguinte na mesma métrica de consentimentos, **When** a lista é exibida, **Then** os dois alertas aparecem como um único evento "Oscilação", com as duas variações.
3. **Given** uma instituição com alertas no mês selecionado e no mês anterior, **When** a lista é exibida, **Then** ela recebe a marca "2º mês seguido" (ou o número de meses consecutivos) e o resumo do mês anterior.
4. **Given** uma condição de alerta de API vista na semana mais recente que ainda depende de confirmação, **When** a aba é exibida, **Then** ela aparece na lateral "Em observação", com valores antes → depois e a semana em que será confirmada ou descartada.
5. **Given** uma instituição com menos de 30.000 consentimentos únicos na semana-base, **When** seus consentimentos ativos variam além dos limites, **Then** nenhum alerta de consentimentos ativos é gerado para ela.
6. **Given** a aba "Quem lidera?", **When** o usuário rola até o fim, **Then** vê o resumo do último ciclo e um atalho para "O que mudou?".

---

### User Story 3 - Levar os resultados para slides (Priority: P2)

Como analista, quero exportar qualquer bloco do painel como imagem pronta para slide e como dados, para montar a apresentação mensal sem recortar telas nem refazer tabelas.

**Why this priority**: É o destino final da análise. Vale para todas as abas, então entra cedo, junto com a primeira.

**Independent Test**: Em qualquer bloco, exportar a imagem e o CSV e verificar que a imagem tem proporção 16:9, título, métrica, data dos dados, filtro ativo e fonte, e que o CSV tem as mesmas linhas e números do bloco.

**Acceptance Scenarios**:

1. **Given** um bloco visível, **When** o usuário pede a imagem, **Then** recebe uma imagem 16:9 com o título do bloco, a métrica, a data dos dados, o filtro ativo e a fonte.
2. **Given** um bloco visível, **When** o usuário pede os dados, **Then** recebe um arquivo CSV com as linhas e colunas exibidas (incluindo as instituições fixadas e sem as excluídas).
3. **Given** um filtro ativo (ex.: só ITPs), **When** o bloco é exibido ou exportado, **Then** o título indica o filtro ("… · só ITPs").

---

### User Story 4 - Entender como opera uma instituição (Priority: P3)

Como analista, quero abrir uma instituição e ver, comparado ao ecossistema, quanto ela representa, para que usa os dados, de onde vêm os consentimentos e quão confiável é o seu uso de API, para preparar uma análise individual.

**Why this priority**: Pergunta de aprofundamento, feita depois das duas primeiras. Substitui o Perfil Receptores no 2.0.

**Independent Test**: Abrir o Nubank e conferir contra a base: únicos PF 22,04 mi (15,1%), PJ 265,0 mil, ativos 37,68 mi, 4,51 bi chamadas na semana e 866 chamadas por consentimento/mês contra 443 do ecossistema, taxa de erro 2,30% contra 4,72%.

**Acceptance Scenarios**:

1. **Given** qualquer ranking ou alerta, **When** o usuário clica no nome de uma instituição, **Then** abre "Como opera uma instituição?" com ela selecionada.
2. **Given** uma instituição selecionada, **When** o usuário escolhe "Comparar com" ecossistema, média do grupo ou outra instituição, **Then** os indicadores comparativos passam a usar a referência escolhida.
3. **Given** uma instituição selecionada, **When** a aba é exibida, **Then** mostra indicadores (únicos PF e PJ, ativos, chamadas de API e por consentimento/mês), evolução com participação, mix de API por grupo, chamadas por grupo com tendência de 12 meses, transmissores de origem dos consentimentos ativos, taxa de erro ao longo do tempo e por transmissor e os alertas da instituição.
4. **Given** uma instituição sem alertas nos últimos 12 meses, **When** a aba é exibida, **Then** o bloco de alertas diz isso e informa o último alerta existente, se houver.

---

### User Story 5 - Acompanhar como o ecossistema evolui (Priority: P3)

Como analista, quero ver quem ganha e quem perde espaço ao longo do período e se o ritmo está acelerando ou desacelerando, para contar a tendência e não só o retrato.

**Why this priority**: Complementa o retrato da aba 1 com tendência. Substitui os gráficos de aceleração e momentum do painel atual.

**Independent Test**: Para ago/25–ago/26 em consentimentos únicos PF, conferir: ecossistema +115%, maior ganho Shopee +5,5 pp (estreou nov/25), maior perda Nubank −6,8 pp, Belvo "acelerando" (+12% → +22%).

**Acceptance Scenarios**:

1. **Given** o período selecionado, **When** o usuário abre "Como evolui?", **Then** vê no topo o crescimento do ecossistema, quem mais ganhou e quem mais perdeu participação (em pontos percentuais).
2. **Given** o gráfico de evolução, **When** exibido, **Then** mostra as 5 maiores instituições por padrão (até 8, escolhidas pelo usuário), na cor do grupo, com traço diferente para instituições do mesmo grupo e valor e crescimento no fim de cada linha.
3. **Given** uma semana sem coleta para uma instituição, **When** a visão semanal é exibida, **Then** a linha é interrompida naquela semana e nunca cai a zero.
4. **Given** a aba aberta, **When** exibida, **Then** mostra a participação por grupo mês a mês, os ganhos e perdas de participação e o ritmo trimestral (acelerando, estável ou desacelerando).
5. **Given** a métrica "Consentimentos ativos", **When** o usuário escolhe "Evolução por transmissor", **Then** as linhas passam a representar transmissores.

---

### Edge Cases

- **Mês sem alertas**: a aba "O que mudou?" diz que não houve alertas no mês e mantém a barra de meses para navegar; não mostra lista vazia sem explicação.
- **Semana mais recente com coleta incompleta**: os rankings usam a última semana com dados; a data no cabeçalho reflete essa semana.
- **Instituição nova no período**: o crescimento mostra "estreou mmm/aa" em vez de percentual; base anterior inexistente nunca gera "+∞%".
- **Base muito pequena há 12 meses**: crescimento acima de +300% aparece como multiplicador (ex.: ×100 para a Klavi PJ, que partiu de ~300); sem chamadas há 12 meses aparece "sem base".
- **Ritmo negativo**: o ritmo aparece com sinal negativo e destaque (ex.: RecargaPay PJ −108/dia).
- **Todas as instituições fixadas já no Top 15**: nenhuma linha tracejada é exibida.
- **Instituição fixada e excluída ao mesmo tempo**: a última escolha prevalece; a instituição sai de uma lista ao entrar na outra.
- **Navegador sem armazenamento local**: o painel funciona com os padrões (Bradesco fixado, nenhuma exclusão) e não quebra.
- **Instituição renomeada na base**: aparece com o nome mais recente, sem duplicar.
- **Filtro de grupo que esconde uma instituição fixada**: a fixada continua visível, pois "Sempre mostrar" vale acima do filtro de grupo.
- **Tabela de alertas ainda não calculada**: "O que mudou?" informa que os alertas ainda não foram gerados, sem erro.

## Requirements *(mandatory)*

### Functional Requirements

**Estrutura, navegação e legado**

- **FR-001**: O sistema MUST oferecer o painel 2.0 com quatro abas, nesta ordem: "Quem lidera?", "Como evolui?", "O que mudou?", "Como opera uma instituição?". A abertura é "Quem lidera?".
- **FR-002**: O sistema MUST manter o painel atual (Ecossistema, Perfil Receptores, Ativos) disponível e funcionando como hoje, acessível a partir do 2.0, e o 2.0 acessível a partir do legado. O legado continua nos endereços atuais e o 2.0 ganha endereço próprio (ex.: `/v2`) até a virada, que é um passo separado, fora desta entrega.
- **FR-003**: O cabeçalho MUST mostrar a data da última semana com dados e a data da última atualização da base em todas as abas.
- **FR-004**: O painel 2.0 MUST usar tema claro por padrão, com opção de tema escuro.
- **FR-005**: Os filtros MUST ficar numa barra no topo que mostra só os controles que valem para a aba aberta; não há barra lateral nem botão "Recarregar dados".
- **FR-006**: Período, grupos de instituição, métrica e instituições escolhidas MUST ser mantidos ao trocar de aba.
- **FR-007**: Mudar qualquer filtro MUST atualizar a aba sem botão de aplicar.
- **FR-008**: A cor que identifica uma instituição MUST ser a cor do seu grupo (Neobancos, ITPs, Incumbentes, Outros), a mesma classificação usada no filtro de grupos atual.
- **FR-009**: Todo valor de instituição exibido em ranking MUST vir acompanhado da participação no total do ecossistema.
- **FR-010**: Clicar no nome de uma instituição em qualquer ranking ou alerta MUST abrir "Como opera uma instituição?" com ela selecionada.

**Exportação**

- **FR-011**: Cada bloco MUST oferecer exportação dos dados exibidos (CSV) e de imagem 16:9 pronta para slide.
- **FR-012**: A imagem exportada MUST conter título do bloco, métrica, data dos dados, filtro ativo e fonte ("dashboard Open Finance Brasil").
- **FR-013**: O título de cada bloco MUST indicar o filtro ativo quando houver (ex.: "… · só ITPs", "… · sem Shopee").

**Aba "Quem lidera?"**

- **FR-014**: A aba MUST oferecer as métricas "Consentimentos únicos" (padrão), "Consentimentos ativos" e "Chamadas de API", sempre com o retrato da semana mais recente.
- **FR-015**: Para consentimentos únicos, MUST exibir rankings Top 15 de pessoa física e de pessoa jurídica lado a lado; para ativos e API, um único ranking Top 15 em largura total.
- **FR-016**: Cada linha MUST mostrar posição no ecossistema, instituição (com cor do grupo), participação, total, ritmo por dia e crescimento no período, além de um menu com "Sempre mostrar", "Excluir do ranking", "Ver na evolução" e "Abrir perfil".
- **FR-017**: O ritmo por dia de consentimentos MUST ser (valor da semana mais recente − valor de 4 semanas antes) ÷ 28, acompanhado do equivalente em % ao dia; para API, a média de chamadas por dia nas últimas 4 semanas. Uma seta ↑ ou ↓ MUST aparecer quando o ritmo difere mais de 10% do das 4 semanas anteriores; caso contrário, →.
- **FR-018**: O crescimento MUST usar o período escolhido (padrão: últimos 12 meses); para API, compara médias de 4 semanas. Instituições que estrearam dentro do período mostram "estreou mmm/aa"; crescimento acima de +300% aparece como multiplicador (×N); ausência de base aparece como "sem base".
- **FR-019**: Os totais do ecossistema MUST mostrar o total, a fatia de cada grupo (% e valor) e o ritmo por dia com a comparação com as 4 semanas anteriores.
- **FR-020**: Usuários MUST poder incluir instituições em "Sempre mostrar" e em "Excluir do ranking". Fixadas fora do Top 15 aparecem abaixo de linha tracejada com a posição real; excluídas saem e a seguinte completa 15; posições e participação continuam calculadas sobre o ecossistema inteiro.
- **FR-021**: No primeiro acesso, o Bradesco MUST estar em "Sempre mostrar". As escolhas de fixar e excluir MUST ser salvas no navegador e valer para todas as métricas.
- **FR-022**: Usuários MUST poder ordenar o ranking por total, ritmo ou crescimento; na métrica API, também por chamadas por consentimento.
- **FR-023**: Na métrica API, a barra MUST mostrar "Escala" (Total, padrão; Por consentimento/mês) e "Status" (Sucesso, padrão; Erros; Todas). Chamadas por consentimento/mês = chamadas das últimas 4 semanas normalizadas para 30 dias ÷ média de consentimentos únicos (PF + PJ) das mesmas semanas — a mesma regra da aba 4 (revisão de 2026-10-05); no ecossistema e no grupo, só entram instituições com chamadas. Com "Erros", a coluna por consentimento dá lugar à taxa de erro.
- **FR-024**: Na métrica API, MUST haver os indicadores: chamadas na semana, ritmo por dia, chamadas por consentimento/mês do ecossistema e concentração nas 3 maiores.
- **FR-025**: A aba MUST terminar com o resumo do último ciclo de alertas e um atalho para "O que mudou?".

**Aba "O que mudou?"**

- **FR-026**: A aba MUST mostrar o número de alertas por mês nos últimos 12 meses, por tipo, permitindo escolher o mês; abre no mês mais recente com dados.
- **FR-027**: Para o mês escolhido, MUST listar uma linha por instituição, ordenada pela maior variação, com cada alerta detalhado: semana, métrica ou grupo de API, valor antes → depois e variação.
- **FR-028**: Uma queda seguida de alta (ou alta seguida de queda) na mesma métrica de consentimentos da mesma instituição em semanas consecutivas MUST ser apresentada como um único evento "Oscilação".
- **FR-029**: Uma instituição com alertas em meses consecutivos MUST ser marcada com o número de meses seguidos ("2º mês seguido") e o resumo dos alertas do mês anterior.
- **FR-030**: O sistema MUST identificar e exibir como "Em observação" as condições de alerta de API vistas na semana mais recente que ainda aguardam a semana de confirmação.
- **FR-031**: A aba MUST oferecer filtros por tipo (quedas, altas, oscilações, novos entrantes), sinal (consentimentos, uso de API), instituição e grupo, e uma lateral com "Em observação", alertas por grupo e as regras de cálculo em linguagem simples.
- **FR-032**: O piso de relevância de 30.000 MUST ser medido sempre em consentimentos únicos da semana-base, inclusive para alertas de consentimentos ativos.

**Aba "Como evolui?"**

- **FR-033**: A aba MUST abrir com três respostas: crescimento do ecossistema no período, quem mais ganhou e quem mais perdeu participação (em pontos percentuais).
- **FR-034**: O gráfico de evolução MUST mostrar as 5 maiores instituições por padrão, permitindo trocar ou adicionar até 8; usa a cor do grupo e traço diferente dentro do mesmo grupo; mostra valor e crescimento no fim de cada linha; alterna entre valores e participação %.
- **FR-035**: A visão MUST ser mensal por padrão (última semana de cada mês), com opção semanal; semana sem coleta interrompe a linha, nunca a leva a zero.
- **FR-036**: A aba MUST mostrar participação por grupo mês a mês, ganhos e perdas de participação por instituição no período e o ritmo trimestral (crescimento dos últimos 3 meses contra os 3 anteriores; "estável" quando a diferença é de até 3 pontos).
- **FR-037**: Na métrica "Consentimentos ativos", MUST permitir "Evolução por receptor" ou "por transmissor".

**Aba "Como opera uma instituição?"**

- **FR-038**: A instituição MUST ser escolhida por busca ou por clique em ranking/alerta; "Comparar com" oferece ecossistema (padrão), média do grupo ou outra instituição.
- **FR-039**: A aba MUST mostrar, com as regras da revisão de 2026-10-05 (Clarifications): posições nas 4 métricas; cards de únicos PF e PJ, ativos e chamadas de API com participação, posição, ritmo por dia, crescimento e referência (API com chamadas por consentimento/mês sobre 4 semanas normalizadas para 30 dias); evolução com seletor de 6 métricas (padrão PF + PJ); mix de API com seletor de unidade (padrão por consentimento); chamadas por grupo de API na unidade do mix; transmissores com "Outros" e crescimento; taxa de erro (500) sobre 4 semanas e mês a mês, também por transmissor; e alertas agrupados como na aba 3, com "em observação".

### Key Entities

- **Instituição (receptor)**: participante que recebe dados; identificada de forma estável, exibida pelo nome mais recente, pertencente a um grupo (Neobancos, ITPs, Incumbentes, Outros).
- **Transmissor**: instituição de onde vêm os dados; usado nos consentimentos ativos e na taxa de erro.
- **Métrica semanal**: consentimentos únicos (PF, PJ, total), consentimentos ativos e chamadas de API (por grupo de API e por status) de uma instituição numa semana.
- **Alerta**: evento detectado (novo entrante, alta, queda) para uma instituição, semana e métrica, com valores antes e depois; agrupável em oscilação e reincidência para exibição.
- **Condição em observação**: condição de alerta de API vista numa semana, aguardando a semana de confirmação.
- **Preferências do ranking**: listas de instituições fixadas e excluídas e a ordenação escolhida, guardadas no navegador do usuário.
- **Filtros compartilhados**: período, grupos, métrica e instituições selecionadas, mantidos entre as abas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em até 10 segundos após abrir o painel 2.0, o usuário identifica as 3 maiores instituições, a posição do Bradesco e o ritmo de crescimento do ecossistema sem trocar de aba nem mexer em filtros.
- **SC-002**: O usuário obtém uma imagem pronta para slide de qualquer bloco em no máximo 2 cliques, sem recorte manual.
- **SC-003**: 100% dos números conferidos numa amostra (Top 15 das três métricas, totais e alertas de agosto/2026) batem com a base para os mesmos filtros.
- **SC-004**: A revisão mensal (ver o que mudou, conferir líderes e exportar os blocos para a apresentação) é concluída em até 20 minutos.
- **SC-005**: O painel legado continua 100% funcional: todas as verificações existentes passam e as três abas atuais abrem com os mesmos resultados de antes.
- **SC-006**: Cada aba do 2.0 mostra seus dados em até 3 segundos depois da primeira carga da página, para o período padrão.
- **SC-007**: Nenhuma semana sem coleta aparece como queda a zero, e nenhum crescimento aparece como percentual sobre base inexistente.

## Assumptions

- O 2.0 reaproveita a base atual e os alertas da feature 010; as novidades de dados são o ritmo por dia, a taxa de erro por instituição/transmissor, as condições "em observação" e a regra do piso em únicos.
- A mudança do piso (FR-032) altera também os alertas mostrados no card "O que mudou" do painel legado, que lê os mesmos alertas; isso é desejado.
- O mix de API por grupo de dados desconsidera o grupo Resource; totais, rankings e chamadas por consentimento incluem todos os grupos, como hoje.
- A taxa de erro considera chamadas com status de sucesso e de erro, exceto as do próprio fluxo de consentimento.
- As preferências de ranking ficam no navegador de cada usuário; não há conta de usuário nem sincronização entre dispositivos.
- O painel continua de leitura: nada no 2.0 grava na base.
- A Constituição será emendada (Princípio VI) para o novo contrato visual antes da implementação, mantendo o contrato atual válido para as páginas do legado.
- O uso em celular não é foco; a barra de filtros quebra em linhas em telas menores e a página continua utilizável a partir de 1280 px de largura, como hoje.
- Ordem de entrega segue as prioridades: P1 (Quem lidera? com a estrutura do 2.0), P2 (O que mudou? e exportação), P3 (Instituição e Evolução). Abas ainda não entregues aparecem no 2.0 com aviso e atalho para a página equivalente do legado.

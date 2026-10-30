# Feature Specification: Período "Desde o começo do ano", API por consentimento em "Como evolui?" e visão por endpoint na instituição

**Feature Branch**: `012-periodo-ano-api-endpoint`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "Quero incluir o filtro "Desde o começo do ano" para o período em "Como evolui?". Quero ter a opção de ver Chamadas de API por consentimento único (PF + PJ) em "Como evolui?". Em "Como opera uma instituição?", junto com o "Para que usa os dados", quero incluir uma forma de ver por endpoint, além da visão por API que já temos."

## Clarifications

### Session 2026-10-29

- Q: Onde vale o período "Desde o começo do ano"? → A: Entra no filtro de período compartilhado e fica disponível em todas as abas que usam o filtro, incluindo "Quem lidera?".
- Q: O que acontece com as visões de participação na escala "por consentimento/mês"? → A: Os blocos de participação (participação %, participação por grupo mês a mês, ganhos e perdas de participação) ficam desativados, com explicação; permanecem o gráfico de linhas, os cartões de crescimento e o ritmo trimestral, calculados sobre o valor por consentimento.
- Q: Quais endpoints a visão "Por endpoint" lista? → A: Todos os endpoints do catálogo da API selecionada, inclusive os que a instituição não usou na janela, que aparecem ao final com valor zero.
- Q: Qual escala abre por padrão para "Chamadas de API" em "Como evolui?" → A: "por consentimento/mês", como na aba da instituição; o volume (4 semanas normalizadas para 30 dias) passa a ser a opção a escolher.

## Contexto de uso

O Dashboard 2.0 já responde às perguntas "Quem lidera?", "Como evolui?", "O que mudou?" e "Como opera uma instituição?". O responsável do produto abre o painel 1 a 2 vezes por mês, depois da atualização da base, e leva prints e dados exportados para slides. Três lacunas aparecem nessa rotina:

1. Os períodos disponíveis são sempre janelas móveis (3, 6 e 12 meses) ou o histórico inteiro. Para contar "como o ano está indo" falta um recorte que comece em janeiro.
2. Em "Como evolui?", as chamadas de API só podem ser vistas em volume absoluto. Esse volume cresce junto com a base de consentimentos e não diz se o uso por cliente está aumentando. A aba "Quem lidera?" e a aba da instituição já oferecem a escala "por consentimento/mês"; "Como evolui?" não.
3. Em "Como opera uma instituição?", o bloco "Para que usa os dados" mostra o uso de API somente por grupo de API (Conta, Cartão, Crédito etc.). Não dá para escolher uma API e ver quais endpoints dentro dela respondem pelo uso.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver o ano até agora (Priority: P1)

Como analista, quero escolher o período "Desde o começo do ano" para ver a evolução de 1º de janeiro até a semana mais recente com dados, para contar o que aconteceu no ano sem recortes móveis que atravessam o ano anterior.

**Why this priority**: É o menor recorte e o mais pedido para apresentações de acompanhamento anual. Entrega valor sozinho: basta o novo período funcionar com as métricas que já existem.

**Independent Test**: Com a base atual (dados até 25/09/2026), escolher "Desde o começo do ano" em "Como evolui?" e conferir que o início do período é a primeira semana de 2026, que o fim é 25/09/2026 e que o crescimento do ecossistema, os ganhos e perdas de participação e os gráficos usam exatamente esse intervalo.

**Acceptance Scenarios**:

1. **Given** a base com dados até a semana de 25/09/2026, **When** o usuário escolhe "Desde o começo do ano" no filtro de período, **Then** o painel considera o intervalo de 1º/01/2026 até 25/09/2026 e os rótulos dizem "desde o começo do ano" (e não "12 meses" ou "no período").
2. **Given** o período "Desde o começo do ano" escolhido em "Como evolui?", **When** o usuário troca de aba, **Then** a escolha de período é mantida, como acontece com os demais períodos.
3. **Given** uma instituição que estreou depois de 1º de janeiro, **When** o período "Desde o começo do ano" é exibido, **Then** o crescimento mostra "estreou mmm/aa" em vez de percentual, como nos outros períodos.
4. **Given** a base cuja semana mais recente cai nos primeiros dias do ano (por exemplo, a segunda sexta-feira de janeiro), **When** o usuário escolhe "Desde o começo do ano", **Then** o painel mostra os poucos pontos disponíveis e avisa que há pouca história no período, sem erro nem gráficos vazios sem explicação.

---

### User Story 2 - Acompanhar o uso de API por consentimento ao longo do tempo (Priority: P2)

Como analista, quero ver em "Como evolui?" as chamadas de API por consentimento único (PF + PJ), para saber se cada instituição está usando mais ou menos a API por cliente, separando esse efeito do crescimento da base de consentimentos.

**Why this priority**: Responde à pergunta de intensidade de uso que o volume absoluto esconde. Depende só de regras já existentes no painel (a mesma conta usada em "Quem lidera?" e na aba da instituição).

**Independent Test**: Em "Como evolui?", escolher a métrica "Chamadas de API" com a escala "por consentimento/mês" e conferir, para uma instituição e um mês, que o valor é igual ao exibido em "Quem lidera?" para a mesma instituição e a mesma semana.

**Acceptance Scenarios**:

1. **Given** o usuário abre "Como evolui?" com a métrica "Chamadas de API", **When** a aba é exibida, **Then** a escala "por consentimento/mês" vem selecionada e as linhas, os valores no fim de cada linha e o crescimento do ecossistema mostram chamadas por consentimento único (PF + PJ) por mês; o usuário pode trocar para o volume (4 semanas normalizadas para 30 dias).
2. **Given** a escala "por consentimento/mês", **When** o gráfico é exibido, **Then** o ecossistema é desenhado como linha de referência e conta apenas instituições com chamadas naquela semana.
3. **Given** a escala "por consentimento/mês", **When** o usuário olha as visões que dependem de participação (participação %, participação por grupo, ganhos e perdas de participação), **Then** elas aparecem desativadas com a explicação "participação não se aplica a chamadas por consentimento", enquanto o gráfico de linhas, os cartões de crescimento e o ritmo trimestral continuam disponíveis sobre o valor por consentimento.
4. **Given** uma instituição sem consentimentos únicos em uma semana, **When** a escala "por consentimento/mês" é exibida, **Then** o ponto fica em branco (lacuna) e nunca vira zero nem divisão por zero.
5. **Given** a escala escolhida em "Como evolui?", **When** o usuário exporta a imagem ou o CSV, **Then** o título, o subtítulo e as colunas indicam a escala usada.

---

### User Story 3 - Ver para que a instituição usa os dados por endpoint (Priority: P3)

Como analista, quero alternar o bloco "Para que usa os dados" entre a visão por grupo de API (atual) e uma visão por endpoint, escolhendo uma API e vendo todos os endpoints dela, para entender quais funcionalidades específicas respondem pelo uso da instituição naquela API.

**Why this priority**: Aprofunda uma análise que já existe, mas exige o detalhe por endpoint disponível para a aba. É a mais trabalhosa e a que menos bloqueia as demais.

**Independent Test**: Abrir uma instituição, alternar para "Por endpoint", escolher uma API e conferir que a soma dos endpoints dela (mais a parcela sem endpoint identificado) é igual ao total dessa API na visão por grupo para a mesma janela de 4 semanas.

**Acceptance Scenarios**:

1. **Given** uma instituição selecionada, **When** o usuário abre "Para que usa os dados", **Then** a visão por grupo de API continua sendo a padrão e há um seletor para alternar para "Por endpoint".
2. **Given** a visão "Por endpoint", **When** exibida, **Then** há um seletor de API (as APIs que a instituição usa, agrupadas por grupo de API e com a cor do grupo) e a lista mostra todos os endpoints da API selecionada, com o nome do endpoint, o volume e a participação dentro da API, na unidade escolhida no seletor de unidade já existente (% · API total · API/(PF + PJ)).
3. **Given** uma API com muitos endpoints, **When** a visão por endpoint é exibida, **Then** todos os endpoints aparecem, sem corte em "Top N" nem linha "Outros", ordenados do maior para o menor volume da instituição; os endpoints que a instituição não usou naquela janela aparecem ao final com valor zero.
4. **Given** a comparação escolhida na aba (ecossistema, média do grupo ou outra instituição), **When** a visão por endpoint é exibida, **Then** cada endpoint mostra também o valor do comparado para a mesma API, como a visão por grupo já faz.
5. **Given** chamadas da API selecionada que a base não atribui a nenhum endpoint, **When** a visão por endpoint é exibida, **Then** essa parcela aparece como "Sem endpoint identificado", de modo que o total da lista seja igual ao total dessa API na visão por grupo.
6. **Given** a visão "Por endpoint" com uma API selecionada, **When** o usuário troca a instituição ou a comparação, **Then** a visão e a API são mantidas se a nova instituição usa essa API; caso contrário, a API com maior volume da nova instituição é selecionada. Ao trocar de aba e voltar, o padrão volta a ser por grupo.
7. **Given** a visão "Por endpoint", **When** o usuário exporta a imagem ou o CSV da aba, **Then** o bloco exportado reflete a API e a unidade selecionadas.

---

### Edge Cases

- **Início do ano com poucas semanas**: se a semana mais recente com dados está em janeiro, "Desde o começo do ano" tem um ou dois pontos; o painel avisa e não calcula tendência trimestral.
- **Virada do ano sem coleta nova**: o ano de referência é o da semana mais recente com dados, não o da data de hoje; com a base ainda em dezembro, o período cobre o ano anterior até dezembro.
- **Semana sem coleta**: continua sendo lacuna, nunca zero, em qualquer escala e período.
- **Instituição sem chamadas de API nas últimas 4 semanas**: a visão por endpoint mostra a mesma mensagem de "sem chamadas" da visão por grupo.
- **Endpoint com nome repetido em APIs diferentes**: como a lista é de uma API por vez, não há ambiguidade; o nome da API selecionada aparece no título do bloco.
- **Grupo Resource**: continua fora do mix por grupo; as APIs desse grupo não são oferecidas no seletor de API da visão por endpoint, e a nota de rodapé informa isso.
- **Escala por consentimento com consentimentos zerados**: ponto em branco, sem erro.

## Requirements *(mandatory)*

### Functional Requirements

**Período "Desde o começo do ano"**

- **FR-001**: O filtro de período MUST oferecer a opção "Desde o começo do ano", que vai de 1º de janeiro do ano da semana mais recente com dados até essa semana.
- **FR-002**: A opção MUST estar disponível na lista única do filtro de período, em todas as abas que o usam (incluindo "Quem lidera?"), e ser mantida ao trocar de aba, como os demais períodos.
- **FR-003**: Todo texto que cita o período (cartões, títulos, subtítulos, rodapés, imagem e CSV exportados) MUST dizer "desde o começo do ano" ou equivalente quando essa opção estiver ativa.
- **FR-004**: O crescimento e a participação MUST usar a primeira semana com dados do ano como base; instituições que estrearam no período mostram "estreou mmm/aa", e base ausente mostra "sem base", como nas outras opções.
- **FR-005**: Quando o período tiver menos pontos do que uma visão exige (por exemplo, o ritmo trimestral), o painel MUST informar isso em vez de exibir valores enganosos.

**Chamadas de API por consentimento em "Como evolui?"**

- **FR-006**: Na métrica "Chamadas de API" de "Como evolui?", o usuário MUST poder escolher entre a escala "por consentimento/mês" (padrão, como na aba da instituição) e o volume (chamadas das últimas 4 semanas normalizadas para 30 dias).
- **FR-007**: A escala "por consentimento/mês" MUST seguir a regra única já adotada no painel: chamadas das 4 semanas normalizadas para 30 dias, divididas pela média de consentimentos únicos (PF + PJ) das mesmas 4 semanas; o ecossistema conta apenas instituições com chamadas na semana.
- **FR-008**: Para a mesma instituição e a mesma semana, o valor por consentimento em "Como evolui?" MUST ser igual ao de "Quem lidera?" e ao da aba da instituição.
- **FR-009**: Na escala por consentimento, o crescimento do ecossistema e o de cada instituição no período MUST ser calculado sobre o valor por consentimento, e a linha do ecossistema MUST ser desenhada como referência.
- **FR-010**: Na escala por consentimento, as visões baseadas em participação (participação %, participação por grupo mês a mês, ganhos e perdas de participação) MUST ficar desativadas com a explicação "participação não se aplica a chamadas por consentimento", porque participação de uma razão não é aditiva; o gráfico de linhas, os cartões de crescimento e o ritmo trimestral MUST continuar disponíveis, calculados sobre o valor por consentimento.
- **FR-011**: A escala escolhida MUST ser mantida ao trocar de métrica e voltar, e constar no título, subtítulo, imagem e CSV exportados.
- **FR-012**: Mês sem coleta ou sem consentimentos únicos MUST aparecer como lacuna, nunca como zero.

**Visão por endpoint em "Como opera uma instituição?"**

- **FR-013**: O bloco "Para que usa os dados" MUST oferecer um seletor entre "Por grupo de API" (padrão, comportamento atual inalterado) e "Por endpoint".
- **FR-014**: A visão por endpoint MUST oferecer um seletor das APIs usadas pela instituição na janela, com a API de maior volume selecionada por padrão, e MUST usar a mesma janela (últimas 4 semanas normalizadas para 30 dias), as mesmas unidades (% · API total · API/(PF + PJ)) e a mesma regra para o grupo Resource da visão por grupo.
- **FR-015**: Cada linha MUST mostrar o nome do endpoint, o valor da instituição, a participação dentro da API selecionada e o valor do comparado escolhido na aba para o mesmo endpoint.
- **FR-016**: A lista MUST mostrar todos os endpoints do catálogo da API selecionada, sem corte em "Top N" nem linha "Outros", ordenados por volume da instituição (do maior para o menor); endpoints sem uso na janela aparecem ao final com valor zero.
- **FR-017**: A soma dos endpoints mais a parcela "Sem endpoint identificado" MUST ser igual ao total da API selecionada na visão por grupo para a mesma instituição e janela.
- **FR-018**: A visão por endpoint MUST respeitar a instituição, a API, a unidade e a comparação selecionadas e ser incluída na imagem e no CSV exportados da aba.
- **FR-019**: A visão por grupo MUST continuar funcionando exatamente como hoje, sem mudança de valores nem de layout quando a visão por endpoint não estiver selecionada.

### Key Entities *(include if feature involves data)*

- **Período**: recorte de datas aplicado ao painel; ganha o recorte "desde o começo do ano", definido pela semana mais recente com dados.
- **Escala de API**: forma de expressar chamadas de API (volume normalizado para 30 dias ou por consentimento/mês).
- **Endpoint**: funcionalidade específica dentro de uma API de um grupo (por exemplo, uma consulta de saldo dentro de Contas), com nome; cada API tem vários, uma instituição usa parte deles, e parte das chamadas da API pode não estar atribuída a nenhum.
- **Parcela sem endpoint identificado**: chamadas da API que a base não consegue atribuir a um endpoint específico.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% das abas com filtro de período, escolher "Desde o começo do ano" produz um intervalo que começa na primeira semana do ano da semana mais recente com dados e termina nela, sem nenhum dia fora desse intervalo.
- **SC-002**: Para qualquer instituição e semana, o valor de chamadas por consentimento/mês em "Como evolui?" é idêntico ao de "Quem lidera?" e ao da aba da instituição (diferença zero).
- **SC-003**: Para qualquer instituição e qualquer API, a soma da visão por endpoint (com "Sem endpoint identificado") é igual ao total dessa API na visão por grupo para a mesma janela, com diferença zero.
- **SC-004**: O analista alterna entre a visão por grupo e por endpoint em um clique e vê o resultado em até 3 segundos, como nas demais interações do painel.
- **SC-005**: Os valores exibidos nas visões e abas existentes que não usam as novas opções permanecem idênticos aos de antes da mudança (nenhuma regressão); a única mudança de comportamento é a escala inicial da métrica "Chamadas de API" em "Como evolui?", que passa a abrir por consentimento/mês, com o volume a um clique e com os mesmos valores de antes.
- **SC-006**: O analista consegue montar, sem consultar a base, o recorte "ano até agora" de uma instituição, incluindo uso de API por consentimento e por endpoint, em menos de 5 minutos.

## Assumptions

- O ano de referência é o da semana mais recente com dados, não o da data atual.
- A escala "por consentimento/mês" em "Como evolui?" segue a mesma regra e o mesmo padrão de seletor de "Quem lidera?" e da aba da instituição, sem criar uma regra nova.
- A visão por endpoint lista todos os endpoints da API selecionada (sem "Top N"); endpoints do catálogo da API que a instituição não usou na janela aparecem com valor zero ao final. O padrão do seletor de API é a de maior volume da instituição.
- A visão por endpoint depende do detalhe por endpoint já coletado e armazenado; não exige nova coleta, mas pode exigir preparar esse detalhe para o painel.
- A base continua sendo atualizada uma vez por mês, e a data dos dados continua sendo a semana mais recente com coleta.
- Fora do escopo: novo período em formato livre (datas escolhidas pelo usuário), mudança no ranking de "Quem lidera?" e alteração da visão por grupo de API.

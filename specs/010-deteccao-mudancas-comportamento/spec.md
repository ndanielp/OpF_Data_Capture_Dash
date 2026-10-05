# Feature Specification: Módulo de Detecção de Mudanças de Comportamento Relevantes

**Feature Branch**: `010-deteccao-mudancas-comportamento`

**Created**: 2026-09-05 · **Revised**: 2026-09-23 (decisões calibradas contra a base real — ver Clarifications)

**Status**: Draft

**Input**: User description: "Um módulo de análise que identifique mudanças de comportamento relevantes, como novos receptores relevantes, aumento no uso de APIs e etc."

## Clarifications

### Session 2026-09-23

Decisões tomadas uma a uma com o responsável do produto, cada uma testada contra o histórico de `consents.db` (jan/2024 – ago/2026).

- Q: Quando um receptor novo vira alerta de "novo entrante relevante"? → A: Pelo ritmo de crescimento, desde que tenha no mínimo 30.000 consentimentos únicos. Com esse piso, três definições de crescimento testadas (+50% em 4 semanas, 2× em 8 semanas, 2× em 4 semanas) pegam exatamente os mesmos receptores na mesma semana; adota-se a mais simples, +50% em 4 semanas. A regra original (volume já na estreia) foi descartada: não pegaria o Banco Inter, que estreou com 271 e chegou a 204 mil em 8 semanas.
- Q: Estrear já acima de 30.000 também conta? → A: Sim. A estreia é tratada como crescimento a partir do zero (Shopee, Neon, RecargaPay). "Novo" = até 26 semanas desde a primeira aparição.
- Q: Alta e queda observam qual métrica? → A: Consentimentos (únicos e ativos) e uso de API, ambos desde a primeira entrega.
- Q: Qual regra para uso de API? → A: Média das 4 semanas mais recentes contra as 4 anteriores, descontando o movimento do ecossistema no mesmo grupo de API, com limites de −40% / +100%, e só alerta quando a condição se mantém por 2 semanas seguidas. A comparação semana a semana foi descartada: gera dezenas de alertas por semana e dispara em feriados (Sexta-feira Santa −26%, Natal, 1º de maio).
- Q: Qual regra para consentimentos? → A: Semana contra semana, −10% / +20%, com alerta imediato (sem exigir confirmação).
- Q: Onde os alertas são calculados? → A: Num processo separado, executado depois da coleta e antes da sincronização com a nuvem, gravando o resultado para o painel consumir. Fica dentro do componente de coleta (o painel não pode escrever no banco — Constituição, Princípio V).
- Q: Onde os alertas aparecem? → A: Num card "O que mudou" no topo da aba Ecossistema, com seletor de semana para consultar semanas anteriores. Não cria aba nova (o contrato visual fixa três abas).
- Q: Alertas de API cobrem o lado do transmissor? → A: Não nesta entrega. Só receptor × grupo de API.
- Q: Como organizar os alertas no card? → A: Seções por tipo (Novos entrantes, Altas, Quedas); dentro de cada uma, uma linha por instituição, ordenadas pelo volume da instituição.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ser alertado sobre novos entrantes relevantes (Priority: P1)

Como analista do ecossistema Open Finance, quero ser avisado quando um receptor recente se torna relevante — seja porque estreou já grande, seja porque cresceu rápido nas semanas seguintes —, para não deixar passar um novo player importante sem precisar comparar a lista de receptores semana a semana.

**Why this priority**: É o sinal de maior valor de descoberta. O caso do Banco Inter mostra o risco: um entrante que estreia pequeno e em poucas semanas vira um dos maiores do ecossistema.

**Independent Test**: Reprocessar o histórico e verificar que os entrantes já conhecidos pela equipe são sinalizados na semana esperada — Banco Inter (semana 6 após a estreia), CloudWalk (3ª observação após a estreia — semana 4 no calendário, pois a série tem uma semana faltando), PagSeguro (semana 2), Cumbuca (semana 10), Shopee e Neon (na estreia) — e que entrantes que nunca chegaram a 30.000 (Google Pay, Midway, BRB) não geram alerta.

**Acceptance Scenarios**:

1. **Given** um receptor que estreou há até 26 semanas, **When** ele estreia já com 30.000 consentimentos únicos ou mais, **Then** o módulo o sinaliza como novo entrante relevante na semana da estreia.
2. **Given** um receptor que estreou há até 26 semanas abaixo de 30.000, **When** ele passa de 30.000 tendo crescido 50% ou mais nas últimas 4 semanas, **Then** o módulo o sinaliza como novo entrante relevante naquela semana.
3. **Given** um receptor recente que cresce rápido mas continua abaixo de 30.000, **When** o módulo analisa a semana, **Then** nenhum alerta é gerado.
4. **Given** um receptor que já foi sinalizado como novo entrante, **When** o módulo analisa as semanas seguintes, **Then** ele não é sinalizado de novo como novo entrante.

---

### User Story 2 - Ser alertado sobre altas relevantes (Priority: P2)

Como analista, quero ser avisado quando uma instituição já estabelecida cresce muito além do seu padrão — em consentimentos ou no uso de um grupo de API —, para identificar tendências de adoção sem vasculhar gráfico por gráfico.

**Why this priority**: Segundo eixo de valor, sobre participantes já conhecidos. Depende do mesmo mecanismo de comparação temporal da US1.

**Independent Test**: Reprocessar o histórico e verificar que as altas conhecidas aparecem (ex.: CloudWalk em Contas, +272% contra o ecossistema em 17/07/2026, confirmado por 2 semanas) e que semanas de flutuação normal não geram alerta.

**Acceptance Scenarios**:

1. **Given** um receptor com 30.000 ou mais consentimentos e mais de 26 semanas de vida, **When** seus consentimentos (únicos ou ativos) sobem mais de 20% de uma semana para a seguinte, **Then** o módulo gera alerta de alta na mesma semana.
2. **Given** uma combinação receptor × grupo de API relevante, **When** a média de uso das últimas 4 semanas fica mais de 100% acima da média das 4 anteriores, já descontado o movimento do ecossistema naquele grupo, **e** essa condição se mantém por 2 semanas seguidas, **Then** o módulo gera um único alerta de alta para esse evento.
3. **Given** uma semana em que o ecossistema inteiro sobe ou cai (feriado, efeito geral), **When** o módulo analisa o uso de API, **Then** esse movimento comum não gera alertas por si só.

---

### User Story 3 - Ser alertado sobre quedas relevantes (Priority: P3)

Como analista, quero ser avisado quando uma instituição estabelecida cai muito abaixo do seu padrão, para investigar a causa (perda de clientes, problema técnico, problema na coleta) antes que passe despercebido.

**Why this priority**: Espelho da US2, com a mesma mecânica.

**Independent Test**: Reprocessar o histórico e verificar que as quedas conhecidas aparecem — Belvo (−37% em consentimentos únicos, fev/2026), Banco Safra (−47%, abr/2026; e queda simultânea em 3 grupos de API em 31/07/2026 — Cartão, Crédito e Investimentos —, com Contas confirmada na semana seguinte), Banco CSF (−83%, jul/2026).

**Acceptance Scenarios**:

1. **Given** um receptor com 30.000 ou mais consentimentos e mais de 26 semanas de vida, **When** seus consentimentos (únicos ou ativos) caem mais de 10% de uma semana para a seguinte, **Then** o módulo gera alerta de queda na mesma semana.
2. **Given** uma combinação receptor × grupo de API relevante, **When** a média das últimas 4 semanas fica mais de 40% abaixo da média das 4 anteriores, descontado o movimento do ecossistema, **e** isso se mantém por 2 semanas seguidas, **Then** o módulo gera um único alerta de queda para esse evento.
3. **Given** uma instituição sem histórico anterior suficiente, **When** o módulo analisa a semana, **Then** a ausência de dados prévios não é tratada como queda.

---

### Edge Cases

- **Picos que se desfazem em consentimentos**: como o alerta de consentimentos é imediato, um salto seguido de reversão na semana seguinte gera dois alertas (ex.: Neon +39% e −27% em julho/2026; Banco do Nordeste −31% e +46% em agosto/2026). É uma troca aceita: prioriza avisar cedo, e o par alta/queda seguido fica visível como anomalia para o analista.
- **Feriados e efeitos gerais no uso de API**: neutralizados por descontar o movimento do ecossistema no mesmo grupo de API.
- **Coleta incompleta**: não há semana com cobertura incompleta nos consentimentos no histórico atual; no uso de API, a exigência de 2 semanas seguidas reduz, mas não elimina, alertas falsos causados por coleta interrompida.
- **Instituição com vários alertas na mesma semana**: exibida numa única linha dentro da seção (ex.: "Banco Safra — queda em 4 grupos de API").
- **Novo entrante que também dispara variação**: durante as primeiras 26 semanas o receptor só pode gerar alerta de novo entrante; alertas de alta e queda de consentimentos começam depois disso.
- **Semana sem nenhum alerta**: o card informa explicitamente que não houve mudanças relevantes naquela semana.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE calcular os alertas num processo separado, executado depois de cada coleta e antes da sincronização com a nuvem, e gravar o resultado para o painel consumir.
- **FR-002**: O sistema DEVE sinalizar como **novo entrante relevante** o receptor com até 26 semanas desde a primeira aparição que (a) estreia com 30.000 ou mais consentimentos únicos, ou (b) passa de 30.000 tendo crescido 50% ou mais nas últimas 4 semanas. Cada receptor é sinalizado como novo entrante no máximo uma vez.
- **FR-003**: O sistema DEVE sinalizar **alta de consentimentos** quando os consentimentos únicos ou ativos de um receptor com 30.000 ou mais e mais de 26 semanas de vida sobem mais de 20% em relação à semana anterior, na mesma semana em que ocorre.
- **FR-004**: O sistema DEVE sinalizar **queda de consentimentos** quando os consentimentos únicos ou ativos de um receptor com 30.000 ou mais e mais de 26 semanas de vida caem mais de 10% em relação à semana anterior, na mesma semana em que ocorre.
- **FR-005**: O sistema DEVE sinalizar **alta** e **queda de uso de API** por receptor × grupo de API quando a razão entre a média das últimas 4 semanas e a das 4 anteriores, dividida pela mesma razão do ecossistema naquele grupo, ficar acima de 2,0 (alta) ou abaixo de 0,6 (queda) por 2 semanas seguidas; gera um alerta por evento, na segunda semana.
- **FR-006**: O sistema DEVE considerar para alertas de API apenas combinações receptor × grupo com uso relevante — média de 1.000.000 ou mais chamadas por semana nas 4 semanas de base —, patamar usado na calibração.
- **FR-007**: O sistema NÃO DEVE gerar alertas de alta ou queda para combinações sem histórico suficiente: 8 semanas para uso de API (4 de base + 4 recentes) e mais de 26 semanas de vida para consentimentos.
- **FR-008**: Cada alerta DEVE conter: tipo, instituição, métrica ou grupo de API, semana de referência, valor anterior, valor atual e variação percentual.
- **FR-009**: O painel DEVE exibir os alertas num card "O que mudou" no topo da aba Ecossistema, em três seções (Novos entrantes, Altas, Quedas), com uma linha por instituição em cada seção, ordenadas pelo volume da instituição.
- **FR-010**: O card DEVE mostrar por padrão a semana mais recente e permitir escolher semanas anteriores.
- **FR-011**: O card DEVE respeitar o filtro de grupos de instituição já existente (Incumbentes, Neo Banks, ITPs, Outros).

### Key Entities

- **Alerta de Mudança**: evento detectado para uma semana. Atributos: tipo (novo entrante, alta, queda), métrica (consentimentos únicos, consentimentos ativos ou grupo de API), instituição, semana, valor anterior, valor atual, variação.
- **Instituição (Receptor)**: entidade já existente, sujeito dos alertas; sua data de primeira aparição define se é "nova".
- **Grupo de API**: categoria já existente (Contas, Cartão, Crédito, Investimentos, Câmbio, Cadastro), sujeito dos alertas de uso de API.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um analista identifica as mudanças relevantes da semana em menos de 1 minuto, sem cruzar tabelas ou gráficos.
- **SC-002**: Reprocessando o histórico, o módulo sinaliza os eventos conhecidos listados nos Independent Tests das três histórias (Inter, Shopee, CloudWalk, PagSeguro, Cumbuca, Neon, Belvo, Safra, CSF) na semana esperada.
- **SC-003**: Na média histórica, o volume fica administrável: cerca de 2 alertas de API e menos de 1 de consentimentos por semana, além dos novos entrantes (10 em 2,5 anos de histórico, cerca de 1 por trimestre).
- **SC-004**: Nenhum alerta de alta ou queda é gerado para instituição ou combinação sem o histórico mínimo do FR-007.

## Assumptions

- Os limites (30.000; +50% em 4 semanas; 26 semanas; −10%/+20%; −40%/+100% com confirmação de 2 semanas; 1.000.000 de chamadas por semana) são fixos nesta versão e foram calibrados contra o histórico de jan/2024 a ago/2026; não são configuráveis pelo usuário final.
- A série de consentimentos é estável (variação semanal típica de +1,2%), o que torna a comparação semana a semana adequada; a de uso de API é ruidosa, o que exige janelas de 4 semanas, desconto do ecossistema e confirmação.
- Os alertas só mudam quando há coleta nova (cadência semanal); não há processamento em tempo real.
- Alertas pelo lado do transmissor ficam fora desta entrega.
- O módulo complementa as visões existentes do painel (mapa estratégico, intensidade, eficiência, aceleração); não as substitui.

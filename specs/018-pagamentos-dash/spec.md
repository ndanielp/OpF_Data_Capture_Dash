# Feature Specification: Tema Pagamentos no Dashboard 2.0

**Feature Branch**: `018-pagamentos-dash`

**Created**: 2026-11-20

**Status**: Implemented

**Input**: User description: "Incluir a visão de pagamento no Dash. Regras: (1) só há sucesso (200) e falha (500, que inclui os 4xx); (2) o proxy de transação é Criar iniciação nas APIs Iniciação de Pagamento e Pagamento Automático; (3) não dá para distinguir os tipos de iniciação; (4) da API de pagamentos sem redirecionamento sai o funil do vínculo de conta. Opção A: seletor de tema Dados | Pagamentos com as mesmas perguntas. Detentora incluída. UX validada no protótipo (ux-handoff.md)."

## Clarifications

### Session 2026-11-20

Decisões tomadas com o responsável do produto durante a revisão do protótipo:

- Q: Quais APIs contam como transação? → A: Criar iniciação em `payments` (endpoint 65, "Iniciação de Pagamento") e `automatic-payments` (endpoint 129, "Pagamento Automático").
- Q: Como mostrar o funil do vínculo? → A: só no nível do ecossistema e da instituição, como detalhe recolhido "só Jornada sem Redirecionamento (JSR)", nunca como bloco principal. Degraus 133 → 139 → 136 (autorização no detentor, inferida) → 137; 135 aparece à parte.
- Q: Funil de pagamento JSR e "fatia sem redirecionamento"? → A: removidos de todo o painel.
- Q: Visão por detentora? → A: sim, em todas as abas (alternador de papel) e na matriz.
- Q: Integração no portal? → A: Opção A, seletor Dados | Pagamentos no cabeçalho com as mesmas perguntas, mais uma aba própria "Quem paga com quem?".

Decisões tomadas na especificação (o usuário pediu para seguir sem interromper; registradas em research.md):

- Q: Regras dos alertas de pagamento? → A: mesmo desenho dos alertas de consentimento: 4 semanas contra as 4 anteriores; volume −10% / +20%; falha ±5 pp; conversão do vínculo ±5 pp; piso de 30 mil transações por 30 dias (falha e conversão: nas duas janelas; 1.000 vínculos iniciados para conversão); vira alerta quando a condição vale na última semana e na anterior, senão fica "em observação".
- Q: Período das abas Evolução, Matriz e Instituição? → A: meses da base, no máximo os 12 últimos; sem filtro de período.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver quem lidera a iniciação de pagamentos (Priority: P1)

O analista abre o painel, troca o tema para Pagamentos e vê as maiores iniciadoras ou detentoras por transações aceitas, a divisão entre Iniciação de Pagamento e Pagamento Automático, a taxa de falha de cada uma e o crescimento.

**Why this priority**: é a porta de entrada do tema e responde à pergunta mais feita ("quem são os grandes?").

**Independent Test**: abrir `/v2`, clicar em "Pagamentos", conferir o Top 10 de iniciadoras e de detentoras contra uma consulta direta à base.

**Acceptance Scenarios**:

1. **Given** a base com dados até 30/10/2026, **When** o usuário abre `/v2/pagamentos`, **Then** vê 4 indicadores (total por 30 dias, cada API com fatia e falha, divisão IP × PA) e o Top 10 de iniciadoras.
2. **Given** a aba aberta, **When** troca para "Detentoras" e para a API "Pagamento Automático", **Then** o ranking passa a ordenar detentoras só pelas transações dessa API, e a fatia é calculada sobre o total dessa API.
3. **Given** uma instituição fixada, **When** ela está fora do Top 10, **Then** aparece ao fim do ranking com destaque.

---

### User Story 2 - Seguir a evolução mês a mês com recorte (Priority: P1)

O analista lê a aba "Como evolui?" como uma história em quatro passos (quanto cresceu, quem puxou, como mudou o mix, se a qualidade acompanhou) e tira ou inclui iniciadoras e detentoras da análise.

**Why this priority**: responde à pergunta de tendência, que o responsável do produto pediu para ler "de cima para baixo".

**Independent Test**: desligar o Google Pay no recorte e conferir que os quatro passos e as frases mudam para o total sem ele.

**Acceptance Scenarios**:

1. **Given** todos os chips ligados, **When** a aba abre, **Then** o passo 1 mostra o total do último mês e do primeiro, e as barras mensais empilhadas por API somam esse total.
2. **Given** uma iniciadora desligada, **When** o recorte muda, **Then** os quatro passos e as frases são recalculados sem ela, sem nova ida ao servidor, e uma linha informa o que está fora.
3. **Given** o rodapé JSR fechado, **When** o usuário clica em "Ver funil do vínculo", **Then** o funil de 4 degraus aparece com a taxa de passagem entre eles.

---

### User Story 3 - Entender uma instituição em pagamentos (Priority: P1)

O analista escolhe uma instituição e um papel (iniciadora ou detentora) e vê quanto ela opera, com quem, com que mix e com que qualidade, com a opção de tirar contrapartes da análise.

**Why this priority**: é a análise que gera ação (onde uma instituição falha e com quem).

**Independent Test**: abrir Nubank como detentora e conferir que o Iniciador concentra a maior parte das falhas no último mês.

**Acceptance Scenarios**:

1. **Given** uma instituição que só aparece como iniciadora, **When** a aba abre, **Then** o chip "Detentora" fica desabilitado e o papel é Iniciadora.
2. **Given** Nubank como detentora, **When** o usuário vê o passo 4, **Then** há linhas de falha por API, a linha tracejada do Automático no ecossistema e a lista "Onde falha" com parte das falhas e taxa por contraparte.
3. **Given** o papel detentora, **When** o usuário abre o rodapé JSR, **Then** vê o funil do vínculo com contas da instituição e a conversão e a autorização dela contra o ecossistema.

---

### User Story 4 - Ver quem paga com quem ao longo do tempo (Priority: P2)

O analista vê a matriz iniciadora × detentora de um mês, colore por volume, falha ou crescimento, percorre os meses pela linha do tempo e abre o detalhe de um par.

**Why this priority**: mostra a dinâmica do mercado entre os dois lados, que nenhuma outra aba mostra.

**Independent Test**: escolher "Falha" e o mês de junho e conferir que a coluna Santander destaca a falha do Automático.

**Acceptance Scenarios**:

1. **Given** a matriz no último mês, **When** o usuário arrasta a linha do tempo para outro mês, **Then** valores, cores, totais e frases mudam para aquele mês.
2. **Given** "Reproduzir", **When** clicado, **Then** os meses avançam a cada 1,2 s até o último e o botão volta a "Reproduzir".
3. **Given** uma célula clicada, **When** o painel abre, **Then** mostra transações, falha, divisão IP/PA, fatia na linha e na coluna e variação contra o mês anterior.

---

### User Story 5 - Saber o que mudou (Priority: P2)

O analista vê as mudanças relevantes de volume, falha e conversão do vínculo nas últimas 4 semanas, por instituição e papel, e as que ainda aguardam confirmação.

**Why this priority**: fecha o paralelo com a aba de alertas do tema Dados.

**Independent Test**: com dados sintéticos em que uma detentora sobe a falha 10 pp por duas semanas seguidas, ela aparece como alerta; com uma semana só, em observação.

**Acceptance Scenarios**:

1. **Given** uma mudança confirmada em duas semanas, **When** a aba abre, **Then** a mudança aparece no card do mês com selo, frase e "antes → agora".
2. **Given** o filtro "Falha", **When** aplicado, **Then** só mudanças de falha aparecem; sem nenhuma, a mensagem de vazio.

---

### Edge Cases

- Tabela pré-agregada de pagamentos ainda não gerada: cada aba mostra um aviso legível ("Dados de pagamento ainda não processados") em vez de erro; o tema Dados segue normal.
- Instituição sem dados no papel escolhido na URL: abre no outro papel.
- Mês com 4 ou 5 semanas: normalizado para 30 dias, para os meses ficarem comparáveis.
- Semana sem coleta dentro do mês: o mês divide só pelas semanas com dado.
- Recorte que tira tudo: frases dizem "Sem transações no recorte escolhido." e os gráficos ficam vazios, sem erro.
- Falha com denominador zero: "—", nunca 0%.
- Diagonal da matriz (mesma instituição dos dois lados): mostra o valor real.
- Uuid desconhecido em `/v2/pagamentos/instituicao`: mensagem "Instituição não encontrada" e o seletor aberto.

## Requirements *(mandatory)*

### Functional Requirements

**Tema e navegação**

- **FR-001**: O cabeçalho de todas as páginas v2 MUST ter o seletor "Dados | Pagamentos". No tema Pagamentos as abas são, nesta ordem: Quem lidera?, Quem paga com quem?, Como evolui?, O que mudou?, Como opera uma instituição?
- **FR-002**: Trocar de tema MUST levar à pergunta equivalente no outro tema; "Quem paga com quem?" leva a "Quem lidera?" do tema Dados. A página de exportação não muda o tema.
- **FR-003**: Todas as páginas do tema MUST seguir a casca v2 (§6.8): barra de filtros primeiro, título, cards com título, subtítulo, rodapé com regra e fonte, "Copiar como imagem" e "Exportar CSV" na barra.

**Regras de dado**

- **FR-010**: Transação MUST ser a contagem de respostas 200 em Criar iniciação (65 em `payments`, 129 em `automatic-payments`). Falha MUST ser 500 ÷ (200 + 500) nesses mesmos endpoints.
- **FR-011**: Iniciadora MUST ser o receptor da tabela de pagamentos; detentora, o transmissor.
- **FR-012**: Volumes das últimas 4 semanas MUST ser normalizados para 30 dias (× 30/28). Volumes mensais MUST ser a soma do mês ÷ número de semanas do mês com dado na base × 30/7.
- **FR-013**: Crescimento no ranking MUST comparar as últimas 4 semanas com as 4 anteriores.
- **FR-014**: Funil do vínculo MUST usar 133 (iniciado), 139 (sinais de risco), 136 (autorizado no detentor, inferido) e 137 (ativo), com status 200; conversão = 137 ÷ 133; autorização = 136 ÷ 139; vínculos encerrados = 135. Sempre rotulado "só Jornada sem Redirecionamento".
- **FR-015**: Consultas por iniciação MUST ser 66 ÷ 65 (Iniciação de Pagamento) e 130 ÷ 129 (Pagamento Automático), status 200, últimas 4 semanas.

**Quem lidera?**

- **FR-020**: A aba MUST mostrar 4 indicadores (total por 30 dias com nº de iniciadoras e detentoras ativas; cada API com valor, fatia e falha; divisão IP × PA com variação em pp contra as 4 semanas anteriores) e o ranking Top 10 por papel e API.
- **FR-021**: Cada linha do ranking MUST ter posição, nome com link para a aba da instituição no papel, barra IP/PA, volume, fatia, falha por API ("—" sem tentativas), crescimento. Falha ≥ 20% em destaque.
- **FR-022**: O usuário MUST poder fixar e excluir instituições; fixadas fora do Top 10 aparecem ao fim; a escolha fica guardada no navegador, separada da do tema Dados.

**Quem paga com quem?**

- **FR-040**: A matriz MUST cruzar as 8 maiores iniciadoras e as 8 maiores detentoras (pelo volume das últimas 4 semanas, as duas APIs) mais "Outras" de cada lado, por mês, em transações por 30 dias, com totais de linha e coluna; com "Top 4" as demais entram em "Outras".
- **FR-041**: A cor da célula MUST seguir Volume, Falha ou Crescimento contra o mês anterior; o filtro de API MUST valer para valores e cores.
- **FR-042**: A linha do tempo MUST permitir escolher o mês (controle deslizante, ‹ ›) e reproduzir os meses a cada 1,2 s; abre no último mês.
- **FR-043**: Clicar numa célula MUST abrir o detalhe do par (transações, falha, divisão IP/PA, fatia na linha e na coluna, variação contra o mês anterior).
- **FR-044**: A aba MUST mostrar 3 frases geradas dos dados do mês escolhido: maior par, par com maior falha entre os que têm ao menos 1% do volume, par que mais cresceu desde o primeiro mês.

**Como evolui?**

- **FR-050**: A aba MUST mostrar os quatro passos (quanto cresceu, quem puxou, como mudou o mix, a qualidade acompanhou), cada um com uma frase de leitura gerada dos números.
- **FR-051**: O recorte MUST permitir ligar e desligar cada uma das 8 maiores iniciadoras e detentoras e "Outras"; os quatro passos seguem o recorte; o detalhe JSR não segue e diz isso.
- **FR-052**: O detalhe JSR MUST abrir fechado, com a conversão do último e do primeiro mês, e mostrar o funil e os encerrados ao abrir.

**O que mudou?**

- **FR-030**: Uma mudança MUST comparar as últimas 4 semanas com as 4 anteriores, por instituição e papel.
- **FR-031**: Volume: queda de 10% ou alta de 20% nas transações.
- **FR-032**: Falha: variação de 5 pp ou mais na taxa de uma API.
- **FR-033**: Conversão do vínculo: variação de 5 pp ou mais.
- **FR-034**: Piso: volume, 30 mil transações por 30 dias na janela atual ou na anterior; falha, 30 mil tentativas da API por 30 dias em cada uma das duas janelas; conversão, 1.000 vínculos iniciados por 30 dias em cada uma das duas janelas.
- **FR-035**: Vira alerta a condição que vale com a janela terminando na última semana e na semana anterior; a que vale só na última fica "em observação".
- **FR-036**: A aba MUST filtrar por tipo (Todas, Volume, Falha, Conversão) e papel (Todos, Iniciadoras, Detentoras) e mostrar o piso.

**Como opera uma instituição?**

- **FR-060**: A aba MUST permitir escolher qualquer instituição que aparece em pagamentos e o papel; o papel sem dados fica desabilitado; a escolha fica na URL (`uuid`, `role`).
- **FR-061**: A aba MUST mostrar os quatro passos (quanto opera, com quem, com que mix, com que qualidade) com frases geradas, e o recorte de contrapartes (8 maiores + Outras).
- **FR-062**: O passo 4 MUST comparar a falha do Automático com a do ecossistema e listar as 5 contrapartes com mais falhas no último mês (parte das falhas e taxa).
- **FR-063**: O rodapé MUST mostrar o funil JSR do papel (vínculos com contas da instituição, como detentora; vínculos que ela iniciou, como iniciadora) contra o ecossistema, ou dizer que ela não usa JSR, e as consultas por iniciação.

**Dados e desempenho**

- **FR-070**: Os dados de pagamento MUST vir de uma pré-agregação mantida pelo coletor (fim da coleta e `compute_signals.py`); o painel só lê.
- **FR-071**: Sem a pré-agregação, as rotas de pagamento MUST responder sem erro com o bloco marcado como indisponível.

### Key Entities

- **Transação de pagamento**: semana × iniciadora × detentora × API × status, contagem de Criar iniciação.
- **Etapa do vínculo**: semana × iniciadora × detentora × endpoint do vínculo (133, 135, 136, 137, 139), contagem com status 200.
- **Consulta**: semana × iniciadora × detentora × endpoint de consulta (66, 130).
- **Mudança de pagamento**: instituição, papel, tipo (volume, falha, conversão), API, antes, agora, estado (alerta ou em observação).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O total de transações por 30 dias da aba Quem lidera? bate com a consulta direta à base (soma dos 200 em 65 e 129 nas últimas 4 semanas × 30/28), com diferença de arredondamento apenas.
- **SC-002**: Cada aba do tema abre com dados em até 2 s na base local atual, e cada rota de pagamento responde em até 500 ms com o cache aquecido.
- **SC-003**: Ligar ou desligar um chip do recorte atualiza a página em menos de 200 ms, sem ida ao servidor.
- **SC-004**: Todas as abas do tema ficam utilizáveis a 1280 × 800 sem rolagem horizontal da página e a 390 px de largura com rolagem só dentro dos cards largos.
- **SC-005**: Nenhum número de pagamento aparece sem a regra de origem no rodapé do card.

## Assumptions

- O portal do Open Finance atrasa cerca de 2 semanas; "dados até" é a última semana da tabela de pagamentos.
- A coleta de pagamentos (`run-pi`) continua gravando `payment_api_requests` com transmissor sempre preenchido.
- Os nomes curtos seguem `SHORT_NAMES`; "Google Pay" e "Lina" entram na lista.
- O tema claro/escuro e o seletor de tema de dados são independentes.
- Exportar slide não entra nesta entrega.

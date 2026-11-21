# Feature Specification: Polimento do tema Pagamentos

**Feature Branch**: `019-pagamentos-polish`

**Created**: 2026-11-20

**Status**: Implemented

**Input**: User description: "Falta polir. Senti falta de conseguir ver algumas informações de meses específicos. Não gostei do modo de excluir da seleção. Prefiro filtrar e ir incluindo. Também quero poder selecionar qualquer instituição." Avaliação de usabilidade completa em [usability-review.md](usability-review.md) (problemas P1–P16).

**Depends on**: feature 018 (tema Pagamentos), já entregue no commit `152a4a8`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver um mês específico (Priority: P1)

O analista quer saber como estava o mercado num mês: quem liderava em junho, quanto cada API transacionou naquele mês e quais mudanças foram confirmadas em agosto. Hoje ele só vê as últimas 4 semanas, ou precisa exportar o CSV.

**Why this priority**: é o pedido mais direto do responsável do produto e afeta todas as abas.

**Independent Test**: escolher "junho/2026" em Quem lidera? e conferir o ranking contra a soma do mês na base; clicar na barra de junho em Como evolui? e ler os valores por API.

**Acceptance Scenarios**:

1. **Given** Quem lidera? aberta, **When** o usuário escolhe "junho/2026" no seletor de mês, **Then** ranking, indicadores, fatia e falha passam a ser de junho (por 30 dias), o crescimento compara com maio e o título do card diz "junho/2026".
2. **Given** as barras mensais de Como evolui?, **When** o usuário passa o mouse ou foca a barra de julho, **Then** vê o total, o valor por API e a falha por API de julho, sem sair da página.
3. **Given** as barras mensais, **When** o usuário clica em julho, **Then** os indicadores ao lado mostram julho, a barra e a linha de julho ficam destacadas em todos os passos e o seletor de mês da barra de filtros passa a julho.
4. **Given** o passo "Quem puxou o crescimento?", **When** o usuário escolhe "de março até agosto", **Then** as barras e a frase comparam março com agosto.
5. **Given** O que mudou?, **When** o usuário clica em agosto na barra de meses, **Then** vê as mudanças confirmadas em agosto; "Em observação" aparece só no mês mais recente.

---

### User Story 2 - Filtrar incluindo instituições (Priority: P1)

O analista parte de "todas" e vai adicionando as instituições que quer analisar. A análise passa a considerar só as escolhidas. Hoje ele começa com tudo ligado e vai riscando, e as instituições riscadas parecem desabilitadas.

**Why this priority**: é o modelo de filtro que o responsável do produto pediu; muda Evolução, Matriz e Instituição.

**Independent Test**: em Como evolui?, adicionar Google Pay e Nubank como iniciadoras e conferir que os quatro passos somam só as duas; limpar e voltar ao total do ecossistema.

**Acceptance Scenarios**:

1. **Given** Como evolui? aberta, **When** a aba abre, **Then** a barra mostra "Iniciadoras: todas" e "Detentoras: todas", cada uma com "+ Adicionar".
2. **Given** "+ Adicionar" em Iniciadoras, **When** o usuário escolhe Google Pay e depois Nubank, **Then** aparecem dois chips com ×, os quatro passos consideram só as duas e as frases dizem "Entre Google Pay e Nubank, …".
3. **Given** dois chips, **When** o usuário clica em "Limpar", **Then** volta a "todas" e aos números do ecossistema.
4. **Given** instituições escolhidas em Como evolui?, **When** o usuário vai para Quem paga com quem?, **Then** a matriz abre com essas instituições nas linhas, e a URL de cada aba reproduz a escolha ao ser aberta noutro navegador.

---

### User Story 3 - Escolher qualquer instituição (Priority: P1)

O analista quer analisar uma instituição pequena (Klavi, Belvo) contra outra, ou montar a matriz só com os bancos que acompanha. Hoje só as 8 maiores podem ser escolhidas, e o resto fica escondido em "Outras".

**Why this priority**: sem isso o filtro por inclusão serve só para as 8 maiores.

**Independent Test**: adicionar Klavi como linha e Sicredi como coluna da matriz e conferir a célula contra a base.

**Acceptance Scenarios**:

1. **Given** a busca de instituição aberta com o campo vazio, **When** o usuário rola a lista, **Then** vê todas as instituições do papel, ordenadas por volume do mês, com o volume e o papel de cada uma.
2. **Given** a matriz, **When** o usuário adiciona Klavi às linhas e Sicredi às colunas, **Then** as duas aparecem com valores próprios; "Outras" soma o resto e mostra quantas instituições soma.
3. **Given** 12 linhas na matriz, **When** o usuário tenta adicionar a 13ª, **Then** a busca avisa o limite e não adiciona.
4. **Given** Quem lidera?, **When** o usuário escolhe "Mostrar: todas", **Then** o ranking lista todas as instituições com transações no período.
5. **Given** a aba da instituição como detentora, **When** o usuário adiciona uma iniciadora fora das 8 maiores, **Then** ela vira uma linha própria e sai de "Outras".

---

### User Story 4 - Leitura e acabamento (Priority: P2)

O analista lê os gráficos sem precisar adivinhar valores pelo eixo e sem ruído visual.

**Why this priority**: melhora a leitura, mas não destrava nenhuma análise nova.

**Independent Test**: percorrer as 5 abas a 1280 px e a 800 px e conferir os critérios FR-040 a FR-045.

**Acceptance Scenarios**:

1. **Given** as linhas de falha, **When** o usuário passa o mouse num mês, **Then** vê o valor de cada série naquele mês; o último ponto e o mês escolhido têm o valor escrito.
2. **Given** uma instituição que só usa o Pagamento Automático, **When** a aba da instituição abre, **Then** a legenda não lista a Iniciação de Pagamento.
3. **Given** a matriz, **When** o usuário escolhe um mês na linha do tempo, **Then** o nome do mês fica alinhado com a posição escolhida e nenhuma marca se sobrepõe aos números das células.
4. **Given** O que mudou?, **When** a aba abre, **Then** as mudanças aparecem agrupadas por instituição e há uma busca por nome.

---

### Edge Cases

- Mês sem nenhuma transação no recorte: cards com "Sem transações em <mês> no recorte escolhido.", sem erro.
- Mês parcial (a base termina no meio do mês): normalizado para 30 dias pelas semanas com dado, como hoje, e marcado "parcial" no seletor.
- Instituição escolhida que não aparece no mês escolhido: fica no recorte, com valor zero e "—" na falha.
- Instituição escolhida num papel em que ela não atua (ex.: Google Pay como detentora): a busca não a oferece naquele papel.
- URL com uuid desconhecido ou mês fora da base: ignora o item inválido, mostra o resto e avisa numa linha.
- Escolha "de" posterior a "até" na comparação de meses: os dois são trocados.
- Recorte com instituições escolhidas dos dois lados: a análise considera só os pares entre elas.

## Requirements *(mandatory)*

### Functional Requirements

**A. Mês específico**

- **FR-001**: Todas as abas de pagamento MUST ter um seletor de mês na barra de filtros, com os meses da base e "Últimas 4 semanas". O padrão é "Últimas 4 semanas" em Quem lidera? e O que mudou? e o último mês nas demais.
- **FR-002**: O mês escolhido MUST valer para a aba toda e aparecer no título dos cards afetados.
- **FR-003**: Em Quem lidera?, com um mês escolhido, ranking, indicadores, fatia e falha MUST ser do mês (por 30 dias), e o crescimento MUST comparar com o mês anterior.
- **FR-004**: As barras mensais MUST mostrar, ao passar o mouse ou focar, o mês, o total, o valor por API e a falha por API; ao clicar, MUST escolher o mês (o mesmo do FR-001), destacando-o em todos os passos.
- **FR-005**: "Quem puxou o crescimento?" (Evolução) e a tabela de contrapartes (Instituição) MUST comparar dois meses escolhidos pelo usuário ("de" e "até"); o padrão é o primeiro e o último mês.
- **FR-006**: As linhas de falha MUST ter um ponto em cada mês, o valor escrito no último ponto e no mês escolhido, e uma dica com o valor de cada série ao passar o mouse.
- **FR-007**: O que mudou? MUST ter uma barra de meses com a contagem de mudanças confirmadas por mês; escolher um mês mostra as mudanças confirmadas nele. "Em observação" só no mês mais recente.
- **FR-008**: A linha do tempo da matriz e o seletor de mês MUST ser o mesmo estado.

**B. Filtrar incluindo**

- **FR-010**: O recorte MUST começar em "todas" para iniciadoras e detentoras, com "+ Adicionar" para cada lado. O modo de riscar desaparece.
- **FR-011**: Cada instituição adicionada MUST aparecer como chip com × para remover; "Limpar" volta a "todas".
- **FR-012**: Com ao menos uma instituição escolhida num lado, a análise MUST considerar só as escolhidas daquele lado; com escolhas dos dois lados, só os pares entre elas.
- **FR-013**: As frases de leitura MUST citar o recorte quando há instituições escolhidas (até 3 nomes, depois "e mais N").
- **FR-014**: Instituições escolhidas e mês MUST ser compartilhados entre as abas de pagamento na mesma sessão do navegador e refletidos na URL de cada aba.
- **FR-015**: "Exportar CSV" MUST ficar à direita da primeira linha da barra de filtros em todas as abas de pagamento.

**C. Qualquer instituição**

- **FR-020**: Qualquer instituição que aparece em pagamentos MUST poder ser escolhida no recorte, nas linhas e colunas da matriz e nas contrapartes da aba da instituição, respeitando o papel.
- **FR-021**: A matriz MUST partir das 8 maiores de cada lado e permitir adicionar e remover linhas e colunas, até 12 de cada lado, com "Outras" somando o resto e mostrando quantas instituições soma. O tamanho padrão passa a ser "Maiores: 4 · 8 · 12".
- **FR-022**: A busca de instituição MUST listar, com o campo vazio, todas as instituições do papel por volume do mês escolhido (maior primeiro), com o volume e os papéis; a lista MUST rolar até o fim; a busca MUST ignorar acento e caixa.
- **FR-023**: Na aba da instituição, as contrapartes MUST partir das 8 maiores e aceitar qualquer outra adicionada pela busca.
- **FR-024**: Quem lidera? MUST oferecer "Mostrar: 10 · 25 · todas"; as fixadas continuam aparecendo fora do corte.

**D. Leitura e acabamento**

- **FR-040**: Legendas MUST listar só as séries presentes no gráfico.
- **FR-041**: Na matriz, o nome do mês escolhido MUST ficar alinhado com a sua posição na linha do tempo.
- **FR-042**: Nenhum elemento sobreposto MUST alterar a leitura do número de uma célula da matriz.
- **FR-043**: Os indicadores de Quem lidera? MUST ficar em 4 colunas a partir de 1000 px e em 2 × 2 abaixo disso, sem card sozinho numa linha.
- **FR-044**: O que mudou? MUST agrupar as mudanças por instituição (uma linha por instituição e papel, com as mudanças dela) e ter busca por nome.
- **FR-045**: Todos os novos controles (seletor de mês, barras clicáveis, chips, busca) MUST funcionar por teclado, com alvo de 44 px e nome acessível.

### Key Entities

- **Recorte**: lista de iniciadoras escolhidas e lista de detentoras escolhidas (vazia = todas).
- **Mês escolhido**: um mês da base ou "Últimas 4 semanas".
- **Comparação de meses**: par "de" e "até".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O total de um mês em Quem lidera? bate com a soma do mês na base normalizada para 30 dias, com diferença só de arredondamento.
- **SC-002**: Um usuário chega ao valor por API de um mês qualquer em no máximo 1 interação (passar o mouse ou focar a barra), sem exportar.
- **SC-003**: Um usuário monta a matriz com 2 instituições fora das 8 maiores em até 6 cliques.
- **SC-004**: Trocar o mês, adicionar ou remover uma instituição atualiza a página em até 1 s com a base local atual.
- **SC-005**: Abrir a URL copiada de uma aba reproduz o mesmo mês e as mesmas instituições.
- **SC-006**: As 5 abas continuam sem rolagem horizontal da página a 1280 × 800 e a 390 px.

## Assumptions

- As regras de dado da feature 018 não mudam: transação, falha, normalização mensal e por 30 dias, papéis, regras de mudança.
- "Últimas 4 semanas" continua existindo porque é a única janela que inclui as semanas mais recentes de um mês ainda incompleto.
- Fixar e excluir no ranking (Quem lidera?) continuam como estão: é preferência de ranking, não recorte de análise.
- O limite de 12 por lado na matriz vem da legibilidade a 1280 px.
- Comparar duas instituições lado a lado, exportar slide e gravar alertas em tabela ficam fora desta feature.

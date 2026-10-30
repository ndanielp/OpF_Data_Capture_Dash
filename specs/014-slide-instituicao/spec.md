# Feature Specification: Exportar "Como opera uma instituição?" como slide

**Feature Branch**: `014-slide-instituicao`

**Created**: 2026-10-30

**Status**: Implemented

**Input**: User description: "Planeje para incluir a exportação de Como opera uma instituição como um slide. A exportação deve funcionar como as demais e não deve incluir alertas. Respeite o design system e regras de layout. Nada mais muda." Depois do plano: "Remove a taxa de erro de API para reduzir a quantidade de conteúdo."

## Clarifications

### Session 2026-10-30

- Q: Que formato tem o slide? → A: Uma imagem PNG 1600×900, como as exportações de imagem das outras abas; não é um arquivo editável de apresentação.
- Q: O que fica fora do slide? → A: Os alertas, a taxa de erro de API e as chamadas por grupo de API. Os três continuam na página; a taxa de erro e as chamadas por grupo continuam no CSV.
- Q: O slide mostra o que está na tela? → A: Sim, como o CSV: mesma instituição, comparação, período, unidade e visão ("Por grupo de API" ou "Por endpoint") escolhidos.

### Session 2026-10-30 (ajuste depois da primeira versão)

- Q: O bloco "Chamadas por grupo de API" fica no slide? → A: Não; sai do slide (continua na página).
- Q: O bloco "Quais dados busca" mantém o nome? → A: Passa a se chamar "Quais dados busca", na página, nas imagens e no slide.
- Q: Como "Quais dados busca" aparece no slide? → A: Completo, sem cortes: todos os grupos ou todos os endpoints da API escolhida.

## Contexto de uso

O responsável do produto abre o painel 1 a 2 vezes por mês, depois da atualização da base, e leva prints e dados exportados para slides. Hoje, em "Como opera uma instituição?", cada bloco pode ser copiado como imagem, um por um, e a página inteira só sai em CSV. Para montar uma lâmina com o perfil de uma instituição é preciso exportar vários blocos e juntá-los à mão. O objetivo é obter, num clique, uma lâmina pronta com o perfil da instituição.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Baixar o perfil da instituição como um slide (Priority: P1)

Como analista, quero exportar o perfil da instituição escolhida como uma única imagem de slide, para colocá-la direto numa apresentação sem montar blocos à mão.

**Why this priority**: É a feature inteira. Entrega valor sozinha e não depende de mudança em dados nem em outras abas.

**Independent Test**: Em "Como opera uma instituição?", com uma instituição, uma comparação e um período escolhidos, acionar "Exportar slide" e conferir que o PNG baixado tem 1600×900, mostra instituição, comparação e período no título, traz os indicadores, a evolução, "Quais dados busca" (completo) e os transmissores, e não traz alertas, taxa de erro nem chamadas por grupo.

**Acceptance Scenarios**:

1. **Given** a página com uma instituição carregada, **When** o usuário aciona "Exportar slide", **Then** é baixado um PNG de 1600×900 com título contendo a instituição e os filtros ativos (comparação e período), subtítulo com a semana dos dados, e rodapé "Fonte: dashboard Open Finance Brasil · dados até DD/MM/AAAA".
2. **Given** a página carregada, **When** o slide é gerado, **Then** ele contém os quatro indicadores, a evolução, "Quais dados busca" e os transmissores, e não contém os alertas, a taxa de erro de API nem as chamadas por grupo. "Quais dados busca" aparece completo: todos os grupos (ou, na visão por endpoint, todos os endpoints da API escolhida), sem corte.
3. **Given** o bloco "Quais dados busca" na visão "Por endpoint", **When** o usuário exporta o slide, **Then** o slide mostra a visão por endpoint, com a API e a unidade escolhidas.
4. **Given** o tema escuro ativo, **When** o usuário exporta o slide, **Then** o slide sai no tema escuro, com as cores de grupo da versão escura.
5. **Given** a exportação concluída, **When** o usuário olha o arquivo, **Then** o nome segue o padrão `opf-instituicao-<instituição>-slide-<AAAA-MM-DD>.png`.
6. **Given** a biblioteca de imagem indisponível (sem rede), **When** o usuário aciona "Exportar slide", **Then** aparece a mesma mensagem de erro das outras exportações, informando que o CSV continua disponível, e nada é baixado.

### Edge Cases

- Instituição com poucos dados ou sem alguns blocos (por exemplo, sem transmissores ou sem chamadas de API): o slide mostra o estado vazio do bloco, em vez de um espaço em branco ou de uma falha.
- Transmissores em número maior que o espaço: o slide mostra os maiores e informa quantos ficaram de fora, sem texto menor que o mínimo e sem cortar linhas pela metade. "Quais dados busca" nunca é cortado.
- Nome de instituição muito longo: o título quebra em até duas linhas, sem sair do quadro.
- Exportar enquanto a página ainda carrega ou depois de um erro de carregamento: a ação fica indisponível, ou avisa que ainda não há dados, e nunca baixa um slide incompleto.
- Trocar de instituição, comparação, período, unidade ou visão e exportar de novo: o slide reflete sempre o estado atual da tela.
- Exportação em tela estreita (celular): a ação continua acessível com alvo de toque de 44 px, e o slide sai com o mesmo formato 1600×900.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A página "Como opera uma instituição?" MUST oferecer a ação "Exportar slide", que baixa uma imagem PNG de 1600×900.
- **FR-002**: O slide MUST conter, nesta ordem: título (instituição e filtros ativos) e subtítulo (semana dos dados); os quatro indicadores; a evolução e os transmissores empilhados numa coluna, ao lado de "Quais dados busca" em coluna inteira; e o rodapé de fonte com a data dos dados.
- **FR-003**: O slide MUST NOT conter os alertas, a taxa de erro de API nem as chamadas por grupo de API.
- **FR-003a**: O bloco "Quais dados busca" MUST aparecer completo no slide, sem corte nem "+N": todos os grupos de API (visão por grupo) ou todos os endpoints da API escolhida (visão por endpoint). Se algum dia não couber, a exportação avisa em vez de cortar.
- **FR-003b**: O bloco antes chamado "Para que usa os dados" MUST chamar-se "Quais dados busca" na página, nas imagens por bloco e no slide; só o título muda.
- **FR-004**: O slide MUST refletir o estado da tela no momento da exportação: instituição, comparação, período, métrica da evolução, unidade e visão ("Por grupo de API" ou "Por endpoint", com a API escolhida).
- **FR-005**: A exportação MUST funcionar como as demais imagens do painel: mesma moldura, mesma tipografia, mesmo rodapé de fonte, tema ativo respeitado, nome de arquivo no padrão `opf-<aba>-<bloco>-<AAAA-MM-DD>.png` e mesma mensagem de erro quando a biblioteca de imagem não carrega.
- **FR-006**: O slide MUST respeitar o design system e as regras de layout da v2: apenas as cores, o espaçamento e os tamanhos de texto já definidos, texto com pelo menos o tamanho mínimo do design system, contraste mínimo de 4,5:1, sem cortes e sem sobreposição.
- **FR-007**: Os transmissores, quando não cabem no quadro, MUST ser reduzidos aos maiores itens, com indicação de quantos ficaram de fora, em vez de diminuir o texto abaixo do mínimo.
- **FR-008**: A ação MUST ficar na barra de filtros, junto de "Exportar CSV", com alvo de toque de pelo menos 44 px, rótulo e `title` que digam o que ela exporta, e estar indisponível enquanto não houver dados carregados.
- **FR-009**: Nenhuma outra exportação, página, dado ou regra do painel MUST mudar: as imagens por bloco das quatro abas, o CSV e o painel legado saem idênticos aos de antes.
- **FR-010**: A regra de exportação do contrato da interface v2 e da Constituição (§6.8), que hoje prevê imagem por bloco e um único botão de CSV por página, MUST ser emendada para registrar a exportação de página inteira como slide.

### Key Entities *(include if feature involves data)*

- **Slide da instituição**: imagem 16:9 que resume o perfil de uma instituição para uma comparação e um período, montada a partir dos blocos da página, menos alertas, taxa de erro e chamadas por grupo.
- **Estado da tela**: conjunto de escolhas ativas (instituição, comparação, período, métrica da evolução, unidade, visão e API) que o slide reproduz.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% das exportações, o arquivo baixado tem exatamente 1600×900 pixels.
- **SC-002**: Em 100% das exportações, o slide não contém alertas, taxa de erro de API nem chamadas por grupo, contém os demais blocos listados em FR-002 (ou o estado vazio do bloco) e mostra "Quais dados busca" com todos os itens.
- **SC-003**: O analista obtém o slide em um clique e em até 5 segundos depois de a página carregar, em conexão normal.
- **SC-004**: Nas verificações de layout (tema claro e escuro, visões por grupo e por endpoint, instituição grande e pequena), há zero textos abaixo do mínimo do design system, zero contrastes abaixo de 4,5:1 e zero cortes ou sobreposições.
- **SC-005**: Os valores do slide são idênticos aos mostrados na tela para a mesma instituição, comparação, período e unidade (diferença zero).
- **SC-006**: As imagens por bloco das quatro abas, geradas antes e depois da mudança com o mesmo estado, são idênticas pixel a pixel (nenhuma regressão).
- **SC-007**: O analista monta o perfil de uma instituição para uma apresentação em menos de 1 minuto, contra os vários cliques e a montagem manual de hoje.

## Assumptions

- O slide é uma imagem; exportar para um arquivo de apresentação editável (PPTX) está fora do escopo.
- Os dados do slide vêm do que a página já carregou; não exige nova coleta, nova API nem mudança de base.
- A taxa de erro de API e as chamadas por grupo saem do slide só para dar espaço a "Quais dados busca" completo; continuam na página e no CSV.
- A ação de página inteira exige emendar a regra "imagem por bloco, um CSV por página" (FR-010), porque é uma exportação nova, e não uma exceção implícita.
- Só os transmissores podem ser cortados no slide (saem do espaço disponível em 1600×900 com o texto no tamanho mínimo). "Quais dados busca" tem no máximo 6 grupos ou 7 endpoints na base atual e cabe inteiro.
- Como nas imagens por bloco, o slide usa as regras de layout responsivo da página aberta: em celular (≤ 720 px) as colunas das listas ficam mais estreitas, com o mesmo formato 1600×900 e o texto ≥ 12 px.
- Fora do escopo: slides das outras abas, várias lâminas por exportação, edição do conteúdo do slide, mudança nos alertas, na taxa de erro, no CSV ou em qualquer dado.

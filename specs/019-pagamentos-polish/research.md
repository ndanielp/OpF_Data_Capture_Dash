# Research: Polimento do tema Pagamentos

Decisões técnicas do plano. As regras de dado da feature 018 ([research](../018-pagamentos-dash/research.md)) continuam valendo.

## R1. Seletor de mês: onde o mês é calculado

- **Decision**:
  - **Matriz, Evolução e Instituição**: o servidor já devolve todos os meses num pedido (`/flows`, `/institution`), e o mês escolhido é só estado do navegador. Trocar de mês não chama o servidor.
  - **Quem lidera?**: ganha o parâmetro `month=AAAA-MM`. O ranking do mês usa os totais mensais normalizados para 30 dias; o crescimento compara com o mês anterior.
  - **O que mudou?**: ganha `month=AAAA-MM`.
  - O valor "Últimas 4 semanas" (`month` ausente) mantém a janela de hoje.
- **Rationale**: SC-004 (até 1 s) fica folgado sem ida ao servidor nas abas de série. No ranking, o servidor já tem tudo na memória e devolve em menos de 50 ms.
- **Alternatives**: mandar a série completa do ranking para o navegador (são ~80 instituições × 10 meses × 4 números; possível, mas duplicaria regras de fatia, falha e fixadas no cliente).

## R2. Mudanças de um mês

- **Decision**: as mudanças confirmadas no mês m são as do FR-035 da 018 com W = a última semana de m na base (condição em W e em W−1, mesma direção). "Em observação" só para o último mês da base. A contagem da barra de meses calcula isso para cada um dos meses mostrados (até 12) e fica em cache pela base.
- **Rationale**: na base de 30/10/2026, 12 semanas de condições levam 0,22 s; 10 meses × 2 semanas ≈ 0,4 s, uma vez por versão da base. A última semana do mês é a mesma referência que "Outubro/2026" usa hoje.
- **Alternatives**: contar condições confirmadas em qualquer semana do mês (a mesma mudança apareceria 4–5 vezes no mês).

## R3. Recorte por inclusão

- **Decision**:
  - `/flows` aceita `rows=uuid,…` e `cols=uuid,…`, além de `size`.
  - Sem lista, o lado usa as `size` maiores, como hoje. Com lista, as linhas ou colunas são as escolhidas, na ordem dada, mais "Outras" com a contagem de quantas soma (`others_count`).
  - "Só as escolhidas" (FR-012) é feito no navegador: com escolhas num lado, a soma deixa de fora a linha ou coluna "Outras" daquele lado.
  - A Evolução pede `/flows` com as escolhas dos dois lados. A Matriz pede com as linhas e colunas dela (escolhidas ou as maiores).
- **Rationale**: um pedido por mudança de escolha, sem lógica nova de soma no servidor. "Pares entre as escolhidas" (dois lados) sai de graça.
- **Alternatives**: filtrar no servidor e devolver só os totais (cada passo da Evolução precisa das células por linha e coluna para "quem puxou").

## R4. Contrapartes escolhidas na Instituição

- **Decision**: `/institution/{uuid}` aceita `counterparts=uuid,…`, com o mesmo modelo do R3:
  - **Sem escolhas** ("todas"): as linhas são as 8 maiores contrapartes mais "Outras". Os passos somam tudo.
  - **Com escolhas**: as linhas são as escolhidas, na ordem dada, mais "Outras" (com `others_count`). Os passos deixam "Outras" de fora da soma.
- **Rationale**: o mesmo recorte e o mesmo componente da Evolução e da Matriz, e uma instituição pequena vira linha própria ao ser escolhida (FR-023).

## R5. Busca de instituição (todas, por volume)

- **Decision**:
  - `/meta` de pagamentos devolve, para cada instituição, `volume: {ini: [por mês], det: [por mês]}`, com as transações por 30 dias, alinhado a `months`.
  - `V2.openInstitutionPicker` ganha opções: `all` (lista inteira, com rolagem, em vez de 8), `sort` (função de ordem quando a busca está vazia) e `detail` (texto à direita do nome, ex.: "8,69 mi · iniciadora").
  - Os padrões ficam como hoje, então as abas do tema Dados não mudam.
- **Rationale**: ~80 instituições × 10 meses × 2 papéis cabe com folga no `/meta` (alguns KB). Estender o seletor existente evita um segundo componente de busca (Princípio I).

## R6. Estado entre abas e URL

- **Decision**:
  - `sessionStorage['opf:v2:filters']` ganha `pay_month`, `pay_r` e `pay_c` (listas de uuid), escritos sem apagar os outros campos.
  - Cada aba lê a URL primeiro (`?month=…&r=…&c=…`), depois o `sessionStorage`, e mantém a URL atualizada com `history.replaceState`.
  - A aba da instituição continua com `uuid` e `role` na URL, e guarda as contrapartes escolhidas em `cp`. Elas não são compartilhadas com as outras abas, porque o lado delas depende do papel.
- **Rationale**: FR-014 e SC-005. Mesmo padrão de persistência do tema Dados (Princípio III).
- **Alternatives**: um "link de compartilhar" (um passo a mais para o usuário).

## R7. Dica ao passar o mouse nas barras e linhas

- **Decision**: um elemento de dica único, criado por `shell.js` (`V2.pay.tip`), aberto por `mouseenter` e `focus` em alvos com `data-tip` (barra do mês, ponto da linha).
  - Cada barra vira um `<button>`: clicar escolhe o mês (FR-004), e o foco por teclado mostra a dica (FR-045).
  - As linhas de falha ganham `<circle>` por mês, com `data-tip`, e uma faixa invisível por mês para o mouse.
- **Rationale**: sem biblioteca nova. Botões dão teclado e nome acessível de graça.
- **Alternatives**: Chart.js (está nas abas do Dados, mas as barras e linhas do tema Pagamentos são HTML/SVG; trocar agora seria refazer as 5 abas).

## R8. Botão sobre a célula da matriz (P12)

- **Decision**: a célula volta a ser um único `<button>` com o número e a cor, e a exportação de imagem passa a preservar os botões marcados com `data-keep`. Ela continua removendo os botões de ação. Em `V2.exportImage`, o seletor `button` vira `button:not([data-keep])`.
- **Rationale**: o traço sobre os números vem do botão transparente posicionado por cima. Um botão só, que o exportador mantém, resolve P12 e o problema que levou ao botão transparente (a grade sumir do PNG).

## R9. Limites e ordem

- **Decision**:
  - Matriz: até 12 linhas e 12 colunas (422 acima disso; a busca avisa antes).
  - Ranking: `limit` aceita até 500; "todas" envia 500.
  - A ordem das escolhidas na matriz é a da escolha; o padrão (as maiores) segue o volume.

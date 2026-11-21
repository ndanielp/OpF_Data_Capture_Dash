# Requisitos para especificar: polimento do tema Pagamentos

**Origem**: avaliação de usabilidade em 2026-11-20, navegando as 5 abas em `localhost:8000` como quem quer explorar, mais três pedidos do responsável do produto:

1. Ver informações de um **mês específico**.
2. Trocar "excluir da seleção" por **filtrar e ir incluindo**.
3. Poder escolher **qualquer instituição**, não só as 8 maiores.

Este arquivo é a entrada para o `/speckit-specify` da próxima feature. Os requisitos estão em linguagem de produto; as notas "Hoje" descrevem o que existe no commit `152a4a8`.

## Problemas encontrados

| # | Onde | Problema | Origem |
|---|---|---|---|
| P1 | Quem lidera? | Só existe a janela das últimas 4 semanas; não dá para ver o ranking de um mês | Pedido 1 |
| P2 | Como evolui?, Instituição | As barras mensais não respondem a clique nem a hover. Para saber o valor de jun por API, é preciso exportar o CSV | Pedido 1 |
| P3 | Como evolui? (passo 2), Instituição (passo 2) | "Quem puxou" e "vs jan" comparam sempre o primeiro e o último mês; não há como comparar dois meses escolhidos | Pedido 1 |
| P4 | O que mudou? | Só o último mês. O tema Dados tem a barra de meses com o histórico; aqui não há | Pedido 1 |
| P5 | Evolução, Instituição | O recorte abre com tudo ligado e o usuário vai riscando. Riscado parece desabilitado, e "Outras" é um bloco que não se abre | Pedido 2 |
| P6 | Evolução, Matriz, Instituição | Só as 8 maiores de cada lado podem ser escolhidas; o resto fica escondido em "Outras" | Pedido 3 |
| P7 | Matriz | Linhas e colunas são sempre as 8 (ou 4) maiores; não dá para montar a matriz das instituições de interesse | Pedido 3 |
| P8 | Busca de instituição | Com a busca vazia aparecem 8 nomes em ordem alfabética, sem papel nem volume, e não há como percorrer a lista | Pedido 3 |
| P9 | Quem lidera? | Só o Top 10; não há "ver mais" | Avaliação |
| P10 | Linhas de falha | Sem pontos nem valores; só se lê pelo eixo. A legenda mostra séries que não estão no gráfico (Iniciação, para quem só usa o Automático) | Avaliação |
| P11 | Matriz | Os nomes dos meses não ficam alinhados com as posições do controle deslizante | Avaliação |
| P12 | Matriz | Algumas células mostram um traço sobreposto ao número (ex.: PicPay e Nubank na linha Google Pay); parece vir do botão transparente sobre a célula | Avaliação (bug) |
| P13 | Evolução, O que mudou? | "Exportar CSV" cai numa linha própria, no meio da barra de filtros | Avaliação |
| P14 | Todas | A escolha feita numa aba (instituições, mês) se perde ao ir para outra | Avaliação |
| P15 | Quem lidera? | O 4º indicador (Iniciação × Automático) fica sozinho numa segunda linha a 800 px | Avaliação |
| P16 | O que mudou? | 23 mudanças numa lista só, sem agrupar por instituição e sem busca | Avaliação |

## Requisitos

### A. Mês específico (P1–P4)

- **R-A1** Todas as abas de pagamento têm um seletor de **mês** na barra de filtros, com os meses da base e "Últimas 4 semanas" (padrão de Quem lidera? e O que mudou?). A escolha vale para a aba toda e aparece no título dos cards.
- **R-A2** Quem lidera?: com um mês escolhido, o ranking, os indicadores, a fatia e a falha são daquele mês (por 30 dias). O crescimento compara com o mês anterior.
- **R-A3** Barras mensais (Evolução passo 1, Instituição passo 1):
  - Passar o mouse ou focar uma barra mostra o mês, o total, o valor por API e a falha por API.
  - Clicar escolhe o mês: os indicadores do lado mostram o mês escolhido, e não mais "out" fixo.
  - O mês escolhido fica destacado na barra e na fatia mensal (passo 3).
- **R-A4** "Quem puxou o crescimento?" (Evolução) e a tabela de contrapartes (Instituição) comparam **dois meses escolhidos** ("de" e "até"); padrão: primeiro e último mês.
- **R-A5** Linhas de falha: pontos em cada mês, rótulo do valor no último ponto e no mês escolhido, e dica com o valor ao passar o mouse.
- **R-A6** O que mudou?: barra de meses com a contagem de mudanças por mês, como no tema Dados. Clicar num mês mostra as mudanças confirmadas naquele mês. "Em observação" só aparece no mês mais recente.
- **R-A7** Matriz: a linha do tempo continua. O mês escolhido nela é o mesmo do seletor de mês (R-A1).

### B. Filtrar incluindo (P5, P13, P14)

- **R-B1** O recorte deixa de ser "tudo ligado, ir riscando". A barra mostra:
  - "Iniciadoras: todas" e "Detentoras: todas", cada um com um botão "+ Adicionar" que abre a busca.
  - Cada instituição adicionada vira um chip com ×.
  - Com pelo menos um chip, a análise considera **só** as instituições escolhidas daquele lado. "Limpar" volta a "todas".
- **R-B2** Os gráficos com séries por instituição mostram uma série por instituição escolhida, e mais "Demais" quando o lado está em "todas". Isso vale para o passo 2 da Evolução, as contrapartes da Instituição e a matriz.
- **R-B3** As frases de leitura citam o recorte ("Entre Google Pay e Nubank, …") quando há instituições escolhidas.
- **R-B4** As instituições escolhidas e o mês ficam guardados entre as abas de pagamento (`sessionStorage`, campos próprios) e na URL, para dar para compartilhar.
- **R-B5** "Exportar CSV" fica sempre à direita da primeira linha da barra de filtros, em todas as abas.

### C. Qualquer instituição (P6–P8, P9)

- **R-C1** Qualquer instituição que aparece em pagamentos pode ser escolhida no recorte, como linha ou coluna da matriz e como contraparte na aba da instituição. "Top 8" deixa de ser um limite e passa a ser só o ponto de partida.
- **R-C2** Matriz:
  - Linhas e colunas partem das 8 maiores. O usuário adiciona e remove linhas e colunas pela busca, até 12 de cada lado.
  - "Outras" continua como a última linha e a última coluna, e soma o resto.
  - "Top 4 / Top 8" vira "Maiores: 4 · 8 · 12", e "Minha seleção" aparece quando houver instituições escolhidas.
- **R-C3** Busca de instituição:
  - Com a busca vazia, lista as instituições do papel por volume (maior primeiro), com o volume do último mês e o papel ("Iniciadora", "Detentora" ou os dois).
  - A lista rola e mostra todas, não só 8.
  - A busca ignora acento e caixa.
- **R-C4** Instituição: as contrapartes partem das 8 maiores, e o usuário pode adicionar qualquer outra pela busca; o rótulo "Outras" mostra quantas instituições soma.
- **R-C5** Quem lidera?: "Mostrar: 10 · 25 · todas". As fixadas continuam aparecendo mesmo fora do corte.

### D. Leitura e acabamento (P10–P12, P15, P16)

- **R-D1** Legendas só listam séries presentes no gráfico.
- **R-D2** Os nomes dos meses da matriz ficam alinhados com as posições da linha do tempo. A linha do tempo pode virar um controle de meses clicáveis, sem trilha.
- **R-D3** Nenhum elemento sobreposto altera a leitura do número da célula (corrigir P12).
- **R-D4** Indicadores de Quem lidera? em 4 colunas a partir de 1000 px e em 2 × 2 abaixo disso, sem card sozinho numa linha.
- **R-D5** O que mudou?: agrupar as mudanças por instituição (uma linha por instituição, com as mudanças dela) e uma busca por nome, como no tema Dados.

## Fora do escopo desta rodada

- Comparar duas instituições lado a lado.
- Exportar slide.
- Alertas de pagamento gravados em tabela (continuam calculados a cada pedido).

## Impacto técnico esperado (para o plano)

- **`/flows`** aceita listas de linhas e colunas (`rows=uuid,…&cols=uuid,…`) além de `size`. O mês e os dois meses de comparação continuam saindo do mesmo pedido, que já traz todos os meses.
- **`/ranking`** aceita `month=AAAA-MM` e `limit` até "todas".
- **`/institution`** aceita `counterparts=uuid,…`.
- **`/changes`** aceita `month` e devolve a contagem por mês.
- **`/meta`** de pagamentos traz o volume do último mês por instituição e papel, para a busca ordenar.
- **`shell.js`**:
  - o recorte por inclusão vira um componente comum (`V2.pay.picker`);
  - o seletor de mês e a dica das barras e linhas passam a ser compartilhados;
  - o estado entre abas vai para `opf:v2:filters` (`pay_month`, `pay_r`, `pay_c`).
- **Constituição**: nenhuma emenda prevista; a barra de filtros e o "Exportar CSV" já seguem §6.8.

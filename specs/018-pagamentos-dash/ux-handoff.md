# UX handoff: Tema Pagamentos

**Feature**: [spec.md](spec.md) · **Protótipo**: [canvas "Dash 2.0 — Pagamentos"](https://claude.ai/artifact/1g4DQVB9Bsmx3Etz7srrRs) (privado; compartilhar pelo menu Share)
**Validado em**: 2026-11-20, depois de 18 versões revisadas com o responsável do produto.

O protótipo é a referência visual e de comportamento. Os números dele saíram da base real (4 semanas até 30/10/2026), mas na implementação tudo vem da API; as frases de leitura são montadas a partir dos números, nunca escritas à mão. Os alertas do protótipo eram ilustrativos; as regras deles estão em [spec.md](spec.md) (FR-030 a FR-036).

## Onde fica

- Um seletor **Dados | Pagamentos** no cabeçalho, à direita de "Dados até …" e antes do botão de tema claro/escuro. "Dados" é o painel de hoje; "Pagamentos" troca as abas.
- Abas do tema Pagamentos, nesta ordem:

| # | Aba | Rota | Quadro do canvas |
|---|---|---|---|
| 1 | Quem lidera? | `/v2/pagamentos` | Main |
| 2 | Quem paga com quem? | `/v2/pagamentos/matriz` | Matriz |
| 3 | Como evolui? | `/v2/pagamentos/evolucao` | Evolucao |
| 4 | O que mudou? | `/v2/pagamentos/mudancas` | Mudancas |
| 5 | Como opera uma instituição? | `/v2/pagamentos/instituicao` | Instituicao |

- Trocar de tema leva à mesma pergunta no outro tema ("Quem paga com quem?" não existe em Dados e leva a "Quem lidera?").
- Mesma casca das outras abas (Constituição §6.8): `.v2-filterbar` primeiro, depois o título da página e os cards; cada card de conteúdo tem título, subtítulo, rodapé com regra e fonte e "Copiar como imagem"; "Exportar CSV" fica à direita da barra de filtros.

## Vocabulário (igual em todas as telas)

| Termo | Significado |
|---|---|
| Transação | Resposta 200 em **Criar iniciação** (endpoint 65 da API `payments` e 129 da `automatic-payments`) |
| Iniciação de Pagamento | API `payments`. Cor `#1F4FD1` |
| Pagamento Automático | API `automatic-payments`. Cor de barra `#9B8FE3`, cor de linha `#6B5BC4` (mais escura, para linha fina) |
| Falha | 500 ÷ (200 + 500) em Criar iniciação. Sempre com a nota "inclui 4xx e novas tentativas" por perto |
| Iniciadora | Coluna `receptor` da tabela de pagamentos (quem inicia: ITP, app) |
| Detentora | Coluna `transmitter` (banco da conta que paga) |
| Por 30 dias | Últimas 4 semanas × 30/28; nos meses, soma do mês ÷ semanas com dado × 30/7 |
| JSR | Jornada sem Redirecionamento. Só aparece como detalhe recolhido, nunca como bloco principal |

Cores de falha e perda: `--down` do tema. Falha alta (≥ 20%) vai numa pílula `.pill-bad` (fundo `--down-bg`).

## 1. Quem lidera? (`/v2/pagamentos`)

- Barra de filtros: **Ranking de** (Iniciadoras | Detentoras), **API** (Todas | Iniciação de Pagamento | Pagamento Automático), **Fixar / excluir** (chips como no Dados, "+ instituição"), "Exportar CSV".
- Título "Quem lidera a iniciação de pagamentos?" e subtítulo "Transações aceitas (Criar iniciação com sucesso) nas últimas 4 semanas, normalizadas para 30 dias."
- 4 cards de indicador (sem ações): Transações · 30 dias (com "N iniciadoras · M detentoras"); Iniciação de Pagamento (valor, fatia, falha); Pagamento Automático (valor, fatia, falha em pílula se ≥ 20%, "inclui novas tentativas"); Iniciação × Automático (barra dividida e a variação da fatia em pp contra as 4 semanas anteriores).
- Card do ranking: "Top 10 iniciadoras (quem inicia o pagamento)" ou "Top 10 detentoras (banco da conta que paga)". Colunas: #, nome (link para a aba da instituição no papel escolhido), barra dividida IP/PA, Volume, Fatia, Falha Inic., Falha Autom., Cresc. (vs 4 semanas anteriores). Fixadas ficam com fundo `--pinned-bg`. Legenda com as duas cores e "≥ 20% falha alta".

## 2. Quem paga com quem? (`/v2/pagamentos/matriz`)

- Barra: **Cor da célula** (Volume | Falha | Crescimento), **API** (Todas | Iniciação | Automático), **Tamanho** (Top 8 | Top 4), "Exportar CSV". Abaixo de 760 px de largura a matriz passa sozinha para Top 4.
- Linha do tempo: controle deslizante de meses, botões ‹ ›, nomes dos meses sob a trilha e "Reproduzir" (avança a cada 1,2 s e para no último mês). Abre no último mês.
- Matriz: linhas = iniciadoras (Top N + "Outras iniciadoras"), colunas = detentoras (Top N + "Outras detentoras"), por 30 dias no mês escolhido; total por linha e por coluna. Célula vazia só quando o valor é 0 ("—"). Volume: escala sequencial do azul; Falha: escala do laranja; Crescimento: contra o mês anterior, divergente (perda `--down`, ganho `--up`). O valor fica escrito na célula.
- Clicar numa célula abre o painel ao lado: par "Iniciadora → Detentora", transações, falha, divisão IP/PA, fatia na linha e na coluna, variação contra o mês anterior.
- Card "O que a matriz mostra": 3 frases geradas dos dados (maior par; par com mais falha entre os que têm ao menos 1% do volume; par que mais cresceu desde o primeiro mês).

## 3. Como evolui? (`/v2/pagamentos/evolucao`)

Lida de cima para baixo como uma história; cada passo tem número, título-pergunta e uma frase de leitura em destaque.

- **Recorte da análise** (no lugar da barra de filtros, com "Exportar CSV" à direita): chips das 8 maiores iniciadoras + "Outras iniciadoras" e das 8 maiores detentoras + "Outras detentoras". Chip ligado = preto; desligado = riscado. "todas" religa o grupo. Uma linha diz o que está fora da análise.
- **1 Quanto cresceu?**: transações em out (e jan), por API; barras empilhadas por mês (IP embaixo, PA em cima) com o total escrito.
- **2 Quem puxou o crescimento?**: alternador por iniciadora | por detentora; barras divergentes da variação do primeiro ao último mês (perda à esquerda, ganho à direita).
- **3 Como mudou o mix?** e **4 A qualidade acompanhou?** lado a lado: fatia da IP por mês; linhas de falha por API por mês, eixo ajustado ao maior valor.
- **Detalhe · só Jornada sem Redirecionamento (JSR)**, rodapé com borda tracejada: uma linha com a conversão do vínculo no último mês e no primeiro (ecossistema, não segue o recorte) e o botão "Ver funil do vínculo", que abre o funil compacto (4 degraus em trapézio, "↓ N% passam" entre eles) e a contagem de vínculos encerrados.

## 4. O que mudou? (`/v2/pagamentos/mudancas`)

- Barra: **Tipo de mudança** (Todas | Volume | Falha | Conversão), **Papel** (Todos | Iniciadoras | Detentoras), a nota do piso, "Exportar CSV".
- Card do mês da última semana ("Outubro/2026", subtítulo "4 semanas até dd/mm vs 4 anteriores"): linhas com selo (Volume ↑ verde, Falha ↑ / Volume ↓ / Conversão ↓ laranja), instituição (link) com papel e API, frase do que aconteceu, "Antes → agora".
- Card "Em observação" (selo amarelo): condição vista na última semana, aguardando a semana de confirmação.
- Vazio: "Nenhuma mudança deste tipo no mês."

## 5. Como opera uma instituição? (`/v2/pagamentos/instituicao`)

- Barra: **Instituição** (botão com busca no catálogo de pagamentos), **Papel em pagamentos** (chips Iniciadora | Detentora; o papel sem dados fica desabilitado), "Exportar CSV". Segunda linha: chips das contrapartes (as 8 maiores + "Outras"), como o recorte da Evolução. Link "também é receptora de dados: ver no tema Dados →" quando a instituição existe no Dados.
- Título "<Nome> · como iniciadora|detentora" e subtítulo do papel.
- **1 Quanto opera?**: transações em out e jan, fatia do ecossistema e posição entre as do papel; barras empilhadas por mês.
- **2 Em quais detentoras opera? / Quais iniciadoras usam contas <Nome>?**: linhas com barra IP/PA do último mês, volume e variação desde o primeiro mês (verde/laranja).
- **3 Com que mix?** e **4 Com que qualidade?** lado a lado: fatia da IP por mês (com a do ecossistema na frase); linhas de falha por API com a linha tracejada do Automático no ecossistema; lista "Onde falha" (5 contrapartes com mais falhas no último mês: parte das falhas e taxa).
- Rodapé tracejado: JSR do papel (conversão e autorização contra o ecossistema, "Ver funil do vínculo") e "Detalhe operacional · consultas por iniciação".

## Removido durante a revisão (não implementar)

- Funil de pagamento JSR (138 → 140): "não diz nada".
- "Fatia sem redirecionamento" (140 ÷ 63) em qualquer tela.
- Funil em destaque na Evolução e na Instituição.
- Filtro de período nas abas Evolução e Instituição (mostram sempre os meses da base, até 12).

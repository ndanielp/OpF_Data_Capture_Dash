# Research — Dashboard 2.0

Decisões técnicas tomadas para cumprir a spec, com a medição que embasou cada uma quando houve. Base de referência: `consents.db` local em 2026-10-05 (dados até 28/08/2026; 139 semanas de `api_requests`, 5,65 mi linhas).

## Decisão 1 — Onde o 2.0 mora e como convive com o legado

- **Decision**: O 2.0 fica no mesmo serviço FastAPI, em páginas novas sob `/v2` (`/v2`, `/v2/evolucao`, `/v2/mudancas`, `/v2/instituicao`), com HTML/CSS/JS próprios em `dashboard/gui/v2/` e endpoints novos sob `/api/v2/*`. O legado (`/`, `/profile`, `/active-consents` e todos os endpoints atuais) não muda, exceto um link "Dashboard 2.0" no titlebar.
- **Rationale**: Atende a clarificação (legado no endereço principal; 2.0 em endereço próprio até a virada). O mesmo serviço reaproveita base, cache, deploy e `resolve_institution_group`. Endpoints novos evitam mexer na forma das respostas atuais (gate do PR: não quebrar endpoints existentes).
- **Alternatives considered**: (a) reaproveitar os endpoints do legado no 2.0 — rejeitado: não entregam ritmo, Top N com fixadas/excluídas, multiplicador nem taxa de erro, e mudar a forma deles quebraria o legado; (b) serviço Cloud Run separado — rejeitado: duplica deploy e download da base sem ganho.

## Decisão 2 — Erros de API (status 500) e taxa de erro precisam de uma pré-agregação nova

- **Decision**: Nova tabela `api_status_weekly` (semana × receptor × transmissor × status, sem a API `consents`), reconstruída por `scrapers.refresh_api_status_weekly()`, chamada no fim da coleta (como `refresh_api_group_weekly`) e por `compute_signals.py`.
- **Rationale**: Princípio IV proíbe agregações multi-dimensão ad hoc no caminho quente. `api_group_weekly` só tem status 200. Medição: agrupar `api_requests` por semana × receptor × transmissor × status dá **167.522 linhas** e leva **~35 s** só a consulta; o rebuild completo (apagar + gravar) mediu **78 s** em `compute_signals.py` (2026-10-05). A leitura por semana fica trivial (50–430 ms por endpoint, 1,3 s na primeira chamada fria). Serve ao ranking de API com "Status: Erros/Todas", à taxa de erro da instituição e à taxa de erro por transmissor.
- **Alternatives considered**: agregação só por receptor × status (7.733 linhas, 20 s) — rejeitada: não atende "taxa de erro por transmissor" (FR-039); consultar `api_requests` direto — rejeitado (Princípio IV; 20–35 s por consulta).

## Decisão 3 — "Em observação" é calculado no data-loader

- **Decision**: `compute_signals.py` passa a gravar, na mesma transação dos alertas, a tabela `behavior_watch`: condições de API (mesma regra 4v4 ajustada pelo ecossistema) vistas na semana mais recente que ainda não completaram as 2 semanas de confirmação.
- **Rationale**: É o mesmo cálculo das regras de API, que mora em `signals.py`; o dashboard não pode reproduzir a regra sem duplicar lógica nem escrever no banco (Princípio V).
- **Alternatives considered**: recalcular no dashboard a partir de `api_group_weekly` — rejeitado: duplicaria a regra em dois componentes, com risco de divergência.

## Decisão 4 — Piso de 30 mil medido em consentimentos únicos

- **Decision**: Em `detect_consent_changes`, a elegibilidade usa os consentimentos únicos da semana-base do receptor (`volume_of[(uuid, semana_anterior)] ≥ 30.000`) para as duas métricas. Teste novo cobre o caso de ativos ≥ 30 mil com únicos < 30 mil.
- **Rationale**: FR-032. Na base, tira 5 dos 25 alertas de ativos (Geru, Unicred, Stone, Cielo), todos de instituições com menos de 30 mil únicos. Afeta também o card do legado, o que é desejado (spec, Assumptions).
- **Alternatives considered**: piso próprio mais alto para ativos (ex.: 50 mil) — rejeitado pelo responsável do produto.

## Decisão 5 — Ritmo por dia

- **Decision**: Consentimentos: `(valor na semana S − valor na semana S−4) ÷ 28`, e `% ao dia = (S ÷ S−4 − 1) ÷ 28`. Comparação: o mesmo cálculo de S−4 contra S−8; seta ↑/↓ se a razão entre os dois ritmos sai de [0,9; 1,1]. Se a semana S−4 não existe para a instituição, usa a observação anterior mais próxima e divide pelos dias reais entre elas. API: média de chamadas por dia nas semanas S−3..S (soma ÷ 28) contra S−7..S−4.
- **Rationale**: Regras validadas nos mocks com a base real (ex.: ecossistema PF +264,6 mil/dia contra +250,1 mil). Usar a observação anterior evita que uma semana sem coleta zere o ritmo (mesmo princípio da feature 010).
- **Alternatives considered**: regressão linear sobre 4 semanas — rejeitada: mais difícil de explicar no rodapé e de conferir à mão.

## Decisão 6 — Crescimento no período

- **Decision**: Consentimentos: semana final do período contra a primeira semana do período. API: média de 4 semanas no fim contra média de 4 semanas no início. Formatação: estreia dentro do período → `{"kind":"debut","month":"2025-10"}`; sem valor no início → `"no_base"`; crescimento > +300% → `"multiplier"` (valor = razão); senão `"pct"`. A formatação vem pronta da API para CSV e tela mostrarem o mesmo.
- **Rationale**: FR-018; elimina os "+9934%" (Klavi PJ partiu de ~300).
- **Alternatives considered**: esconder crescimento acima de um limite — rejeitado: o dado é verdadeiro, só precisa de outra forma de leitura.

## Decisão 7 — Fixar e excluir instituições

- **Decision**: As listas de fixadas e excluídas ficam no navegador (`localStorage['opf:v2:ranking']`) e vão para o endpoint como parâmetros (`pinned`, `excluded`, por UUID). O servidor monta o Top N já aplicando as regras (excluídas saem, a próxima completa N, fixadas fora do corte voltam com `below_cut: true`, posição sempre a do ecossistema). Bradesco é fixado no primeiro acesso, resolvido pelo nome na lista de instituições de `/api/v2/meta`.
- **Rationale**: FR-020/021. Montar no servidor garante que tela e CSV usem a mesma lista; guardar no navegador dispensa contas (spec, Assumptions).
- **Alternatives considered**: montar o corte no cliente a partir do ranking completo — rejeitado: duplicaria a lógica no JS e no CSV.

## Decisão 8 — Visão mensal e semanas sem coleta

- **Decision**: Mensal = valor da última semana com dado de cada instituição dentro do mês (o mês fica vazio se não houver nenhuma). Semanal = valor da semana ou `null`; o gráfico usa `spanGaps: false` e nunca preenche com zero. Participação mensal = valor ÷ soma dos valores de fim de mês de todas as instituições (cada uma na sua última semana com dado; ajuste na implementação da US5 — assim as participações do mês somam 100% e a lacuna de uma instituição não infla as outras). Ganho/perda em pp do período usa a foto da semana inicial e da final, com lacuna de até 3 semanas preenchida pela observação anterior.
- **Rationale**: FR-035 e SC-007. Corrige na origem o "falso colapso do Belvo em 07/08" do legado, que preenche semanas ausentes com 0.
- **Alternatives considered**: última semana do calendário do mês — rejeitado: uma instituição sem coleta naquela semana sumiria do mês inteiro.

## Decisão 9 — Oscilação e reincidência são apresentação

- **Decision**: Calculadas no endpoint `/api/v2/changes` a partir de `behavior_signals`: oscilação = dois alertas de consentimento de sinais opostos, mesma instituição e métrica, em semanas consecutivas; reincidência = instituição com alerta em meses consecutivos até o mês escolhido (contagem retroativa).
- **Rationale**: Não mudam a detecção (a tabela continua com os dois alertas); são só agrupamento para leitura (FR-028/029). Contagem de alertas por mês continua honesta (12 em agosto).
- **Alternatives considered**: gravar oscilação como tipo novo no data-loader — rejeitado: mudaria a contagem e o card do legado.

## Decisão 10 — Cores e rótulos dos grupos no 2.0

- **Decision**: Nova constante `GROUP_COLORS_V2` em `services/constants.py` (neo_banks `#5B2BC4`, itps `#1F8FD6`, incumbentes `#E8913A`, outros `#A3ABBA`) e `GROUP_LABELS_V2` ("Neobancos", "ITPs", "Incumbentes", "Outros"), servidas por `/api/v2/meta`. O legado continua com `GROUP_COLORS`.
- **Rationale**: Princípio III exige cores vindas de `constants.py`. A paleta aprovada no canvas foi escolhida para tema claro, com luminosidades diferentes entre os grupos (legível em print e para daltônicos); a paleta atual foi feita para tema escuro e mudar a do legado alteraria telas que não fazem parte do escopo.
- **Alternatives considered**: reaproveitar `GROUP_COLORS` — rejeitado: azul-marinho e rosa sobre branco não seguem a paleta aprovada.

## Decisão 11 — Exportar imagem e CSV no navegador

- **Decision**: CSV gerado no cliente a partir do mesmo JSON que desenhou o bloco. Imagem: o bloco é clonado num quadro 16:9 (1600×900) com título, métrica, data, filtro e fonte, e rasterizado com a biblioteca `html-to-image` (via CDN, no mesmo padrão do Chart.js do legado); gráficos Chart.js entram pela própria imagem do canvas.
- **Rationale**: FR-011/012 sem servidor de renderização. Chart.js sozinho não exporta tabelas HTML.
- **Alternatives considered**: renderizar PNG no servidor (Playwright/headless) — rejeitado: pesado para o Cloud Run e o dashboard não tem browser; desenhar cada bloco em Canvas 2D à mão — rejeitado: duplicaria o layout de cada bloco.
- **Impacto constitucional**: biblioteca nova de frontend → listada na emenda (Stack Constraints).

## Decisão 12 — Frontend sem bundler, com casca compartilhada

- **Decision**: `gui/v2/shell.js` monta cabeçalho, abas, barra de filtros, estado compartilhado (`sessionStorage['opf:v2:filters']`), preferências (`localStorage`), tema e exportação; cada página (`index.html`, `evolucao.html`, `mudancas.html`, `instituicao.html`) só tem seus blocos. CSS em `gui/v2/v2.css` com tokens próprios (claro padrão, escuro opcional). Abas ainda não entregues mostram aviso e link para a página equivalente do legado.
- **Rationale**: Stack fixa (JS puro, sem bundler). Uma casca compartilhada por 4 páginas é o caso de 3+ usos do Princípio I. O legado repete o shell em cada HTML — o 2.0 evita isso desde o início.
- **Alternatives considered**: página única com troca de abas por JS — rejeitado: cada aba com endereço próprio facilita favoritos e o link "abrir perfil".

## Decisão 13 — Desempenho

- **Decision**: Endpoints `/api/v2/*` com `TTLCache` (como `of_analytics`), chave por parâmetros; consultas só sobre `unique_consents` (4,6 mil linhas), `active_consents` (110 mil), `api_group_weekly`, `api_status_weekly` (167 mil) e `behavior_signals`. Meta: < 500 ms p95 (Princípio IV) e aba completa em < 3 s (SC-006).
- **Rationale**: Todas as fontes são pequenas ou pré-agregadas; o cálculo de Top N e ritmo é pandas em memória.
- **Alternatives considered**: nova tabela pré-calculada de rankings — rejeitado: as fontes já são pequenas e fixar/excluir varia por usuário.

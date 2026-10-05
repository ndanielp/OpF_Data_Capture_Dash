---
description: "Task list for 011-dashboard-v2"
---

# Tasks: Dashboard 2.0

**Input**: Design documents from `/specs/011-dashboard-v2/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/v2-api.md, contracts/v2-ui-shell.md, quickstart.md

**Design de referência**: canvas https://claude.ai/artifact/LZivcKNMg2z43daC2arfWv, página "Versão final — para aprovação" (quadros `FinalLideranca`, `FinalLiderancaAtivos`, `FinalLiderancaApi`, `FinalMudancas`, `FinalInstituicao`, `FinalEvolucao`). Layout, textos e cores das telas seguem esses quadros e `contracts/v2-ui-shell.md`.

**Tests**: Incluídos. A Constituição (Princípio II) exige:
- teste de integração em SQLite real para toda escrita nova no banco;
- teste HTTP (caminho feliz + erro) para todo endpoint novo;
- validação manual no navegador para toda mudança de tela.

**Organization**: As tarefas estão agrupadas por user story da spec:
- US1: Quem lidera? (P1)
- US2: O que mudou? (P2)
- US3: Exportação para slides (P2)
- US4: Instituição (P3)
- US5: Evolução (P3)

Cada fase de história é um PR próprio contra `main` (plan.md, "Entrega por fases").

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: US1–US5

## Path Conventions

- **Escrita no banco:** só `data-loader/`.
- **Leitura e telas:** `dashboard/`.
- **Regras numéricas** (ritmo, crescimento, Top N, piso, oscilação): estão em `research.md` e `data-model.md`. Não reinventar nas tarefas.
- **Formato das respostas:** está em `contracts/v2-api.md`.

---

## Phase 1: Setup

**Purpose**: Destravar o gate da Constituição e preparar os arquivos de teste.

- [X] T001 Emendar `.specify/memory/constitution.md` para a versão 1.2.0 (MINOR), com Sync Impact Report no topo:
  - **Princípio VI:** o §6.1–6.7 atual passa a valer para as páginas do legado (`/`, `/profile`, `/active-consents`). Novo §6.8 "Shell v2" para as páginas `/v2*`, copiando de `specs/011-dashboard-v2/contracts/v2-ui-shell.md`: rotas, esqueleto, controles por aba, estado (`opf:v2:*`), tema claro padrão, tokens, exportação e formatação.
  - **Titlebar do legado:** permitir o link "Dashboard 2.0".
  - **Princípio III:**
    - cores de grupo de instituição vêm de `GROUP_COLORS` (legado) e `GROUP_COLORS_V2` (2.0) em `constants.py`;
    - cada shell tem sua chave de filtros;
    - trocar "Ecossistema, Perfil Receptor e Ativos" por "as páginas de cada versão".
  - **Stack Constraints:** adicionar a linha "Exportação de imagem (frontend) | `html-to-image`".
- [X] T002 [P] Criar `data-loader/tests/test_api_status_weekly.py` com fixture de SQLite em arquivo temporário contendo `api_requests`, `unique_consents` e `api_group_weekly` (DDL de `scrapers.open_db`) e helper para inserir chamadas por semana × receptor × transmissor × api × status. Seguir o padrão de `data-loader/tests/test_signals.py`.
- [X] T003 [P] Criar `dashboard/tests/v2_fixtures.py` com uma base SQLite temporária de 2 anos de semanas para 6 instituições sintéticas (uma de cada grupo, incluindo uma com nome contendo "BRADESCO", uma estreante e uma com semana faltando). A base preenche `unique_consents`, `active_consents`, `api_group_weekly`, `api_status_weekly`, `behavior_signals`, `behavior_signals_run` e `behavior_watch`, e aponta `config.DB_PATH` para ela. Seguir o padrão de `dashboard/tests/test_institution_groups.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Tabela de status, paleta, casca e catálogo funcionando de ponta a ponta, com as 4 abas abrindo vazias.

**⚠️ CRITICAL**: Nenhuma user story começa antes desta fase.

- [X] T004 Adicionar em `scrapers.open_db()` (`data-loader/scrapers.py`) o DDL de `api_status_weekly`, com PK e índices de `data-model.md`. Criar `refresh_api_status_weekly(con)`, que reconstrói a tabela inteira com `DELETE` + `INSERT … SELECT date, receptor_uuid, receptor, transmitter_uuid, transmitter, status, SUM(total) FROM api_requests WHERE api <> 'consents' GROUP BY …`, no mesmo estilo de `refresh_api_group_weekly`.
- [X] T005 Chamar `scrapers.refresh_api_status_weekly` logo depois de `refresh_api_group_weekly`:
  - no fim da coleta, em `data-loader/collector.py` (perto da linha 423);
  - em `data-loader/compute_signals.py` (perto da linha 87).
  Registrar o tempo no log.
- [X] T006 [P] Testes de integração em `data-loader/tests/test_api_status_weekly.py`:
  - o refresh agrega por semana × receptor × transmissor × status;
  - exclui a API `consents`;
  - rodar duas vezes dá as mesmas linhas;
  - invariante: para cada (date, receptor), a soma com status 200 é igual à soma de `req_week` em `api_group_weekly`.
- [X] T007 [P] Adicionar `GROUP_COLORS_V2` e `GROUP_LABELS_V2` (valores de research.md, Decisão 10) e um mapa de nomes curtos para instituições em `dashboard/services/constants.py`. Para os nomes curtos, reaproveitar `LABEL_MAP` de `services/of_analytics.py` e acrescentar os da tela: "ITAÚ UNIBANCO" → "Itaú", "CAIXA ECONOMICA FEDERAL" → "Caixa", "BANCO BTG PACTUAL" → "BTG Pactual", "KLAVI INSTITUICAO…" → "Klavi", "CUMBUCA…" → "Cumbuca", "PLUGGY…" → "Pluggy", "NEON PAGAMENTOS" → "Neon".
- [X] T008 Criar `dashboard/services/v2_metrics.py` com funções puras e tipadas de carga:
  - `load_unique(con, column)`, com `column` ∈ {`cpf`, `cnpj`, `total`};
  - `load_active(con, by)`;
  - `load_api(con, status)`.
  Cada uma devolve um DataFrame semanal (date, uuid, name, value) com o nome mais recente por UUID. Incluir também `latest_week(con)` e `institutions(con)`, que devolve uuid, nome, nome curto e grupo via `resolve_institution_group`.
- [X] T009 Criar `dashboard/routers/v2.py` com `GET /meta`, conforme `contracts/v2-api.md`:
  - devolve `data_through`, `updated_at` (de `behavior_signals_run` e da última semana), `groups` (rótulo e cor V2), `api_groups` (de `API_GROUPS`) e `institutions`;
  - cache TTL de 1 h;
  - funciona mesmo sem as tabelas novas.
  Registrar com `app.include_router(v2.router, prefix="/api/v2")` em `dashboard/server.py`.
- [X] T010 Adicionar em `dashboard/server.py` as rotas de página `/v2`, `/v2/evolucao`, `/v2/mudancas` e `/v2/instituicao`, servindo os arquivos de `gui/v2/` no mesmo padrão de `/profile`.
- [X] T011 [P] Criar `dashboard/gui/v2/v2.css` com:
  - tokens claro (padrão) e escuro de `contracts/v2-ui-shell.md`;
  - estilos de header, abas, barra de filtros (com linha 2 opcional), `.v2-card`, chips, segmented control, tabela de ranking, linha fixada (`#FFF4E3`), linha tracejada de corte, selos de alerta e estados de carregamento e erro;
  - números tabulares;
  - alvos de 44 px;
  - quebra da barra de filtros abaixo de 1280 px.
  Fonte IBM Plex Sans via Google Fonts com fallback.
- [X] T012 Criar `dashboard/gui/v2/shell.js` (JS puro, sem módulos ES que exijam bundler) com:
  - `initShell(tabId)`, que monta o header com marca, 4 abas (`aria-current` na ativa), "Dados até … · atualizado em …" (de `/api/v2/meta`), alternador de tema e link "Painel atual (legado)";
  - estado compartilhado `getFilters()` / `setFilters(partial)` em `sessionStorage['opf:v2:filters']`, preservando campos de outras abas;
  - preferências `getPrefs()` / `setPrefs()` em `localStorage['opf:v2:ranking']`, com Bradesco fixado no primeiro acesso (resolvido pelo nome em `meta.institutions`);
  - tema em `localStorage['opf:v2:theme']`, aplicado antes da pintura;
  - todo acesso a storage em try/catch;
  - formatadores (`fmtCompact` para mi/mil/bi, `fmtShare`, `fmtGrowth` para pct, multiplicador, estreia e sem base, `fmtPace` com seta, `fmtDate`, `fmtMonth`);
  - `fetchJSON(url)` com mensagem de erro legível;
  - `setLoading(cardEl, on)`.
- [X] T013 Criar `dashboard/gui/v2/index.html`, `evolucao.html`, `mudancas.html` e `instituicao.html`, cada um com `<body data-theme>`, link para `v2.css`, script do Chart.js 4.4.1 (mesmo CDN do legado), `shell.js` e `initShell('<aba>')`. Nas três abas ainda não entregues, colocar um bloco "Em construção" com link para a página equivalente do legado (Evolução → `/`, O que mudou? → `/`, Instituição → `/profile`).
- [X] T014 [P] Adicionar o link "Dashboard 2.0" (para `/v2`) no `.titlebar` de `dashboard/gui/dashboard.html`, `dashboard/gui/receptor_profile.html` e `dashboard/gui/active_consents.html`, depois do grupo de abas, sem alterar mais nada nessas páginas.
- [X] T015 [P] Testes HTTP em `dashboard/tests/test_v2_meta_ranking.py`:
  - `GET /api/v2/meta` devolve grupos com cores V2, instituições com grupo e `data_through`;
  - base sem `api_status_weekly` ainda responde 200;
  - `GET /v2`, `/v2/evolucao`, `/v2/mudancas` e `/v2/instituicao` respondem 200 com HTML;
  - `GET /` (legado) continua 200.

**Checkpoint**: `python compute_signals.py` gera `api_status_weekly`; `/v2` abre com cabeçalho, abas e tema; o legado tem o link e continua igual; todos os testes existentes passam.

---

## Phase 3: User Story 1 — Ver quem lidera e quanto (Priority: P1) 🎯 MVP

**Goal**: Aba "Quem lidera?" completa nas três métricas, com Top 15, ritmo, crescimento, fixar e excluir.

**Independent Test**: Roteiro 1–6 e 8 de `quickstart.md`, que confere com a base os números de PF, PJ, ativos e API, a exclusão da Shopee, o Bradesco fixado e o link para o legado.

### Tests for User Story 1

- [X] T016 [P] [US1] Testes de unidade das funções puras em `dashboard/tests/test_v2_meta_ranking.py`, usando a fixture:
  - ritmo por dia e seta (±10%);
  - ritmo quando a semana S−4 falta (usa a observação anterior e os dias reais);
  - crescimento `pct` / `multiplier` (> +300%) / `debut` / `no_base`;
  - Top N com excluída (a seguinte completa N, `rank` = posição no ecossistema), fixada fora do corte (`below_cut`) e filtro de grupos (fixada passa; `share` sobre o total).
- [X] T017 [P] [US1] Testes HTTP de `GET /api/v2/ranking` em `dashboard/tests/test_v2_meta_ranking.py`:
  - formato do contrato para `unique_pf`, `unique_pj`, `active` e `api`;
  - `status=500` preenche `error_rate`;
  - `scale=per_consent` reordena por chamadas por consentimento/mês;
  - `metric=xyz` → 422;
  - `limit=0` → 422;
  - UUID desconhecido em `pinned` é ignorado.

### Implementation for User Story 1

- [X] T018 [US1] Implementar em `dashboard/services/v2_metrics.py`:
  - `pace(series, week)`, conforme research.md Decisão 5: consentimentos usam S vs S−4 ÷ 28 e comparam com S−4 vs S−8; API usa a média diária de 4 semanas;
  - `growth(series, start, end, kind)`, conforme a Decisão 6, com mês de estreia.
- [X] T019 [US1] Implementar `build_ranking(df, week, *, limit, sort, pinned, excluded, groups)` em `dashboard/services/v2_metrics.py`, com as regras de montagem de `data-model.md` (Linha de ranking). Devolve `rows`, `excluded` (nome e posição) e `filters_label` (ex.: "sem Shopee", "só ITPs").
- [X] T020 [US1] Implementar `ecosystem_summary(df, week, start)` em `dashboard/services/v2_metrics.py`. Devolve:
  - total e número de receptores;
  - `by_group` (valor e participação por grupo);
  - ritmo atual e anterior;
  - crescimento;
  - para API: chamadas por consentimento/mês do ecossistema (`calls×30÷(únicos×7)`), concentração das 3 maiores e taxa de erro.
- [X] T021 [US1] Implementar `GET /ranking` em `dashboard/routers/v2.py`, conforme `contracts/v2-api.md`:
  - parâmetros `metric`, `start`, `end`, `limit`, `sort`, `groups`, `pinned`, `excluded`, `status` e `scale`, todos validados (422 com mensagem legível);
  - `api` lê `api_status_weekly`, com fallback para `api_group_weekly` quando `status=200` e a tabela nova não existe, e `unavailable: ["errors"]` quando `status≠200` e ela não existe;
  - por consentimento usa `unique_consents.total` da mesma semana;
  - cache TTL por parâmetros.
- [X] T022 [US1] Montar a barra de filtros da aba em `dashboard/gui/v2/index.html`:
  - **Linha 1:** Métrica (únicos/ativos/API); com API, Escala e Status destacados à esquerda com borda azul; Período do crescimento; chips de Grupos; Exportar dados.
  - **Linha 2:** "Sempre mostrar no ranking" (chips com alfinete e ×, "+ Incluir instituição" com busca em `meta.institutions`); "Excluir do ranking" (chips riscados com ×, "+ Excluir instituição"); "Ordenar por" (Total, Ritmo por dia, 12 meses e, com API, Por consentimento); nota "Escolhas salvas neste navegador · valem para todas as métricas".
  - Qualquer mudança grava estado/preferências e recarrega.
- [X] T023 [US1] Renderizar os blocos de resumo em `dashboard/gui/v2/index.html`:
  - título e subtítulo da métrica;
  - **Únicos:** 2 cards PF/PJ com total, ritmo/dia e seta com "4 sem. antes", barra empilhada por grupo com % e legenda com valores.
  - **Ativos:** 1 card largo.
  - **API:** 4 cards (chamadas na semana, ritmo por dia, por consentimento/mês, concentração top 3).
  Layout de referência: quadros `FinalLideranca`, `FinalLiderancaAtivos` e `FinalLiderancaApi` do canvas.
- [X] T024 [US1] Renderizar o ranking em `dashboard/gui/v2/index.html`:
  - **Únicos:** dois Top 15 lado a lado (PF/PJ) com colunas #, Instituição + barra na cor do grupo, Part., Total, Ritmo/dia · 4 sem. (valor, seta, %/dia), 12 m e menu "⋯".
  - **Ativos e API:** ranking único em largura total com coluna Grupo; API acrescenta "Por dia · 4 sem." com % vs 4 sem. antes e "Por consent./mês" (negrito acima de 2.000).
  - Linha fixada com fundo de destaque e alfinete; fixadas `below_cut` abaixo de borda tracejada.
  - Rodapé com exclusões, regra da seta e fonte.
  - Ritmo negativo em cor de queda.
- [X] T025 [US1] Implementar o menu "⋯" por linha em `dashboard/gui/v2/index.html` (menu acessível por teclado):
  - "Sempre mostrar" e "Excluir do ranking" atualizam as preferências, garantindo que uma instituição não fique nas duas listas;
  - "Ver na evolução" grava a instituição em `filters.institutions` e abre `/v2/evolucao`;
  - "Abrir perfil" abre `/v2/instituicao?uuid=`.
  Clicar no nome também abre o perfil.
- [X] T026 [US1] Acrescentar ao fim de `dashboard/gui/v2/index.html` o bloco "O que mudou desde a última atualização". Nesta fase, ele lê `/api/signals` (legado) da semana mais recente e mostra contagem e link para `/v2/mudancas`. Na US2 passa a usar `/api/v2/changes`.
- [X] T027 [US1] Validação manual: roteiro 1–6 e 8 do `quickstart.md` em `http://127.0.0.1:8000/v2`, em tema claro e escuro e a 1280 px. Também conferir que `/`, `/profile` e `/active-consents` continuam idênticos, exceto pelo link.

**Checkpoint**: MVP entregável — PR 1 (Phase 1 + 2 + US1).

---

## Phase 4: User Story 2 — Saber o que mudou desde a última atualização (Priority: P2)

**Goal**: Aba "O que mudou?" por mês, com oscilação, reincidência e "em observação", e o piso em únicos.

**Independent Test**: Roteiro 9 de `quickstart.md`: agosto/2026 com 12 alertas em 6 instituições, Banco do Nordeste como oscilação, Safra "2º mês seguido" e Santander Investimentos em observação.

### Tests for User Story 2

- [X] T028 [P] [US2] Teste em `data-loader/tests/test_signals.py`: receptor com únicos em 20.000 e ativos subindo de 40.000 para 60.000 não gera alerta de `active_consents`; receptor com únicos ≥ 30.000 continua gerando.
- [X] T029 [P] [US2] Testes em `data-loader/tests/test_signals.py` para `behavior_watch`:
  - condição de API vista só na última semana entra em `behavior_watch` com `confirm_week` = semana seguinte e não em `behavior_signals`;
  - condição confirmada em 2 semanas sai de `behavior_watch` e vira alerta;
  - rebuild idempotente.
- [X] T030 [P] [US2] Testes HTTP em `dashboard/tests/test_v2_changes.py`:
  - formato de `GET /api/v2/changes`;
  - queda + alta em semanas seguidas viram um evento `oscillation`, e `summary.alerts` continua contando 2;
  - instituição com alertas em meses consecutivos tem `streak_months` = 2 e `previous_month_summary`;
  - `watching` vem de `behavior_watch`;
  - `month=2026-13` → 422;
  - base sem `behavior_signals` → 200 com `unavailable: ["signals"]`;
  - filtros `types`, `signal`, `institution` (sem acento/caixa) e `groups`.

### Implementation for User Story 2

- [X] T031 [US2] Em `data-loader/signals.py` (`detect_consent_changes`), trocar a elegibilidade para os consentimentos únicos da semana-base (`volume_of[(uuid, semana_anterior)] ≥ CONSENT_FLOOR`) nas duas métricas e atualizar a docstring (research.md, Decisão 4).
- [X] T032 [US2] Em `data-loader/signals.py`, criar `detect_api_watch(pivot, approved_weeks, names)`. Reaproveita o cálculo 4v4 ajustado pelo ecossistema de `detect_api_changes` (extrair a parte comum numa função privada, sem duplicar) e devolve as condições na última semana aprovada que ainda não completaram `API_CONFIRM_WEEKS`.
- [X] T033 [US2] Adicionar o DDL de `behavior_watch` (`data-model.md`) em `scrapers.open_db()` (`data-loader/scrapers.py`) e gravá-la em `data-loader/compute_signals.py`, na mesma transação de `behavior_signals` (apagar e inserir). Registrar a contagem no log.
- [X] T034 [US2] Rodar `python compute_signals.py` na base local e registrar em `specs/011-dashboard-v2/quickstart.md` as contagens resultantes: alertas por métrica (ativos devem cair de 25 para cerca de 20) e linhas de `behavior_watch`.
- [X] T035 [US2] Implementar em `dashboard/services/v2_metrics.py`:
  - `group_events(signals, month)`: uma entrada por instituição; oscilação = alertas de consentimento com sinais opostos, mesma métrica, semanas consecutivas; `max_abs_change`; `items` ordenados;
  - `streaks(signals, month)`: meses consecutivos com alerta até o mês e resumo do mês anterior;
  - `monthly_counts(signals, months=12)` por tipo.
  Seguir research.md, Decisão 9.
- [X] T036 [US2] Implementar `GET /changes` em `dashboard/routers/v2.py`, conforme `contracts/v2-api.md`:
  - parâmetros `month`, `types`, `signal`, `institution`, `groups`;
  - `summary`, `events` ordenados por `max_abs_change`, `watching` de `behavior_watch`, `by_group`, `rules` (texto das regras em linguagem simples) e `computed_at`;
  - rótulo de grupo de API vem de `API_GROUPS`.
- [X] T037 [US2] Substituir o bloco "Em construção" de `dashboard/gui/v2/mudancas.html` pela aba completa:
  - barra de filtros: Mês, Tipo, Sinal, Instituição (busca) e Grupos;
  - título "O que mudou em <mês>" com contagens;
  - barra de 12 meses empilhada por tipo (queda, alta, novo entrante), com o mês selecionado destacado e meses clicáveis;
  - lista por instituição: selo do tipo, nome, grupo, "Nº mês seguido", tabela semana / grupo de API ou métrica / antes → depois / variação, resumo do mês anterior e "Abrir perfil →";
  - lateral com "Em observação" (borda tracejada), alertas por grupo e "Como os alertas são calculados";
  - estado "nenhum alerta no mês" e estado `unavailable`.
  Layout de referência: quadro `FinalMudancas`.
- [X] T038 [US2] Trocar a fonte do bloco final de `dashboard/gui/v2/index.html` para `/api/v2/changes` (mês mais recente): selo, instituição, descrição curta, maior variação e link "Ver tudo em 'O que mudou?' →".
- [X] T039 [US2] Validação manual: roteiro 9 do `quickstart.md`. Também conferir que o card "O que mudou" do legado em `/` reflete o piso novo (menos alertas de ativos) sem quebrar.

**Checkpoint**: PR 2 (US2 + US3) — a revisão mensal já cabe no 2.0.

---

## Phase 5: User Story 3 — Levar os resultados para slides (Priority: P2)

**Goal**: Todo bloco das abas entregues exporta CSV e imagem 16:9 pronta para slide.

**Independent Test**: Roteiro 7 de `quickstart.md`, nas abas 1 e 3.

- [X] T040 [US3] Implementar em `dashboard/gui/v2/shell.js` `exportCSV(block)`, que a partir de `{title, columns, rows, filtersLabel, week}` gera CSV com separador `;`, decimal com vírgula, cabeçalho em português e UTF-8 com BOM. Nome do arquivo: `opf-<aba>-<bloco>-<AAAA-MM-DD>.csv`.
- [X] T041 [US3] Implementar em `dashboard/gui/v2/shell.js` `exportImage(cardEl, meta)`:
  - clona o bloco num quadro 1600×900 fora da tela, com título (incluindo `filtersLabel`), subtítulo (métrica e semana), o conteúdo e o rodapé "Fonte: dashboard Open Finance Brasil · dados até DD/MM/AAAA";
  - converte canvas de Chart.js em `<img>` antes da captura;
  - gera o PNG com `html-to-image` (carregado via CDN em todas as páginas de `gui/v2/`);
  - em caso de falha, mostra mensagem legível e mantém o CSV disponível.
- [X] T042 [US3] Ligar os botões "Copiar como imagem" e "Baixar CSV" (ícones com `aria-label`) em todos os `.v2-card` de `dashboard/gui/v2/index.html` e `dashboard/gui/v2/mudancas.html`. O botão "Exportar dados (CSV)" da barra exporta o ranking ou a lista completa. Títulos de bloco mostram o filtro ativo (FR-013).
- [X] T043 [US3] Validação manual: roteiro 7 do `quickstart.md`. Abrir o CSV no Excel (acentos e números certos) e colar o PNG num slide 16:9 sem recorte.

---

## Phase 6: User Story 4 — Entender como opera uma instituição (Priority: P3)

**Goal**: Aba "Como opera uma instituição?" completa e acessível a partir de qualquer nome.

**Independent Test**: Roteiro "Instituição" do `quickstart.md`: Nubank com 4,51 bi chamadas, 866/mês contra 443, taxa de erro 2,30% contra 4,72% e Banco do Brasil 6,6% entre os transmissores.

### Tests for User Story 4

- [X] T044 [P] [US4] Testes HTTP em `dashboard/tests/test_v2_institution.py`:
  - formato de `GET /api/v2/institution/{uuid}`;
  - `compare=group` e `compare=<uuid>` mudam as referências (`ref_*`);
  - `api_mix` sem `Resource` e somando 100%;
  - `kpis.api` com todos os grupos;
  - taxa de erro calculada de `api_status_weekly`;
  - UUID inexistente → 404 legível;
  - `compare=xyz` inválido → 422;
  - instituição sem alertas devolve `last_alert`.

### Implementation for User Story 4

- [X] T045 [US4] Implementar em `dashboard/services/v2_metrics.py` as funções:
  - `institution_kpis(uuid, ref)`;
  - `api_mix(uuid, ref, week)`, de `api_group_weekly` sem Resource;
  - `api_by_group_monthly(uuid)`;
  - `transmitters(uuid, week)`, de `active_consents`;
  - `error_rate(uuid, ref)`, de `api_status_weekly`: série mensal e por transmissor da última semana;
  - `reference(kind)`, com ecossistema, média do grupo ou outra instituição.
- [X] T046 [US4] Implementar `GET /institution/{uuid}` em `dashboard/routers/v2.py`, conforme `contracts/v2-api.md`, incluindo posições nas quatro métricas, evolução com participação (mensal) e alertas dos últimos 12 meses ou último alerta.
- [X] T047 [US4] Substituir o bloco "Em construção" de `dashboard/gui/v2/instituicao.html` pela aba completa:
  - barra com Instituição (busca), Comparar com e Período;
  - cabeçalho com nome, grupo, frase de posições e selo de alertas;
  - 4 cards de indicadores;
  - "Cresce, mas perde espaço" (Chart.js, valores + participação nos pontos-chave);
  - "Para que usa os dados" (barras pareadas instituição × referência);
  - "Chamadas por grupo de API" (minilinhas de 12 meses nas cores de `API_GROUPS`);
  - "De onde vêm os consentimentos ativos";
  - "Taxa de erro de API" (série e por transmissor);
  - "Alertas da instituição".
  Layout de referência: quadro `FinalInstituicao`. Instituição inicial: `?uuid=` → `filters.institution` → maior do PF.
- [X] T048 [US4] Ligar cliques de nome de instituição a `/v2/instituicao?uuid=` em `dashboard/gui/v2/index.html` e `dashboard/gui/v2/mudancas.html` (FR-010) e os botões de exportação dos blocos da aba 4 (`exportCSV`/`exportImage`).
- [X] T048a [US4] Aplicar a revisão de 2026-10-05 (spec, Clarifications) em `dashboard/routers/v2.py`, `dashboard/services/v2_metrics.py` (`per_30_days`, `per_consent_30d`, `flow_means`) e `dashboard/gui/v2/instituicao.html`: 4 posições, ritmo nos cards, seletor de evolução, seletor de unidade do mix e dos grupos, transmissores com "Outros" e crescimento, taxa de erro em 4 semanas e todos os meses, alertas como na aba 3; `mudancas.html` aceita `?institution=`; testes em `dashboard/tests/test_v2_institution.py`
- [X] T049 [US4] Validação manual: roteiro "Instituição" do `quickstart.md`, alternando "Comparar com" entre ecossistema, média dos Neobancos e Mercado Pago.

---

## Phase 7: User Story 5 — Acompanhar como o ecossistema evolui (Priority: P3)

**Goal**: Aba "Como evolui?" com tendências, substituindo aceleração e momentum.

**Independent Test**: Roteiro "Evolução" do `quickstart.md`: ago/25–ago/26 PF com +115%, Shopee +5,5 pp, Nubank −6,8 pp, Belvo "acelerando" e lacuna do Belvo em 07/08 na visão semanal.

### Tests for User Story 5

- [X] T050 [P] [US5] Testes HTTP em `dashboard/tests/test_v2_evolution.py`:
  - formato de `GET /api/v2/evolution`;
  - semana faltante vira `null` na visão semanal (nunca 0);
  - mensal usa a última semana com dado da instituição no mês;
  - `headline` com maior ganho e maior perda em pp;
  - `quarterly_pace` com "stable" para diferença ≤ 3 pontos;
  - padrão = 5 maiores;
  - mais de 8 instituições → 422;
  - `by=transmitter` só com `metric=active` (senão 422).

### Implementation for User Story 5

- [X] T051 [US5] Implementar em `dashboard/services/v2_metrics.py`:
  - `monthly(df)` e `weekly(df)`, com `null` em lacunas (research.md, Decisão 8);
  - `share_series`;
  - `share_changes(start, end)`;
  - `group_share_monthly`;
  - `quarterly_pace(df, end)` (últimos 3 meses vs 3 anteriores) e o do ecossistema.
- [X] T052 [US5] Implementar `GET /evolution` em `dashboard/routers/v2.py`, conforme `contracts/v2-api.md` (parâmetros `metric`, `granularity`, `institutions`, `by`, `start`, `end`, `groups`).
- [X] T053 [US5] Substituir o bloco "Em construção" de `dashboard/gui/v2/evolucao.html` pela aba completa:
  - barra com Métrica, Evolução por (só Ativos), Período, Granularidade, Grupos e linha "Instituições no gráfico" (chips removíveis, "+ Adicionar (até 8)", sugerindo primeiro as fixadas da aba 1);
  - 3 cards de resposta;
  - gráfico Chart.js com cor do grupo, traço diferente no mesmo grupo (`borderDash`), `spanGaps: false`, rótulo de valor e crescimento no fim da linha e alternância Valores/Participação %;
  - participação por grupo mês a mês (barras empilhadas 100%) com variação em pp;
  - "Quem ganhou e quem perdeu espaço" (barras divergentes);
  - "Ritmo" trimestral com selos Acelerando/Desacelerando.
  Layout de referência: quadro `FinalEvolucao`. Ligar exportação e cliques de nome.
- [X] T054 [US5] Validação manual: roteiro "Evolução" do `quickstart.md`, incluindo "Ver na evolução" vindo do menu da aba 1.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T055 [P] Atualizar `CLAUDE.md`:
  - seção "Dashboard 2.0" com rotas `/v2*`, endpoints `/api/v2/*` e arquivos de `gui/v2/`;
  - tabelas novas (`api_status_weekly`, `behavior_watch`) no esquema;
  - nota de que `compute_signals.py` agora também reconstrói `api_status_weekly`;
  - SQLite Schema passa a listar as tabelas atuais.
- [X] T056 [P] Medir `/api/v2/*` na base real (10 chamadas por endpoint, sem cache) e registrar p95 em `specs/011-dashboard-v2/quickstart.md`. Meta: < 500 ms (Princípio IV) e aba completa em < 3 s (SC-006). Se algum passar, otimizar a carga em `v2_metrics.py` antes do PR.
- [X] T057 Rodar todos os testes (`data-loader` e `dashboard`) e o roteiro completo do `quickstart.md`. Conferir SC-003 (amostra de números contra a base) e SC-005 (legado igual).
- [ ] T058 Deploy com `.\deploy.ps1` depois de cada PR mergeado. Conferir `/v2` e `/` no Cloud Run. **Só com confirmação do usuário.**

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências; T001 (emenda) bloqueia toda tarefa de tela `/v2`.
- **Foundational (Phase 2)**: depende da Phase 1; bloqueia todas as histórias.
- **US1 (Phase 3)**: depende da Phase 2. É o MVP.
- **US2 (Phase 4)**: depende da Phase 2; T038 depende de T026 (US1).
- **US3 (Phase 5)**: depende de US1 (blocos da aba 1); a ligação na aba 3 depende de US2.
- **US4 (Phase 6)**: depende da Phase 2; T048 depende de US1/US2 (páginas onde os nomes são clicáveis).
- **US5 (Phase 7)**: depende da Phase 2; "Ver na evolução" depende de T025 (US1).
- **Polish (Phase 8)**: ao fim de cada PR (T055–T057) e após o merge (T058).

### Within Each User Story

- Testes escritos antes da implementação e falhando.
- `v2_metrics` (funções puras) → endpoint em `routers/v2.py` → página em `gui/v2/` → validação manual.

### Parallel Opportunities

- Phase 1: T002 e T003 em paralelo, depois de T001 (ou em paralelo com ele: arquivos diferentes).
- Phase 2: T006, T007, T011, T014 e T015 em paralelo; T004 → T005; T008 → T009.
- US2: T028, T029 e T030 em paralelo; T031–T034 (data-loader) em paralelo com T035–T036 (dashboard).
- US4 e US5: depois de US1, podem ser feitas em paralelo (arquivos diferentes), cada uma num PR.

---

## Parallel Example: User Story 1

```text
# Testes primeiro, juntos:
Task: "T016 Testes de unidade das funções puras em dashboard/tests/test_v2_meta_ranking.py"
Task: "T017 Testes HTTP de GET /api/v2/ranking em dashboard/tests/test_v2_meta_ranking.py"

# Depois: T018 → T019 → T020 → T021 (mesmo arquivo/serviço, em sequência)
# Em paralelo com T021, a tela: T022 → T023 → T024 → T025 → T026
```

## Parallel Example: User Story 2

```text
# data-loader e dashboard em paralelo:
Task: "T031–T034 piso em únicos e behavior_watch em data-loader/"
Task: "T035–T036 group_events/streaks e GET /api/v2/changes em dashboard/"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: emenda da Constituição + fixtures.
2. Phase 2: `api_status_weekly`, paleta, casca, `/api/v2/meta`, páginas e link no legado.
3. Phase 3: "Quem lidera?" completa.
4. **PARAR e VALIDAR** com o roteiro 1–6 e 8; PR 1 → merge → deploy (com confirmação).

### Incremental Delivery

1. PR 1: Setup + Foundational + US1 → `/v2` com a aba de abertura, demais abas apontando para o legado.
2. PR 2: US2 + US3 → revisão mensal e exportação no 2.0.
3. PR 3: US4 → perfil da instituição.
4. PR 4: US5 → evolução.
5. Depois (fora desta feature): virada do endereço principal para o 2.0.

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente.
- O legado só recebe o link do titlebar (T014); qualquer outra mudança nele está fora do escopo.
- Commit ao fim de cada tarefa ou grupo lógico; nada de commit, push ou deploy sem pedido do usuário.
- Números de conferência estão no `quickstart.md`; se a base for atualizada antes da validação, recalcular os números esperados em vez de forçar os antigos.

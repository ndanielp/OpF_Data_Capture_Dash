# Tasks: Tema Pagamentos no Dashboard 2.0

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/payments-api.md](contracts/payments-api.md), [ux-handoff.md](ux-handoff.md)

Formato: `[ID] [P?] [Story] Descrição`. `[P]` = pode correr em paralelo (arquivos diferentes, sem dependência pendente).

## Phase 1: Setup

- [x] T001 Emendar a Constituição (§6.8 seletor de tema e abas do tema Pagamentos; Princípio III cores `PAYMENT_APIS`), versão 2.0.0 → 2.1.0 com relatório de sincronização, em `.specify/memory/constitution.md`
- [x] T002 [P] Adicionar `PAYMENT_APIS`, `PAYMENT_HEAT` e os nomes curtos "Google Pay" e "Lina" em `dashboard/services/constants.py`

## Phase 2: Foundational (bloqueia todas as histórias)

- [x] T003 DDL de `payment_weekly` (+ índice `(endpoint_id, date)`) em `scrapers.open_db()` e `refresh_payment_weekly(con)` em `data-loader/scrapers.py`
- [x] T004 Chamar `refresh_payment_weekly` no fim de `run-pi` em `data-loader/collector.py` (a coleta `run` não toca em pagamentos) e em `compute()` de `data-loader/compute_signals.py`
- [x] T005 [P] Teste de integração do refresh (filtro de endpoints, soma por status, sem transmissor vazio, idempotência, chamado por `compute_signals.compute`) em `data-loader/tests/test_payment_weekly.py`
- [x] T006 Serviço `dashboard/services/payments.py`: carga cacheada pela base (`TableMissing` quando ausente), catálogo, janelas de 4 semanas, fator mensal (R2), meses (R3)
- [x] T007 Roteador `dashboard/routers/payments.py` com `GET /meta`; incluir em `dashboard/server.py` (prefixo `/api/v2/payments`), aquecer no startup, rotas de página `/v2/pagamentos*`
- [x] T008 [P] Base sintética de pagamento `dashboard/tests/pay_fixtures.py` (DDL de `payment_weekly`, 3 iniciadoras, 4 detentoras, meses de 4 e 5 semanas, falha conhecida, vínculos) e teste de `/meta` + tabela ausente em `dashboard/tests/test_payments.py`
- [x] T009 Casca: seletor "Dados | Pagamentos", abas do tema, data do cabeçalho do tema, `V2.initShell(tabId, {theme})`, `V2.pay` (meta, cores, preferências de fixar/excluir em `localStorage['opf:v2:pay-ranking']`, formatação de 30 dias, recorte com chips, barras mensais, linhas de falha, funil) em `dashboard/gui/v2/shell.js`; estilos em `dashboard/gui/v2/v2.css`

**Checkpoint**: tabela populada na base local, `/api/v2/payments/meta` responde, cabeçalho troca de tema.

## Phase 3: User Story 1 — Quem lidera? (P1) 🎯 MVP

- [x] T010 [US1] `ranking(role, api, limit, pinned, excluded)` em `dashboard/services/payments.py` (FR-013, FR-020–022)
- [x] T011 [US1] `GET /ranking` em `dashboard/routers/payments.py` com validação (422)
- [x] T012 [P] [US1] Testes HTTP de `/ranking` (valores, filtro de API, fixadas, 422, tabela ausente) em `dashboard/tests/test_payments.py`
- [x] T013 [US1] Página `dashboard/gui/v2/pagamentos.html` (indicadores, ranking, fixar/excluir, CSV, imagem; grava `pay_role`/`pay_api` em `sessionStorage['opf:v2:filters']` preservando os outros campos)

## Phase 4: User Story 2 — Como evolui? (P1)

- [x] T014 [US2] `flows(size)` e `enrollment(receptor, transmitter)` em `dashboard/services/payments.py` (FR-014, FR-040, R4, R6)
- [x] T015 [US2] `GET /flows` e `GET /enrollment` em `dashboard/routers/payments.py`
- [x] T016 [P] [US2] Testes HTTP de `/flows` (normalização mensal, Outras, soma = total) e `/enrollment` (ecossistema, por detentora, 422 com os dois filtros, tabela ausente)
- [x] T017 [US2] Página `dashboard/gui/v2/pagamentos-evolucao.html` (recorte, 4 passos, frases, JSR recolhido, CSV)

## Phase 5: User Story 3 — Como opera uma instituição? (P1)

- [x] T018 [US3] `institution(uuid, role)` em `dashboard/services/payments.py` (FR-015, FR-060–063)
- [x] T019 [US3] `GET /institution/{uuid}` (404, 422, papel sem dados)
- [x] T020 [P] [US3] Testes HTTP de `/institution` (caminho feliz, 404, 422, papel sem dados, tabela ausente) em `dashboard/tests/test_payments.py`
- [x] T021 [US3] Página `dashboard/gui/v2/pagamentos-instituicao.html` (seletor, papel, recorte, 4 passos, onde falha, JSR e consultas, CSV)

## Phase 6: User Story 4 — Quem paga com quem? (P2)

- [x] T022 [US4] Página `dashboard/gui/v2/pagamentos-matriz.html` sobre `/flows` (cor, API, Top 8/4 com troca automática para Top 4 abaixo de 760 px, linha do tempo e reprodução, detalhe da célula, 3 frases, CSV)

## Phase 7: User Story 5 — O que mudou? (P2)

- [x] T023 [US5] `changes()` em `dashboard/services/payments.py` (FR-030–035, R5)
- [x] T024 [US5] `GET /changes`
- [x] T025 [P] [US5] Testes HTTP de `/changes` (alerta confirmado, em observação, piso, tabela ausente)
- [x] T026 [US5] Página `dashboard/gui/v2/pagamentos-mudancas.html` (filtros, alertas, em observação, vazio, CSV)

## Phase 8: Polish

- [x] T027 Popular `payment_weekly` na base local (`compute_signals.py`) e conferir SC-001 com SQL direto; medir cada rota com cache quente (≤ 500 ms) e a carga de cada aba (≤ 2 s) — SC-002
- [x] T028 Rodar toda a suíte (`data-loader/tests`, `dashboard/tests`)
- [x] T029 Validação manual no navegador das 5 abas, tema escuro, 1280 × 800 e 390 px sem rolagem da página (SC-004), recorte sem ida ao servidor (SC-003) (Constituição II; quickstart.md)
- [x] T030 Atualizar `CLAUDE.md` (tema Pagamentos, `payment_weekly`, rotas) e marcar tarefas

## Dependencies

- T001 (emenda da Constituição) MUST estar pronta antes de qualquer tarefa de página (T009, T013, T017, T021, T022, T026). T001–T002 → T003–T009 → histórias. T006 antes de T010/T014/T018/T023. T014 antes de T022 (a matriz usa `/flows`).
- US1, US2, US3, US5 independentes entre si depois da fase 2; US4 depende de T015.

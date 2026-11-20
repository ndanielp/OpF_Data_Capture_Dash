# Tasks: Polimento do tema Pagamentos

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/payments-api-delta.md](contracts/payments-api-delta.md)

Formato: `[ID] [P?] [Story] Descrição`.

## Phase 1: Foundational (servidor)

- [x] T001 `meta()` com `volume` por papel e mês em `dashboard/services/payments.py` (FR-022, R5)
- [x] T002 `ranking(..., month)` com período do mês, crescimento e `ip_share_prev` contra o mês anterior, `period` na resposta; `limit` até 500 em `dashboard/routers/payments.py` (FR-003, FR-024, R1)
- [x] T003 `flows(size, rows, cols)` com escolhidas na ordem e `others_count`; 422 acima de 12 (FR-020, FR-021, R3)
- [x] T004 `institution(uuid, role, counterparts)` com escolhidas e `others_count`; 422 acima de 12 (FR-023, R4)
- [x] T005 `changes(month)` com `months` (contagem por mês, em cache) e `watching` só no último mês; 422 para mês fora da base (FR-007, R2)
- [x] T006 [P] Testes HTTP dos parâmetros novos (caminho feliz + 422 + resposta igual sem parâmetro) em `dashboard/tests/test_payments.py`

## Phase 2: Foundational (casca)

- [x] T007 Seletor de instituição: opções `all`, `sort`, `detail` em `V2.openInstitutionPicker`, com padrão igual ao de hoje (R5)
- [x] T008 `V2.pay.state` (ler URL → sessionStorage; gravar `pay_month`, `pay_r`, `pay_c` preservando os outros campos; `replaceState`), `V2.pay.monthSelect` com o mês parcial marcado; descartar uuid ou mês inválido da URL com aviso de uma linha (FR-001, FR-002, FR-014, R6, Edge Cases)
- [x] T009 `V2.pay.scope` (barra de recorte: "todas", "+ Adicionar", chips com ×, "Limpar", aviso de limite; tudo por teclado, alvo de 44 px) (FR-010–FR-013, FR-045)
- [x] T010 `V2.pay.tip` + barras mensais como botões com dica e escolha do mês + linhas com pontos, rótulos e dica; legendas só com séries presentes (FR-004, FR-006, FR-040, FR-045, R7)
- [x] T011 `V2.exportImage`/`exportSlide` preservam `button[data-keep]` (R8)
- [x] T012 CSS: seletor de mês, recorte, dica, barras-botão, pontos, "Exportar CSV" à direita da 1ª linha (FR-015)

## Phase 3: User Story 1 — Mês específico (P1)

- [x] T013 [US1] `pagamentos.html`: seletor de mês, título com o mês, "Mostrar: 10 · 25 · todas", indicadores 4 → 2 × 2 (FR-003, FR-024, FR-043)
- [x] T014 [US1] `pagamentos-mudancas.html`: barra de meses, mês escolhido, agrupamento por instituição e papel, busca (FR-007, FR-044)

## Phase 4: User Stories 2 e 3 — Recorte por inclusão e qualquer instituição (P1)

- [x] T015 [US2] `pagamentos-evolucao.html`: recorte por inclusão (pede `/flows` com as escolhas), mês escolhido com destaque, "de / até" no passo 2, frases com o recorte (FR-004, FR-005, FR-010–FR-014)
- [x] T016 [US3] `pagamentos-matriz.html`: linhas e colunas pelo recorte (até 12), "Maiores: 4 · 8 · 12", mês = estado comum, meses alinhados, célula num só botão `data-keep` (FR-008, FR-021, FR-041, FR-042)
- [x] T017 [US3] `pagamentos-instituicao.html`: recorte de contrapartes por inclusão (`counterparts`), mês escolhido, "de / até", legendas (FR-005, FR-023, FR-040)

## Phase 5: Polish

- [x] T018 Rodar a suíte do painel e do coletor; conferir o total de um mês contra SQL direto (SC-001)
- [x] T019 Validação manual (quickstart.md): mês, recorte, URL compartilhada, 1280/800/390 px, teclado
- [x] T020 Atualizar `CLAUDE.md` (tema Pagamentos: mês, recorte, parâmetros) e marcar as tarefas

## Dependencies

- T001–T005 → T006. T007–T012 → páginas. T003 → T015/T016; T004 → T017; T002 → T013; T005 → T014.
- US1 independente de US2/US3 depois das fases 1 e 2.

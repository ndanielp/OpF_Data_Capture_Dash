---

description: "Tarefas da feature 016: Remover o painel v1 (legado)"
---

# Tasks: Remover o painel v1 (legado)

**Input**: `/specs/016-remove-v1-dashboard/` (spec.md, plan.md, research.md, contracts/routes.md, quickstart.md)

**Tests**: A feature é de remoção. Os testes v1 saem; entram testes só para o que é novo (redirecionamentos, 404, classificação). A prova de "sem mudança de comportamento" é a comparação antes/depois (T002 e T020).

## Phase 1: Linha de base

- [x] T001 Subir o servidor da `main` na base real e confirmar que responde
- [x] T002 Gravar a linha de base em `/tmp/v1-baseline`: `/api/v2/meta`, `/ranking?metric=unique_pf`, `/ranking?metric=api`, `/evolution?metric=unique_pf`, `/changes`, `/institution/<uuid do Nubank>`, e uma exportação `unique` de 12 meses pelo `services.export` (CSV), para comparar depois

## Phase 2: Realocar o que o v2 usa (bloqueia a remoção)

- [x] T003 Mover `resolve_institution_group` de `dashboard/services/of_analytics.py` para `dashboard/services/constants.py` (junto de `INSTITUTION_GROUPS`)
- [x] T004 [P] Em `dashboard/routers/v2.py` e `dashboard/services/v2_metrics.py`, trocar o import de `services.of_analytics` por `services.constants`
- [x] T005 [P] Criar `dashboard/tests/test_v1_removal.py` com testes unitários de `resolve_institution_group` (Bradesco → incumbentes, Nubank → neo_banks, instituição desconhecida → outros)

## Phase 3: US2, links antigos redirecionam (P1)

- [x] T006 [US2] Em `dashboard/server.py`, trocar as rotas `/`, `/profile` e `/active-consents` por redirecionamentos 307 para `/v2` (descartando a query string)
- [x] T007 [US2] Em `dashboard/tests/test_v1_removal.py`, testes dos redirecionamentos (com e sem parâmetros) e do 404 das rotas de API e dos estáticos removidos (lista de [contracts/routes.md](contracts/routes.md))

## Phase 4: US3, apagar o código v1 (P2)

- [x] T008 [US3] Apagar `dashboard/gui/dashboard.html`, `dashboard/gui/receptor_profile.html`, `dashboard/gui/active_consents.html`
- [x] T009 [US3] Apagar `dashboard/routers/openfinance.py`, `dashboard/routers/active_consents.py`, `dashboard/routers/signals.py`, `dashboard/services/of_analytics.py`, `dashboard/services/cache.py`
- [x] T010 [US3] Em `dashboard/server.py`: remover os `include_router` dos três routers apagados, as rotas `/api/receptors`, `/api/consents`, `/api/api-requests`, `/api/api-requests-timeseries`, `/api/resources`, `/api/acceleration`, `/api/efficiency`, `/api/stats`, o cache de respostas, os carregadores, os helpers de cor/filtro/sinal, `_warm_profile_cache`, `_get_latest_weeks` e as constantes só do v1; manter `lifespan`, os três `_ensure_*`, `_warm_v2_cache`, as páginas `/v2*`, os redirecionamentos, `_RevalidatingStatic` e `run_server`; remover imports não usados
- [x] T011 [US3] Em `dashboard/services/constants.py`, apagar as constantes que ficarem sem uso (`BRAND_COLORS`, `GROUP_COLORS`, `GROUP_LABELS`, `EXCLUDED_APIS`, `RESOURCES_API` etc.), confirmando cada uma com busca no repositório
- [x] T012 [US3] Apagar `dashboard/tests/test_active_consents_api.py`, `dashboard/tests/test_institution_groups.py`, `dashboard/tests/test_signals_api.py`
- [x] T013 [US3] Em `dashboard/gui/v2/shell.js`, remover o link "Painel legado" do cabeçalho; em `dashboard/server.py` e `dashboard/services/constants.py`, reescrever os comentários que citam o legado

## Phase 5: US1, nada mudou no v2 (P1)

- [x] T014 [US1] Rodar `pytest dashboard/tests` e `pytest data-loader` e corrigir o que quebrar
- [x] T015 [US1] Subir o servidor da branch na base real e repetir as chamadas de T002; `diff` contra `/tmp/v1-baseline` sem diferenças (exceto `updated_at` se a base mudou)
- [x] T016 [US1] No navegador, abrir `/`, `/profile`, `/active-consents?x=1` (devem terminar em `/v2`), as cinco páginas v2 (sem "Painel legado") e uma exportação

## Phase 6: Governança e Git

- [x] T017 [P] Emendar `.specify/memory/constitution.md` (2.0.0): remover §6.1–6.7 e as referências ao shell legado nos Princípios III e VI, atualizar relatório de impacto, versão e data
- [x] T018 [P] Atualizar `CLAUDE.md`: remover a descrição do v1, as rotas e serviços v1, a frase "used by the legacy dashboard" e a seção "Dashboard API" antiga; ajustar o texto do Dashboard 2.0 ("served alongside the legacy one")
- [x] T019 [P] Apagar `specs/002-active-consents-views`, `specs/003-ui-shell-ativos`, `specs/004-matrix-sort`, `specs/005-matrix-visual-parity`, `specs/006-active-consents-improvements` e a pasta `especificações/`; ajustar `README.md` se citar o v1
- [x] T020 Buscas finais: `git grep -il "painel legado\|dashboard\.html\|receptor_profile\|active_consents\.html\|of_analytics\|api/of/"` sem resultados fora de `specs/` históricas; registrar o resultado em `checklists/requirements.md`
- [x] T021 Commit, push da branch e pull request para a `main`

## Dependencies & Execution Order

- T001–T002 primeiro (linha de base antes de apagar). Phase 2 antes da Phase 4, porque o v2 importa a função movida.
- T006–T007 (redirects) independem de T008–T013, mas T010 mexe no mesmo `server.py`: fazer em sequência.
- T017–T019 podem andar em paralelo com a Phase 4. T014–T016 e T020 depois de tudo.

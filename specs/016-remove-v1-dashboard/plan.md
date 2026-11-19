# Implementation Plan: Remover o painel v1 (legado)

**Branch**: `016-remove-v1-dashboard` | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/016-remove-v1-dashboard/spec.md`

## Summary

Apagar o painel v1 (três páginas, as rotas de API, os serviços e os testes que só ele usa, o link "Painel legado", as regras de shell legado na constituição, as seções do `CLAUDE.md` e as specs antigas) e fazer `/`, `/profile` e `/active-consents` redirecionarem para `/v2`. O Dashboard 2.0, o portal de exportação e a coleta não mudam. O trabalho é remoção, mais uma única realocação: `resolve_institution_group` sai de `of_analytics.py` e vai para `constants.py`, porque o v2 a usa. O histórico do Git não é reescrito.

## Technical Context

**Language/Version**: Python 3.11+ (dashboard), JavaScript sem build (frontend)

**Primary Dependencies**: FastAPI, Uvicorn, pandas, cachetools (já existentes). Nenhuma dependência nova; `cachetools` e `pandas` continuam usados pelo v2.

**Storage**: SQLite `consents.db`, sem mudança.

**Testing**: pytest + httpx `ASGITransport`. Testes v1 saem; testes v2 e exportação ficam; entram testes dos redirecionamentos, do 404 das rotas removidas e da classificação de instituições.

**Target Platform**: Cloud Run (sem mudança de configuração).

**Project Type**: web service (FastAPI) + páginas estáticas.

**Performance Goals**: sem regressão; a partida do servidor fica mais leve (menos pré-aquecimento de cache).

**Constraints**: nenhuma mudança de comportamento no v2, na exportação, na coleta ou no deploy; histórico preservado.

**Scale/Scope**: ~6 mil linhas de HTML, ~1.600 de `server.py`/routers/serviços e ~900 de testes a apagar; 5 specs e 2 documentos de apoio a apagar; 1 emenda MAIOR da constituição.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Code Quality**: remove código morto; a única função movida (`resolve_institution_group`) ganha o lugar natural, junto de `INSTITUTION_GROUPS`.
- [x] **II. Testing**: nenhum upsert novo; os testes v1 saem junto do código que cobriam, e entram testes para o que é novo (redirecionamentos, 404, classificação).
- [x] **III. UX Consistency**: o v2 não muda; o link "Painel legado" sai.
- [x] **IV. Performance**: sem consulta nova; a partida fica mais leve.
- [x] **V. Paradigm**: sem import entre componentes, sem mudança de schema, o dashboard continua só lendo a base (os `_ensure_*` ficam como hoje).
- [ ] **VI. UI Shell**: **precisa de emenda MAIOR (2.0.0)**: o shell legado (§6.1–6.7) deixa de existir. Entra no mesmo PR (Complexity Tracking).

**Pós-design (Phase 1)**: mesmos resultados. A emenda é tarefa explícita.

## Project Structure

### Documentation (this feature)

```text
specs/016-remove-v1-dashboard/
├── spec.md
├── plan.md             # este arquivo
├── research.md         # inventário do que sai e do que fica
├── data-model.md       # sem mudança de dados
├── quickstart.md       # comparação antes/depois
├── contracts/routes.md # rotas antes e depois
├── checklists/requirements.md
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root)

```text
dashboard/
├── server.py                   # encolhe: lifespan, páginas /v2*, redirects, static, _ensure_*, run_server
├── services/
│   ├── constants.py            # recebe resolve_institution_group; perde constantes só do v1
│   ├── of_analytics.py         # APAGADO
│   └── cache.py                # APAGADO (só o v1 usava)
├── routers/
│   ├── openfinance.py          # APAGADO
│   ├── active_consents.py      # APAGADO
│   ├── signals.py              # APAGADO
│   ├── v2.py, export.py        # só mudam os imports de resolve_institution_group
├── gui/
│   ├── dashboard.html, receptor_profile.html, active_consents.html   # APAGADOS
│   └── v2/shell.js             # sem o link "Painel legado"
└── tests/
    ├── test_active_consents_api.py, test_institution_groups.py, test_signals_api.py   # APAGADOS
    ├── test_v1_removal.py      # NOVO: redirects, 404, sem link legado, resolve_institution_group
    └── v2_fixtures.py, test_v2_*.py                                                  # ficam
specs/002..006, especificações/ # APAGADOS
.specify/memory/constitution.md # emenda 2.0.0
CLAUDE.md                       # sem v1; ponteiro do plano
```

**Structure Decision**: segue o que já existe (router fino, regras em `services/`), só que sem a geração anterior.

## Fases de implementação (para /speckit-tasks)

1. **Linha de base**: gravar as respostas do v2 e uma exportação na base real, antes de apagar.
2. **Realocar o que o v2 usa**: `resolve_institution_group` para `constants.py`, imports em `v2.py` e `v2_metrics.py`; testes de classificação.
3. **US2, redirecionamentos**: `/`, `/profile`, `/active-consents` → 307 `/v2`; testes.
4. **US3, apagar o código v1**: páginas, routers, serviços, rotas e helpers de `server.py`, constantes órfãs, testes v1, link "Painel legado".
5. **US1, comparação**: comparar a linha de base com o estado depois; rodar toda a bateria.
6. **Governança e Git**: constituição 2.0.0, `CLAUDE.md`, specs 002–006 e `especificações/`, buscas finais, commit e PR.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Princípio VI: emenda MAIOR que remove o shell legado | O shell legado só se aplicava às páginas que saem | Manter §6.1–6.7 deixaria uma regra para páginas que não existem e confundiria quem lê a constituição |

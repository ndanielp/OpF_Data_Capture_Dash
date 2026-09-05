# Implementation Plan: Filtro de Grupos de Instituições

**Branch**: `009-filtro-grupos-instituicoes` | **Date**: 2026-09-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-filtro-grupos-instituicoes/spec.md`

## Summary

Adicionar um filtro por **grupo de instituição** (Incumbentes, Neo Banks, ITPs,
Outros/Não classificado) ao dashboard OpF, aplicável a receptores e transmissores nas
três páginas existentes (Ecossistema, Perfil Receptores, Ativos). A classificação é um
mapeamento estático nome→grupo (mesmo padrão de `BRAND_COLORS`), exposto via um novo
endpoint `/api/of/institution-groups`, e consumido como mais um parâmetro de filtro
(`groups`) combinável com os filtros já existentes (`start`, `end`, `receptors`),
seguindo o mesmo contrato de persistência em `sessionStorage['opf:filters']`.

## Technical Context

**Language/Version**: Python 3.11+ (dashboard component, FastAPI) + Vanilla JS (frontend) — fixado pela constituição.

**Primary Dependencies**: FastAPI, pandas (agregação em memória), Chart.js — stack existente, nenhuma dependência nova.

**Storage**: SQLite (`consents.db`), somente leitura pelo dashboard. **Nenhuma alteração de schema** — a classificação de grupo é um mapeamento estático em código Python (`constants.py`), não uma coluna no banco.

**Testing**: `httpx.AsyncClient` para os endpoints HTTP tocados/novos (Principle II). Validação manual no navegador (porta 8000) para o comportamento do filtro nas 3 páginas.

**Target Platform**: Cloud Run (produção) + servidor local (`uvicorn --reload`).

**Project Type**: Web service existente (dashboard) — feature é inteiramente dentro de `dashboard/`, não toca `data-loader/`.

**Performance Goals**: Endpoints `/api/of/*` afetados mantêm o orçamento existente de 500ms p95 (Principle IV). O filtro de grupo é aplicado como um passo adicional de filtragem em memória (pandas/SQL `LIKE`) sobre dados já carregados — não introduz novo cruzamento multi-dimensional que exigiria pré-agregação.

**Constraints**: Sem alterações de schema SQLite; filtro deve ser combinável com `receptors`/`start`/`end` já existentes; deve seguir o contrato de shell/filtro da Constituição (Principle III, VI).

**Scale/Scope**: 63 instituições classificadas hoje (ver `institution-groups-draft.md`), 4 grupos. Toca as 3 páginas do dashboard e ~6 endpoints que já aceitam `receptors`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify against `.specify/memory/constitution.md` v1.1.0:

- [x] **I. Code Quality**: Novo dicionário `INSTITUTION_GROUPS` em `constants.py`
  reaproveita o padrão já existente de `BRAND_COLORS` (mesmo formato de match por
  substring). A função de resolução de grupo (`resolve_institution_group(name)`) tem
  ≥3 call sites reais (matrix, séries por API, ranking/acceleration) — abstração
  justificada.
- [x] **II. Testing**: HTTP-level test cobrindo o novo endpoint
  `/api/of/institution-groups` e o parâmetro `groups` nos endpoints existentes que
  passam a aceitá-lo. Validação manual em navegador do filtro nas 3 páginas.
- [x] **III. UX Consistency**: Nenhuma cor nova hardcoded — grupos usam paleta neutra
  definida em `constants.py`. Filtro `groups` se comporta identicamente nas 3 páginas.
  `/api/of/institution-groups` segue o mesmo padrão de fonte única de verdade que
  `/api/of/api-groups`. `sessionStorage['opf:filters']` ganha o campo `groups`,
  preservando (spread) os campos existentes.
- [x] **IV. Performance**: Resolução de grupo por instituição é um lookup O(1) em
  memória (após pré-computar um dict nome→grupo no boot do processo) — não requer
  nova tabela pré-agregada. Pruning de coleta não é afetado (feature é dashboard-only).
- [x] **V. Paradigm**: Nenhuma mudança em `data-loader/`. Nenhuma alteração de schema
  SQLite. Filtro na matriz usa `LIKE` parametrizado, seguindo o padrão já usado por
  `_parse_receptors`/`matrix()` em `active_consents.py`.

**Nota sobre VI (UI Shell Contract)**: a feature adiciona um novo grupo de filtro na
sidebar (`.sidebar-group "Grupos"`, ver seção 6.3), reaproveitando a estrutura de
lista com seleção já usada para receptores — não introduz um padrão de UI novo.

## Project Structure

### Documentation (this feature)

```text
specs/009-filtro-grupos-instituicoes/
├── plan.md                        # Este arquivo
├── research.md                    # Fase 0
├── data-model.md                  # Fase 1
├── quickstart.md                  # Fase 1
├── contracts/
│   └── institution-groups-api.md  # Fase 1
├── institution-groups-draft.md    # Classificação confirmada das 63 instituições (insumo do data-model)
└── tasks.md                       # Fase 2 (/speckit-tasks — não criado por este comando)
```

### Source Code (repository root)

```text
dashboard/
├── services/
│   └── constants.py            # + INSTITUTION_GROUPS, GROUP_LABELS (novo)
├── services/
│   └── of_analytics.py         # + resolve_institution_group() / helper de lookup (novo, reaproveitado por routers)
├── routers/
│   └── openfinance.py          # + GET /api/of/institution-groups (novo)
├── server.py                   # get_consents, get_api_requests, get_resources,
│                                #   get_acceleration ganham parâmetro `groups`
├── routers/
│   └── active_consents.py      # evolution, matrix, ranking, intensity ganham `groups`
│                                #   (matrix filtra ambos os eixos: receptor E transmissor)
├── gui/
│   ├── dashboard.html          # sidebar: novo .sidebar-group "Grupos"; lê/escreve
│   │                            #   sessionStorage['opf:filters'].groups
│   ├── receptor_profile.html   # idem
│   └── active_consents.html    # idem
└── tests/
    └── test_institution_groups_api.py   # novo — HTTP-level test (Principle II)
```

**Structure Decision**: Feature inteiramente contida em `dashboard/`. Não há novo
diretório de projeto — segue a estrutura já existente (routers + services + gui +
tests), adicionando um novo módulo de dados estáticos (`INSTITUTION_GROUPS`) e um novo
parâmetro de query (`groups`) propagado pelos endpoints que já aceitam `receptors`.

## Complexity Tracking

*Nenhuma violação da Constituição identificada — seção não aplicável.*

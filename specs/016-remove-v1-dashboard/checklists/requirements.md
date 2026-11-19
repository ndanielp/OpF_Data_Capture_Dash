# Specification Quality Checklist: Remover o painel v1 (legado)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-19
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Os três pontos em aberto (raiz, "inclusive do Git" e base da branch) foram respondidos pelo usuário antes da especificação e estão em "Clarifications".
- A lista exata de arquivos, rotas e funções a apagar sai da fase de plano, depois de mapear o que o v2 reutiliza.

## Validação da implementação (2026-11-19)

- `pytest dashboard/tests`: 168 passam (inclui `test_v1_removal.py`); `data-loader`: 61 passam.
- Linha de base x depois, na base real: `/api/v2/meta`, `/ranking` (unique_pf e api), `/evolution`, `/changes`, `/institution/<Nubank>` e um CSV de exportação, **idênticos byte a byte** (`diff -rq`).
- `GET /`, `/profile`, `/active-consents?x=1` → 307 para `/v2` (GET e HEAD); `/api/consents`, `/api/of/institutions`, `/api/signals`, `/api/stats`, `/static/dashboard.html` → 404.
- Navegador: `/profile?x=1` termina em `/v2`, 4 abas, sem "Painel legado", ranking carregado.
- Busca final (`git grep`) sem resultados fora de `specs/` históricas, dos relatórios de impacto antigos da constituição e de `.claude/settings.json` (permissões de curl antigas, não é código).
- **Não verificado**: deploy no Cloud Run após a remoção.

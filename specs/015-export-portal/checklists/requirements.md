# Specification Quality Checklist: Portal de exportação de dados

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

- FR-011 resolvido em 2026-11-19: sem limite de linhas; aviso acima de 1 milhão de linhas, sem bloquear (FR-011, FR-011a, SC-005, SC-005a).
- O formato do arquivo (CSV com `;`, vírgula decimal) aparece em FR-012 porque é um padrão que o usuário vê, já fixado no Dashboard 2.0, e não uma escolha técnica nova.
- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`

## Validação da implementação (2026-11-19)

- `pytest dashboard/tests` 173 passam (36 novos em `test_v2_export.py`); `data-loader` 61 passam.
- Base real (somente leitura): contagem de "Chamadas de API" 0,25–0,5 s com cache quente (8 s a frio, por isso o catálogo e a contagem inicial são aquecidos na partida); exportação completa de "Chamadas de API" (por endpoint, 4,9 M linhas) + "Consentimentos ativos" em ZIP: primeiro byte em 2,8 s, 29,5 s no total, pico de memória 311 MB.
- Navegador (base sintética): acesso, erro de código, bloqueio, código trocado com filtros preservados, 3 tabelas em ZIP com progresso (seletor de arquivo simulado), download nativo com travamento de 3 s, celular com barra fixa.
- **Não verificado**: o seletor de arquivo real do Chrome/Edge (`showSaveFilePicker`), o download em Safari/Firefox, o deploy no Cloud Run com o segredo `opf-export-code` e o modo escuro.

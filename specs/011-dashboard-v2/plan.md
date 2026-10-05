# Implementation Plan: Dashboard 2.0

**Branch**: `011-dashboard-v2` | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-dashboard-v2/spec.md` · Design: canvas https://claude.ai/artifact/LZivcKNMg2z43daC2arfWv (página "Versão final — para aprovação")

## Summary

O 2.0 nasce **ao lado** do legado, no mesmo serviço: páginas novas sob `/v2` (uma por aba) com uma casca compartilhada em `dashboard/gui/v2/` e endpoints novos sob `/api/v2/*`. O legado não muda, exceto um link para o 2.0.

O `data-loader` ganha três coisas, todas aditivas:

1. a pré-agregação `api_status_weekly`, para erros e taxa de erro;
2. a tabela `behavior_watch`, para o "em observação";
3. a regra do piso de 30 mil medida em consentimentos únicos.

A entrega segue as prioridades da spec:

- **P1:** emenda da Constituição + casca + "Quem lidera?";
- **P2:** "O que mudou?" + exportação;
- **P3:** "Como opera uma instituição?" e "Como evolui?".

## Technical Context

**Language/Version**: Python 3.11+ (data-loader e dashboard) + JavaScript puro e HTML/CSS (frontend) — fixado pela Constituição.

**Primary Dependencies**:

- **Backend:** FastAPI, pandas e cachetools, todos já em uso.
- **Frontend:** Chart.js 4.4.1 via CDN, como no legado.
- **Nova no frontend:** `html-to-image` via CDN, para exportar imagem (Decisão 11 do research). Exige incluir a linha na tabela de Stack da Constituição.
- **Fonte:** IBM Plex Sans via Google Fonts, com fallback do sistema.

**Storage**: SQLite `consents.db`.

- Tabelas novas: `api_status_weekly` e `behavior_watch`, ambas criadas e escritas só pelo `data-loader`.
- Nenhuma tabela existente muda de esquema.

**Testing**:

- **data-loader:** pytest com SQLite real (refresh de `api_status_weekly`, `behavior_watch`, piso em únicos, idempotência).
- **dashboard:** pytest com `httpx` contra o app real para cada endpoint `/api/v2/*`, cobrindo o caminho feliz e um erro.
- **Telas:** validação manual em navegador pelo roteiro do `quickstart.md`.
- **Legado:** todos os testes existentes continuam passando.

**Target Platform**: Cloud Run (dashboard) e máquina local (coleta e cálculo). Navegadores desktop a partir de 1280 px.

**Project Type**: Extensão dos dois componentes existentes. Não há componente novo.

**Performance Goals**:

- `/api/v2/*` abaixo de 500 ms p95 (Princípio IV) e cada aba completa em menos de 3 s (SC-006).
- As fontes são pequenas ou pré-agregadas: `unique_consents` tem 4,6 mil linhas, `active_consents` 110 mil e `api_status_weekly` cerca de 167 mil.
- O rebuild de `api_status_weekly` custa cerca de 35 s, pago no fim da coleta e em `compute_signals.py`.

**Constraints**:

- O dashboard não escreve no banco (Princípio V).
- Não há imports cruzados entre os componentes.
- O SQL é parametrizado.
- O legado continua idêntico: mesmas rotas, mesmas respostas, mesmos testes.

**Scale/Scope**:

- 1 a 2 usuários e uso mensal.
- 4 páginas novas, 5 endpoints novos e 2 tabelas novas.
- Cerca de 45 receptores, 139 semanas.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify against `.specify/memory/constitution.md` v1.1.0:

- [x] **I. Code Quality**:
  - A casca compartilhada (`gui/v2/shell.js`) é usada pelas 4 páginas, o que atende ao mínimo de 3 usos.
  - As regras de Top N, ritmo e crescimento ficam num módulo de serviço (`services/v2_metrics.py`), com funções puras e tipadas, usadas por ranking, evolução e instituição.
  - Não há abstração especulativa.
- [x] **II. Testing**:
  - Teste de integração em SQLite real para cada escrita nova: `api_status_weekly`, `behavior_watch` e a regra do piso.
  - Teste HTTP (caminho feliz + erro) para os 5 endpoints.
  - Roteiro manual no navegador para as 4 páginas e para o legado.
- [~] **III. UX Consistency**:
  - As cores vêm de `constants.py` (`GROUP_COLORS_V2`, `API_GROUPS`) via `/api/v2/meta`, sem hex de dado fixo no HTML/JS.
  - Os tokens de tema ficam em CSS, como no legado.
  - O filtro de grupos tem a mesma semântica da 009.
  - **Desvio:** a persistência usa chaves próprias (`opf:v2:*`) para não colidir com `opf:filters` do legado. Ver Complexity Tracking.
- [x] **IV. Performance**:
  - A consulta nova que cruza várias dimensões (status × transmissor × receptor × semana) usa a pré-agregação nova `api_status_weekly`, preenchida por `scrapers.refresh_api_status_weekly` no fim da coleta, como o princípio pede.
  - Também é chamada por `compute_signals.py`, no mesmo padrão já justificado na 010.
  - Não há caminho de coleta novo.
- [x] **V. Paradigm**:
  - Continuam dois componentes. Só o `data-loader` escreve.
  - As tabelas novas são aditivas; sem ORM; SQL parametrizado.
  - O dashboard só lê `api_status_weekly` e `behavior_watch`. Se faltarem, responde vazio com `unavailable` e não cria nada.
- [ ] **VI. UI Shell Contract**:
  - **Violação até a emenda.** As páginas `/v2` usam outro contrato: 4 abas por pergunta, barra de filtros no topo sem sidebar, tema claro padrão e exportação por bloco.
  - **Resolução:** emendar a Constituição como **primeira tarefa** (v1.1.0 → 1.2.0, MINOR). O §6 atual passa a valer para o legado e entra um §6.8 "Shell v2" baseado em `contracts/v2-ui-shell.md`. Fica permitido o link "Dashboard 2.0" no titlebar do legado, e `html-to-image` entra na tabela de Stack.
  - Feita a emenda, o gate passa. Nenhuma página `/v2` é implementada antes dela.

## Project Structure

### Documentation (this feature)

```text
specs/011-dashboard-v2/
├── spec.md
├── plan.md              # este arquivo
├── research.md          # Fase 0 — 13 decisões
├── data-model.md        # Fase 1 — tabelas novas, regras, entidades de leitura
├── quickstart.md        # Fase 1 — subir, testar, roteiro manual com números da base
├── contracts/
│   ├── v2-api.md        # /api/v2/meta, ranking, evolution, changes, institution/{uuid}
│   └── v2-ui-shell.md   # rotas, esqueleto, controles, estado, tokens, exportação
├── checklists/requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
.specify/memory/constitution.md   # emenda 1.2.0 (Princípio VI §6.8, Stack, III)

data-loader/
├── scrapers.py             # + DDL api_status_weekly e behavior_watch; + refresh_api_status_weekly()
├── collector.py            # + chama refresh_api_status_weekly no fim da coleta (ao lado de refresh_api_group_weekly)
├── signals.py              # piso em únicos; + detect_api_watch() (condições sem confirmação)
├── compute_signals.py      # + refresh_api_status_weekly; grava behavior_watch na mesma transação
└── tests/
    ├── test_signals.py         # + piso em únicos, + behavior_watch
    └── test_api_status_weekly.py   # NOVO — refresh, invariante com api_group_weekly, idempotência

dashboard/
├── server.py               # + rotas /v2, /v2/evolucao, /v2/mudancas, /v2/instituicao; include_router(v2, "/api/v2")
├── routers/
│   └── v2.py               # NOVO — meta, ranking, evolution, changes, institution/{uuid}
├── services/
│   ├── constants.py        # + GROUP_COLORS_V2, GROUP_LABELS_V2
│   └── v2_metrics.py       # NOVO — séries semanais/mensais, ritmo, crescimento, Top N com fixadas/excluídas, oscilação/reincidência
├── gui/
│   ├── dashboard.html, receptor_profile.html, active_consents.html   # + link "Dashboard 2.0" no titlebar (único toque no legado)
│   └── v2/                 # NOVO
│       ├── v2.css          # tokens claro/escuro, header, barra de filtros, cards, ranking, chips
│       ├── shell.js        # header, abas, barra de filtros, estado, preferências, tema, formatação, exportação CSV/PNG
│       ├── index.html      # Quem lidera?            (P1)
│       ├── mudancas.html   # O que mudou?            (P2)
│       ├── instituicao.html# Como opera uma instituição? (P3)
│       └── evolucao.html   # Como evolui?            (P3)
└── tests/
    ├── test_v2_meta_ranking.py   # NOVO (P1)
    ├── test_v2_changes.py        # NOVO (P2)
    ├── test_v2_institution.py    # NOVO (P3)
    └── test_v2_evolution.py      # NOVO (P3)

CLAUDE.md                   # + seção do 2.0 (rotas, tabelas novas, comandos)
```

**Structure Decision**: Nenhum projeto novo. O 2.0 é um conjunto de rotas, de endpoints e uma pasta `gui/v2/` dentro do `dashboard/`. Os cálculos que gravam no banco ficam no `data-loader/`, mantendo a divisão da 010.

## Entrega por fases

| Fase | Conteúdo | Pronto quando |
|---|---|---|
| 0 · Base | Emenda da Constituição 1.2.0; `api_status_weekly` + refresh; `GROUP_COLORS_V2` | Gate VI passa; teste de integração verde |
| 1 · P1 Quem lidera? | `/api/v2/meta`, `/api/v2/ranking`, `v2_metrics` (ritmo, crescimento, Top N), casca `shell.js`/`v2.css`, `/v2`, abas futuras com aviso + link ao legado, link no legado | Roteiro 1–8 do quickstart |
| 2 · P2 O que mudou? + exportação | piso em únicos, `behavior_watch`, `/api/v2/changes`, `/v2/mudancas`, CSV/PNG em todos os blocos | Roteiro 7 e 9 |
| 3 · P3 Instituição | `/api/v2/institution/{uuid}`, `/v2/instituicao`, cliques de nome em todas as abas | Roteiro "Instituição" |
| 4 · P3 Evolução | `/api/v2/evolution`, `/v2/evolucao` | Roteiro "Evolução" |

Cada fase é um PR próprio contra `main`, com deploy independente. A virada do endereço principal para o 2.0 fica fora desta feature (spec, Clarifications).

## Riscos

| Risco | Mitigação |
|---|---|
| `html-to-image` falha com fontes externas ou gráficos | Fonte com `crossorigin`; gráficos Chart.js convertidos em imagem antes da captura; se falhar, mensagem legível e o CSV continua disponível |
| Rebuild de `api_status_weekly` alonga o fim da coleta (~35 s) | Aceitável frente aos ~2 min da 010; mesma tabela reconstruída por `compute_signals.py` quando a coleta não termina |
| Mudança do piso altera o card do legado | Esperado e documentado (spec, Assumptions); teste cobre |
| Nomes curtos de instituição ("ITAÚ UNIBANCO" → "Itaú") | Mapa de nomes curtos em `v2_metrics`, reaproveitando o `LABEL_MAP` existente do backend |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Princípio VI: novo contrato visual para `/v2` (até a emenda) | É o objetivo da feature, com design aprovado pelo responsável do produto. A emenda 1.2.0 é a primeira tarefa e mantém o §6 atual válido para o legado. | Reaproveitar o shell atual: contradiz as decisões aprovadas (abas por pergunta, filtros no topo, tema claro, exportação). |
| Princípio III (persistência de filtros): chaves `opf:v2:*` separadas de `opf:filters` | As duas versões têm filtros diferentes: o 2.0 tem métrica e instituições fixadas, e o legado tem receptor, status e normalize. Compartilhar a chave faria uma versão sobrescrever o estado da outra. | Uma chave só: o legado leria campos que não conhece e vice-versa. A emenda registra a regra "cada shell tem sua chave". |
| Biblioteca nova no frontend (`html-to-image`) fora da tabela de Stack | A exportação de imagem 16:9 de qualquer bloco (FR-011/012) não é possível só com Chart.js, porque os blocos têm tabelas HTML. | Renderizar no servidor exigiria um browser no Cloud Run. Desenhar à mão em Canvas duplicaria cada layout. Registrada na emenda. |

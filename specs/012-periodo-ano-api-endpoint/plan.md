# Implementation Plan: Período "Desde o começo do ano", API por consentimento em "Como evolui?" e visão por endpoint

**Branch**: `012-periodo-ano-api-endpoint` | **Date**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-periodo-ano-api-endpoint/spec.md`

## Summary

Três entregas independentes sobre o Dashboard 2.0, em ordem de prioridade da spec:

1. **P1, período "Desde o começo do ano"**: mudança só de frontend. Hoje a lista de períodos e o cálculo da data inicial estão copiados em três páginas (`index.html`, `evolucao.html`, `instituicao.html`). O plano move os dois para `shell.js` (`V2.PERIODS`, `V2.periodStart`) e acrescenta o período `ytd`. O backend já aceita qualquer `start`, então não muda.
2. **P2, chamadas de API por consentimento em "Como evolui?"**: `/api/v2/evolution` ganha o parâmetro `scale` (`total` | `per_consent`), com a mesma semântica de `/api/v2/ranking`. Nenhuma tabela nova: a série por consentimento sai das funções que o ranking e a aba da instituição já usam. Na escala por consentimento, os blocos de participação vêm marcados como indisponíveis e a página os desativa. A escala por consentimento é o padrão da métrica "Chamadas de API" (Clarifications).
3. **P3, visão por endpoint**: precisa de dado que o dashboard não tem pré-agregado. O `data-loader` ganha a tabela `api_endpoint_weekly` (aditiva), preenchida por `scrapers.refresh_api_endpoint_weekly` no fim da coleta e em `compute_signals.py`. O dashboard ganha o endpoint `GET /api/v2/institution/{uuid}/endpoints`, chamado só quando o usuário abre a visão "Por endpoint". O endpoint `/api/v2/institution/{uuid}` não muda.

## Technical Context

**Language/Version**: Python 3.11+ (data-loader e dashboard; a imagem do dashboard usa 3.11) e JavaScript puro com HTML/CSS, como fixa a Constituição.

**Primary Dependencies**: FastAPI, pandas e cachetools no dashboard; Chart.js e `html-to-image` via CDN no frontend. Nenhuma dependência nova.

**Storage**: SQLite `consents.db`.

- Tabela nova: `api_endpoint_weekly`, criada e escrita só pelo `data-loader`.
- Tabelas lidas: `api_endpoint_weekly`, `endpoint_history` (catálogo), `unique_consents`, `api_status_weekly`, `active_consents`.
- Nenhuma tabela existente muda de esquema.

**Testing**:

- **data-loader:** pytest com SQLite real em memória para o `refresh_api_endpoint_weekly` (valores, parcela sem endpoint, só status 200, exclusão de `consents`, idempotência).
- **dashboard:** pytest com `httpx` contra o app real para o endpoint novo e para `scale` em `/evolution` (caminho feliz e um erro cada), sobre a base sintética de `tests/v2_fixtures.py`, que ganha `api_endpoint_weekly` e `endpoint_history`.
- **Telas:** validação manual em navegador pelo roteiro do `quickstart.md`.
- **Legado e 2.0 existente:** todos os testes atuais continuam passando (SC-005).

**Target Platform**: Cloud Run (dashboard) e máquina local (coleta e cálculo). Navegadores desktop a partir de 1280 px.

**Project Type**: Extensão dos dois componentes existentes. Não há componente novo.

**Performance Goals**: `/api/v2/*` abaixo de 500 ms p95 (Princípio IV) e interações em até 3 s (SC-004). A tabela nova tem na ordem de 10⁵ linhas (a mesma agregação sem filtro de status deu 196.412 linhas em 7,1 s na base atual), e o custo de reconstruí-la no fim da coleta é estimado em 10 a 20 s, a medir.

**Constraints**:

- O dashboard não escreve no banco (Princípio V); se a tabela nova faltar, responde `unavailable` e a tela explica.
- Sem imports cruzados, SQL parametrizado, sem ORM.
- Nenhum valor de tela existente muda, exceto a escala inicial da métrica "Chamadas de API" em "Como evolui?" (SC-005).

**Scale/Scope**: 1 a 2 usuários, uso mensal; 38 receptores com chamadas, 15 APIs com endpoint e 74 endpoints em uso (catálogo com 95), 143 semanas.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verificado contra `.specify/memory/constitution.md` v1.2.0:

- [x] **I. Code Quality**:
  - `V2.PERIODS` e `V2.periodStart` substituem três cópias idênticas (menos código, não mais).
  - O parâmetro `scale` reaproveita `M.per_consent_30d` e `M.paired_sums`; não nasce helper novo para a série por consentimento, porque ela é uma linha de pandas.
  - A única função nova de serviço é a leitura do detalhe por endpoint, usada pelo endpoint novo.
  - Funções públicas com anotações de tipo.
- [x] **II. Testing**:
  - Integração em SQLite real para o `refresh_api_endpoint_weekly` (escrita nova), incluindo idempotência.
  - Teste HTTP (feliz + erro) para o endpoint novo e para `scale`.
  - Roteiro manual no navegador para as três mudanças de tela.
- [x] **III. UX Consistency**:
  - Cores de grupo de API vêm de `API_GROUPS` via `/api/v2/meta`; nenhum hex de dado novo no HTML/JS.
  - O período `ytd` e a escala usam o estado compartilhado `opf:v2:filters` (escreve só os campos próprios e preserva os demais).
  - Carregamento e erro visíveis por card, em português.
- [x] **IV. Performance**:
  - A agregação nova (data × receptor × API × endpoint) usa uma tabela pré-agregada preenchida por `scrapers.refresh_*` no fim da coleta, como o princípio exige; nada de agregação ad hoc sobre `api_requests` (5,9 milhões de linhas) no caminho quente.
  - Nenhum caminho de coleta novo, então a poda por probes não é afetada.
- [x] **V. Paradigm**:
  - Só o `data-loader` escreve; o DDL fica em `scrapers.open_db()`; mudança aditiva.
  - SQL parametrizado, sem ORM, sem import entre componentes.
- [x] **VI. UI Shell**: as três mudanças são em páginas `/v2*` e seguem o §6.8: a barra de filtros mostra só os controles da aba, qualquer mudança recarrega na hora, o estado fica em `opf:v2:filters`, e o código compartilhado vive em `shell.js`.

**Re-avaliação após o desenho (Fase 1)**: sem violações. Duas observações, nenhuma é violação:

- O banco já passa dos 200 MB do Princípio IV (hoje 4,2 GB). A tabela nova acrescenta cerca de 0,3% e não muda esse quadro, que fica fora desta feature.
- A Constituição cita `.\deploy.ps1`; existe agora o `deploy.sh` equivalente (PR #29). Atualizar essa menção é uma emenda de documentação separada.

## Project Structure

### Documentation (this feature)

```text
specs/012-periodo-ano-api-endpoint/
├── spec.md
├── plan.md              # este arquivo
├── research.md          # Fase 0 — 12 decisões
├── data-model.md        # Fase 1 — tabela nova, invariantes, entidades de leitura
├── quickstart.md        # Fase 1 — subir, testar, roteiro manual
├── contracts/
│   └── v2-api-delta.md  # /evolution (scale), /institution/{uuid}/endpoints, mudanças de UI
├── checklists/requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks) — não criado aqui
```

### Source Code (repository root)

```text
data-loader/
├── scrapers.py             # + DDL api_endpoint_weekly (e índices); + refresh_api_endpoint_weekly()
├── collector.py            # + chama refresh_api_endpoint_weekly no fim da coleta
├── compute_signals.py      # + refresh_api_endpoint_weekly (preenche a base já existente)
└── tests/
    └── test_api_endpoint_weekly.py   # NOVO — valores, parcela sem endpoint, status, idempotência

dashboard/
├── routers/v2.py           # + parâmetro scale em /evolution; + GET /institution/{uuid}/endpoints
├── services/v2_metrics.py  # + load_endpoint_weekly(), load_endpoint_catalog()
├── gui/v2/
│   ├── shell.js            # + V2.PERIODS (com ytd) e V2.periodStart() (saem das 3 páginas)
│   ├── index.html          # usa V2.PERIODS / V2.periodStart
│   ├── evolucao.html       # idem; + seletor de escala; blocos de participação desativáveis
│   └── instituicao.html    # idem; + seletor "Por grupo | Por endpoint" e seletor de API
└── tests/
    ├── v2_fixtures.py            # + api_endpoint_weekly e endpoint_history sintéticas
    ├── test_v2_evolution.py      # + casos de scale
    └── test_v2_institution.py    # + casos do endpoint novo

CLAUDE.md                   # + tabela nova e comando de preenchimento; ponteiro do plano
```

**Structure Decision**: Nenhum projeto novo. O que grava no banco fica no `data-loader/`, o que lê e exibe fica no `dashboard/`, mantendo a divisão da 010 e da 011.

## Entrega por fases

| Fase | Conteúdo | Pronto quando |
|---|---|---|
| 1 · P1 Período | `V2.PERIODS` e `V2.periodStart` em `shell.js` com `ytd`; três páginas passam a usá-los; aviso de poucos pontos | Roteiro "Período" do quickstart; nenhuma regressão nos períodos antigos |
| 2 · P2 Escala | `scale` em `/evolution`; seletor e padrão por consentimento; blocos de participação desativados; exportação com a escala | Roteiro "Escala"; SC-002 (igualdade com Quem lidera?) |
| 3 · P3 Endpoint, dados | DDL + `refresh_api_endpoint_weekly` + chamadas no coletor e em `compute_signals.py`; teste de integração | Teste verde; tabela preenchida na base local; invariante da soma verificada |
| 4 · P3 Endpoint, tela | `load_endpoint_*`, endpoint novo, visão "Por endpoint" com seletor de API, exportação | Roteiro "Endpoint"; SC-003 e SC-004 |

Cada fase é um PR próprio contra `main`. A fase 3 exige rodar `compute_signals.py` e sincronizar a base antes de a fase 4 aparecer em produção; sem isso, a tela mostra a mensagem de indisponível.

## Riscos

| Risco | Mitigação |
|---|---|
| Em janeiro, "Desde o começo do ano" tem 1 ou 2 pontos | A página mostra o aviso de FR-005 quando o período tem menos de 3 pontos; o ritmo trimestral usa o histórico inteiro e não depende do período |
| A escala por consentimento vira padrão e desativa os blocos de participação na abertura da métrica de API | Decisão registrada nas Clarifications; o volume fica a um clique e a explicação aparece nos blocos desativados |
| Chamadas da API sem endpoint atribuído (0,44% dos casos medidos) quebram a soma | Linha explícita "Sem endpoint identificado" (`endpoint_id = 0`), calculada no refresh; teste da invariante |
| Base em produção sem a tabela nova | O endpoint responde 200 com `unavailable: ["endpoints"]` e a tela mostra a instrução; a visão por grupo segue intacta |
| O catálogo de endpoints (`endpoint_history`) deixar de cobrir uma API nova | A leitura une o catálogo com os endpoints vistos em `api_endpoint_weekly`, então nunca perde um endpoint usado |

## Complexity Tracking

Sem violações a justificar.

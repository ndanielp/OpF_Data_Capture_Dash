# Implementation Plan: Módulo de Detecção de Mudanças de Comportamento

**Branch**: `010-deteccao-mudancas-comportamento` | **Date**: 2026-09-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-deteccao-mudancas-comportamento/spec.md`

## Summary

Um script novo no `data-loader/`, `compute_signals.py`, roda depois da coleta e antes do
sync. Ele (1) recalcula `api_group_weekly`, (2) aplica as regras da spec sobre
`unique_consents`, `active_consents` e `api_group_weekly`, e (3) reconstrói do zero uma
tabela nova, `behavior_signals`, com uma linha por alerta, para **todo o histórico**. O
dashboard ganha um endpoint `GET /api/signals` que lê essa tabela por semana, aplica o
filtro de grupos de instituição (feature 009) e agrupa por seção e instituição, e um card
"O que mudou" no topo da aba Ecossistema, com seletor de semana.

## Technical Context

**Language/Version**: Python 3.11+ (data-loader e dashboard) + JavaScript puro (frontend) — fixado pela Constituição.

**Primary Dependencies**: pandas (já em ambos os `requirements.txt`) para as janelas móveis e razões; FastAPI no dashboard. **Nenhuma dependência nova** — a calibração inteira foi feita só com pandas.

**Storage**: SQLite `consents.db`. Uma tabela nova, `behavior_signals`, criada e escrita só pelo `data-loader`. Mudança aditiva — nenhuma tabela existente é alterada.

**Testing**: pytest com SQLite real em arquivo temporário no `data-loader` (Princípio II: toda nova escrita no banco precisa de teste de integração sem mock); `httpx.AsyncClient` para o endpoint novo no dashboard; validação manual do card no navegador.

**Target Platform**: `compute_signals.py` roda local (mesma máquina da coleta). Endpoint e card rodam no Cloud Run e no servidor local.

**Project Type**: Extensão dos dois componentes existentes, sem componente novo.

**Performance Goals**: As regras reprocessam ~140 semanas × ~50 receptores × 6 grupos em segundos. O script inteiro leva **~2min20s** na base real (medido em 2026-09-23), quase todo no `refresh_api_group_weekly`, que agrega a tabela `api_requests` inteira — o mesmo custo que a coleta já paga ao terminar. `GET /api/signals` responde em 6–20 ms — bem abaixo do limite de 500 ms p95.

**Constraints**: O dashboard não escreve no banco (Princípio V). O `data-loader` não importa nada do `dashboard/` — o filtro de grupos de instituição é aplicado no dashboard, na leitura.

**Scale/Scope**: ~2 alertas de API + < 1 de consentimentos por semana, ~1 novo entrante por trimestre (spec SC-003) → a tabela inteira terá algumas centenas de linhas.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify against `.specify/memory/constitution.md` v1.1.0:

- [x] **I. Code Quality**: Lógica das regras isolada num módulo `signals.py` com funções puras (uma por regra) e tipadas; `compute_signals.py` é só a entrada de linha de comando. Sem abstração especulativa: nada de "motor de regras" genérico — três regras, três funções.
- [x] **II. Testing**: Teste de integração em SQLite real para a escrita de `behavior_signals`, incluindo idempotência (rodar duas vezes produz exatamente as mesmas linhas). Teste HTTP para `GET /api/signals` (caminho feliz + tabela ausente + filtro de grupo). Validação manual do card.
- [x] **III. UX Consistency**: Cores do card vêm dos tokens CSS já existentes (`--success`, `--error`, `--text-muted`) — nenhum hex novo. O parâmetro `groups` tem a mesma semântica dos 8 endpoints da 009. Estado de carregamento via `setCardLoading()` e mensagem de erro legível.
- [~] **IV. Performance**: O princípio pede que tabelas pré-agregadas novas sejam preenchidas por uma função `scrapers.refresh_*` chamada **no fim de cada coleta**. Aqui o cálculo roda num **processo separado**, por decisão explícita do responsável do produto (spec, Clarifications). Justificado em Complexity Tracking.
- [x] **V. Paradigm**: Continua havendo exatamente **dois componentes**: o script novo mora dentro do `data-loader/`, como o `sync_to_gcs.py`. Quem escreve no banco é só o `data-loader`; o dashboard apenas lê `behavior_signals`. Tabela nova = mudança aditiva, sem migração. SQL parametrizado. Sem imports cruzados.
- [x] **VI. UI Shell Contract**: Nenhuma aba nova (continuam 3). O card usa `.chart-card` com o padrão de carregamento, e entra como bloco em `.main-content`, logo depois da `.date-bar`.

## Project Structure

### Documentation (this feature)

```text
specs/010-deteccao-mudancas-comportamento/
├── spec.md
├── plan.md              # este arquivo
├── research.md          # Fase 0
├── data-model.md        # Fase 1
├── quickstart.md        # Fase 1
├── contracts/
│   ├── compute-signals-cli.md   # contrato do script
│   └── signals-api.md           # contrato do endpoint
├── checklists/requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
data-loader/
├── signals.py              # NOVO — regras puras: novo entrante, variação de consentimentos, variação de API
├── compute_signals.py      # NOVO — entrada: refresh api_group_weekly → trava de cobertura → regras → reconstrói behavior_signals
├── scrapers.py             # + DDL de behavior_signals em open_db() (aditivo)
└── tests/
    └── test_signals.py     # NOVO — integração em SQLite real + idempotência + casos de validação da spec

dashboard/
├── routers/
│   └── signals.py          # NOVO — GET /api/signals (semana, grupos, seções, semanas disponíveis)
├── server.py               # + include_router(signals, prefix="/api/signals")
├── gui/
│   └── dashboard.html      # + card "O que mudou" após a .date-bar, seletor de semana, respeita o filtro de grupos
└── tests/
    └── test_signals_api.py # NOVO

CLAUDE.md                   # + passo `python compute_signals.py` no fluxo de comandos
```

**Structure Decision**: Nenhum diretório novo de projeto. O cálculo fica no `data-loader/` (único lado que escreve no banco) e a leitura/exibição no `dashboard/`, seguindo a mesma divisão da `api_group_weekly`.

## Pipeline resultante

```text
python main.py run          # coleta (pode ser interrompida — não recalcula nada se não terminar)
python compute_signals.py   # NOVO: refresh api_group_weekly + alertas para todo o histórico
.\deploy.ps1 -SyncOnly      # sobe a base
```

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Tabela pré-agregada (`behavior_signals`) preenchida por um processo separado, e não por `refresh_*` no fim da coleta (Princípio IV) | Decisão do responsável do produto (spec, Clarifications). Há também um motivo verificado na base: o refresh no fim da coleta **só roda quando a coleta termina**. As duas últimas coletas (21/09) não terminaram, e por isso `api_group_weekly` está parada em 31/07 enquanto os dados brutos vão até 28/08. Um processo separado pode ser rodado a qualquer momento sobre os dados que existem, sem depender de a coleta ter chegado ao fim. | Chamar o cálculo no fim de `collector.run_collection()`: herdaria exatamente a fragilidade acima — coleta interrompida, alertas e `api_group_weekly` defasados sem aviso. |
| `api_group_weekly` passa a ser recalculada em dois lugares (fim da coleta e `compute_signals.py`) | Os alertas de API dependem dela estar em dia. Os dois lugares chamam a **mesma** função `scrapers.refresh_api_group_weekly`, que reconstrói a tabela inteira e é idempotente. Ambos estão no mesmo componente (`data-loader`). | Deixar só no fim da coleta: os alertas de API usariam dados de semanas diferentes dos de consentimento sempre que uma coleta não terminasse (caso atual). |

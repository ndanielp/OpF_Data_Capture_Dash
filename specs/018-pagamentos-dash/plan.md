# Implementation Plan: Tema Pagamentos no Dashboard 2.0

**Branch**: `018-pagamentos-dash` | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md) | **UX**: [ux-handoff.md](ux-handoff.md)

## Summary

Um seletor "Dados | Pagamentos" no cabeçalho do Dashboard 2.0 abre cinco abas de pagamento (Quem lidera?, Quem paga com quem?, Como evolui?, O que mudou?, Como opera uma instituição?). O coletor passa a manter a pré-agregação `payment_weekly` (endpoints de criação, consulta e vínculo, por semana × iniciadora × detentora × status). O painel lê essa tabela uma vez por versão da base (`services/payments.py`), expõe `/api/v2/payments/{meta,ranking,flows,enrollment,changes,institution}` e as páginas fazem o recorte e as frases de leitura no navegador, com o código comum em `shell.js` (`V2.pay`).

## Technical Context

**Language/Version**: Python 3.11+ (dashboard e data-loader), JS puro (ES2019) no navegador

**Primary Dependencies**: FastAPI, pandas, cachetools (dashboard); sqlite3 (data-loader). Sem biblioteca de gráfico nova: barras, linhas e matriz em HTML/SVG, como no protótipo

**Storage**: SQLite `consents.db`; tabela nova `payment_weekly` (aditiva)

**Testing**: pytest + httpx `AsyncClient` (dashboard, base sintética); pytest com SQLite real (data-loader)

**Target Platform**: Cloud Run (dashboard), máquina local (coletor)

**Project Type**: web-service + páginas estáticas

**Performance Goals**: rotas de pagamento ≤ 500 ms p95 com cache quente; carga da tabela (~142 mil linhas) ≤ 1 s, uma vez por versão da base, aquecida no startup

**Constraints**: painel não cria tabela nem importa o coletor; cores de série de `constants.py`; casca §6.8

**Scale/Scope**: ~60 iniciadoras, ~70 detentoras, 44 semanas; 5 páginas novas, 6 rotas novas

## Constitution Check

Verificado contra `.specify/memory/constitution.md` v2.0.0:

- [x] **I. Code Quality**: um serviço novo (`services/payments.py`) e um roteador novo (`routers/payments.py`); helpers de navegador só os usados por 2+ páginas (`V2.pay`). Anotações em todas as assinaturas públicas.
- [x] **II. Testing**: teste de integração de `refresh_payment_weekly` com SQLite real; teste HTTP de cada rota (caminho feliz + erro + tabela ausente); validação manual no navegador das 5 abas.
- [x] **III. UX Consistency**: cores das APIs de pagamento entram em `constants.py` (`PAYMENT_APIS`, `PAYMENT_HEAT`) e chegam pelo `/meta` de pagamentos; estados de carga e erro com `.v2-card.loading` e `V2.errorBox`; `sessionStorage['opf:v2:filters']` só com campos próprios (`pay_role`, `pay_api`).
- [x] **IV. Performance**: leitura só de `payment_weekly`, populada por `scrapers.refresh_payment_weekly` no fim de `run-pi` e em `compute_signals.py`. Coleta inalterada.
- [x] **V. Paradigm**: nenhuma importação cruzada; SQL sem interpolação de entrada do usuário; mudança de esquema só aditiva.
- [x] **VI. UI Shell**: **exigiu emenda** (feita, T001) de §6.8 — seletor de tema no cabeçalho e lista de abas do tema Pagamentos (5 abas, incluindo "Quem paga com quem?"). Justificativa: decisão do responsável do produto (Opção A, 2026-11-20). Emenda MINOR 2.0.0 → 2.1.0 feita como tarefa desta feature; Princípio III ganha a referência a `PAYMENT_APIS`.

Pós-desenho: mantém-se. Nenhuma outra violação.

## Project Structure

### Documentation (this feature)

```text
specs/018-pagamentos-dash/
├── spec.md · ux-handoff.md · plan.md · research.md · data-model.md · quickstart.md · tasks.md
├── contracts/payments-api.md
└── checklists/requirements.md
```

### Source Code

```text
data-loader/
├── scrapers.py            # DDL payment_weekly + refresh_payment_weekly
├── collector.py           # chama o refresh no fim de run-pi
├── compute_signals.py     # chama o refresh
└── tests/test_payment_weekly.py

dashboard/
├── server.py              # rotas /v2/pagamentos*, roteador de pagamentos, aquecimento
├── routers/payments.py    # /api/v2/payments/*
├── services/payments.py   # carga, normalização, ranking, fluxos, funil, mudanças, instituição
├── services/constants.py  # PAYMENT_APIS, PAYMENT_HEAT, SHORT_NAMES
├── gui/v2/shell.js        # seletor de tema, abas do tema, V2.pay (helpers comuns)
├── gui/v2/v2.css          # estilos do seletor, recorte, passos, funil, matriz
├── gui/v2/pagamentos.html · pagamentos-matriz.html · pagamentos-evolucao.html
├── gui/v2/pagamentos-mudancas.html · pagamentos-instituicao.html
└── tests/pay_fixtures.py · tests/test_payments.py

.specify/memory/constitution.md   # emenda §6.8 e III
CLAUDE.md                         # seção Dashboard 2.0: tema Pagamentos, payment_weekly
```

**Structure Decision**: segue a divisão existente (serviço puro + roteador fino + uma página por aba).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| §6.8 lista 4 abas fixas | O tema Pagamentos tem 5 perguntas (a matriz é nova) e o cabeçalho ganha o seletor de tema | Pôr pagamentos dentro das abas atuais misturaria métricas de natureza diferente (consentimento × transação) em cada página |

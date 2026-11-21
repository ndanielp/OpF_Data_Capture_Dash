# Implementation Plan: Polimento do tema Pagamentos

**Branch**: `019-pagamentos-polish` | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md) | **Revisão**: [usability-review.md](usability-review.md)

## Summary

O tema Pagamentos ganha três coisas:
- **Seletor de mês** compartilhado entre as abas. Barras e linhas mostram os valores ao passar o mouse, e clicar numa barra escolhe o mês.
- **Recorte por inclusão**: começa em "todas" e o usuário adiciona instituições como chips. A busca lista todas as instituições, por volume.
- **Qualquer instituição** nas linhas e colunas da matriz e nas contrapartes da instituição.

O servidor ganha parâmetros opcionais (`month`, `rows`/`cols`, `counterparts`) e o volume mensal no `/meta`. O navegador concentra os componentes novos em `shell.js` (`V2.pay`).

## Technical Context

**Language/Version**: Python 3.11+ (dashboard), JS puro no navegador

**Primary Dependencies**: FastAPI, pandas (sem dependência nova)

**Storage**: SQLite `payment_weekly` (sem mudança de esquema)

**Testing**: pytest + httpx sobre a base sintética `tests/pay_fixtures.py`; validação manual no navegador

**Target Platform**: Cloud Run / local

**Project Type**: web-service + páginas estáticas

**Performance Goals**: rotas ≤ 500 ms com cache quente; troca de mês nas abas de série sem ida ao servidor; troca de escolha ≤ 1 s (SC-004)

**Constraints**: casca §6.8; sem mudança no tema Dados além das opções novas (com padrão igual) do seletor de instituição

**Scale/Scope**: 4 rotas alteradas, 5 páginas alteradas, `shell.js`/`v2.css`

## Constitution Check

Verificado contra `.specify/memory/constitution.md` v2.1.0:

- [x] **I. Code Quality**: componentes novos só onde 3+ páginas usam: seletor de mês (5), barra de recorte (3), dica (3). O seletor de instituição é estendido, não duplicado.
- [x] **II. Testing**: testes HTTP para cada parâmetro novo (caminho feliz + 422); validação manual das 5 abas.
- [x] **III. UX Consistency**: estado em `opf:v2:filters` com campos próprios (`pay_month`, `pay_r`, `pay_c`); cores seguem de `PAYMENT_APIS`; estados de carga e erro como hoje.
- [x] **IV. Performance**: nenhuma consulta nova à base. Tudo sai do quadro já carregado de `payment_weekly`, e as mudanças por mês ficam em cache pela base (R2).
- [x] **V. Paradigm**: só leitura; sem importação cruzada; sem mudança de esquema.
- [x] **VI. UI Shell**: barra de filtros primeiro, "Exportar CSV" à direita (FR-015), cards com cabeçalho e rodapé. Nenhuma emenda.

## Project Structure

### Documentation

```text
specs/019-pagamentos-polish/
├── spec.md · usability-review.md · plan.md · research.md · data-model.md · quickstart.md · tasks.md
├── contracts/payments-api-delta.md
└── checklists/requirements.md
```

### Source Code

```text
dashboard/
├── services/payments.py      # meta.volume, ranking(month), flows(rows, cols), institution(counterparts), changes(month)
├── routers/payments.py       # parâmetros e validação
├── gui/v2/shell.js           # V2.pay.month*, V2.pay.scope (recorte), V2.pay.tip, barras/linhas interativas; picker com all/sort/detail;
│                             # exportImage preserva button[data-keep]
├── gui/v2/v2.css             # seletor de mês, chips do recorte, dica, barras-botão, linhas com pontos
├── gui/v2/pagamentos*.html   # 5 páginas
└── tests/test_payments.py    # casos novos
```

**Structure Decision**: mantém a divisão da 018 (serviço puro + roteador fino + uma página por aba).

## Complexity Tracking

Nenhuma violação.

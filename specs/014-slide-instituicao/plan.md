# Implementation Plan: Exportar "Como opera uma instituição?" como slide

**Branch**: `014-slide-instituicao` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-slide-instituicao/spec.md`

## Summary

Um botão "Exportar slide" na barra de filtros de `/v2/instituicao` baixa um PNG 1600×900 com os indicadores, a evolução, "Quais dados busca" (completo) e os transmissores (sem alertas, taxa de erro nem chamadas por grupo). É só front-end: o slide sai do que a página já carregou. `V2.exportImage` e o slide passam a compartilhar a moldura (título, rodapé de fonte, geração e download do PNG), e `V2.exportSlide` compõe os blocos numa grade 16:9 sem reduzir o texto: só os transmissores são cortados nos maiores itens, com "+N"; "Quais dados busca" sai completo. O gráfico de evolução é redesenhado no tamanho da célula, e não esticado.

## Technical Context

**Language/Version**: JavaScript (navegador, sem build) em `dashboard/gui/v2/`

**Primary Dependencies**: `html-to-image@1.11.11` (CDN, já usada), Chart.js (já usada na página)

**Storage**: N/A (nenhuma tabela, nenhum endpoint, nenhum dado novo)

**Testing**: verificação em Chromium headless (Playwright do data-loader): dimensões e conteúdo do PNG, texto mínimo, ausência de alertas e taxa de erro, diff de pixels zero das 36 imagens por bloco existentes; `pytest` do dashboard e do data-loader sem regressão

**Target Platform**: navegador desktop e celular (a ação existe em qualquer largura; o PNG é sempre 1600×900)

**Project Type**: web-service com front-end estático (FastAPI + HTML/JS)

**Performance Goals**: slide em até 5 s após a página carregar (SC-003)

**Constraints**: texto do slide ≥ `--text-caption` (12px), tokens do design system, nenhuma outra exportação muda

**Scale/Scope**: 1 página, 1 função nova no shell, 1 botão, 1 emenda de regra

## Constitution Check

- [x] **I. Code Quality**: o código comum entre `exportImage` e `exportSlide` é extraído (2 chamadores, a moldura e o download); nada de código morto.
- [x] **II. Testing**: front-end sem teste automatizado no projeto; verificação no navegador com diff de pixels (UI), como nas features 011–013. Nenhum endpoint ou upsert novo.
- [x] **III. UX Consistency**: cores de grupo vindas de `V2.groupColor` (tema escuro incluído); nenhum valor novo.
- [x] **IV. Performance**: sem consulta nova.
- [x] **V. Paradigm**: nenhum import entre componentes, nenhuma alteração de esquema.
- [x] **VI. UI Shell (§6.8)**: página v2 segue o shell v2. A regra "imagem por bloco, um CSV por página" é emendada (Constituição 1.4.0, MINOR) para incluir a exportação de página como slide.

## Project Structure

### Documentation (this feature)

```text
specs/014-slide-instituicao/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
├── contracts/v2-ui-delta.md
├── checklists/requirements.md
└── tasks.md
```

`data-model.md` não se aplica (sem dados novos).

### Source Code (repository root)

```text
dashboard/gui/v2/
├── shell.js          # extrai a moldura de V2.exportImage; adiciona V2.exportSlide
├── v2.css            # .v2-fb-actions (agrupa "Exportar slide" e "Exportar CSV")
└── instituicao.html  # botão, estado, montagem dos blocos e gráfico offscreen
.specify/memory/constitution.md                       # 1.4.0 (§6.8)
specs/011-dashboard-v2/contracts/v2-ui-shell.md       # emenda da regra de exportação
CLAUDE.md                                             # uma linha
```

**Structure Decision**: tudo em `dashboard/gui/v2/`, como as demais exportações. Nenhum arquivo novo no código.

## Complexity Tracking

Sem violações. A emenda da Constituição é uma mudança de regra declarada (FR-010), não um desvio.

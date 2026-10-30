# Tasks: Exportar "Como opera uma instituição?" como slide

**Input**: `specs/014-slide-instituicao/` (spec, plan, research, contracts, quickstart)
**Branch**: `014-slide-instituicao`

## Phase 1: Setup

- [x] T001 Capturar as 36 imagens por bloco das 4 abas (claro/escuro) como linha de base e confirmar que duas capturas seguidas são idênticas

## Phase 2: Foundational (moldura compartilhada)

- [x] T002 Em `dashboard/gui/v2/shell.js`, extrair de `V2.exportImage` a moldura 1600×900 (cabeçalho, rodapé de fonte) e a geração/download do PNG, sem mudar o resultado
- [x] T003 Reexportar as 36 imagens e comparar com a linha de base: diff de pixels zero

## Phase 3: User Story 1 — Baixar o perfil da instituição como slide (P1)

**Goal**: botão "Exportar slide" que baixa o PNG 1600×900 do perfil, sem alertas e sem taxa de erro.
**Independent Test**: quickstart, roteiro manual e verificação headless.

- [x] T004 [US1] Em `dashboard/gui/v2/shell.js`, criar `V2.exportSlide(opts)`: grade por linhas/células, clones dos blocos sem cabeçalho/ações/seletores/rodapé, título e subtítulo de cada bloco, ajuste por corte de itens ("+N") sem reduzir o texto, gráfico redesenhado no tamanho da célula
- [x] T005 [P] [US1] Em `dashboard/gui/v2/v2.css`, `.v2-fb-actions` (agrupa os dois botões à direita, 44 px) e o estilo do slide com tokens existentes
- [x] T006 [US1] Em `dashboard/gui/v2/instituicao.html`: botão "Exportar slide" (desativado sem dados), estado "carregando" que avisa, função que desenha a evolução fora da tela no tamanho da célula, montagem dos blocos (indicadores, evolução, mix, grupos, transmissores) e do título/subtítulo/nome do arquivo
- [x] T007 [US1] Verificar no Chromium headless: 1600×900; sem "Alertas" nem "Taxa de erro"; texto ≥ 12px; sem corte/sobreposição; claro e escuro; visão por grupo e por endpoint; instituição grande e pequena
- [x] T008 [US1] Ajustar densidade/cortes até a verificação passar

## Phase 4: Polish

- [x] T009 [P] Emendar `.specify/memory/constitution.md` (1.4.0, §6.8) e `specs/011-dashboard-v2/contracts/v2-ui-shell.md`
- [x] T010 [P] Atualizar `CLAUDE.md` (uma linha em "Dashboard 2.0")
- [x] T011 Reexportar as 36 imagens (diff zero) e rodar `pytest` do dashboard e do data-loader
- [x] T012 Rodar o roteiro do `quickstart.md` e marcar as tarefas

## Phase 5: Ajuste (2026-10-30)

- [x] T013 Renomear o bloco "Para que usa os dados" para "Quais dados busca" em `dashboard/gui/v2/instituicao.html` (página, imagens e slide)
- [x] T014 Tirar "Chamadas por grupo de API" do slide e reorganizar a grade (evolução e transmissores empilhados; "Quais dados busca" em coluna inteira) em `instituicao.html` e `shell.js` (`stack`, célula completa sem `more`, erro se não couber)
- [x] T015 Verificar "Quais dados busca" completo (5–6 grupos; 7 endpoints), claro e escuro, e que as imagens dos outros blocos seguem iguais (a de "Quais dados busca" muda só o título)
- [x] T016 Atualizar spec, plano, contrato, quickstart, Constituição/contrato do shell e `CLAUDE.md`

## Dependências

T001 → T002 → T003 → T004–T006 → T007 → T008 → T009–T012

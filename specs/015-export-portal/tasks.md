---

description: "Tarefas da feature 015: Portal de exportação de dados"
---

# Tasks: Portal de exportação de dados

**Input**: `/specs/015-export-portal/` (plan.md, spec.md, ux-handoff.md, research.md, data-model.md, contracts/export-api.md, quickstart.md)

**Prerequisites**: plan.md, spec.md

**Tests**: Incluídos. O plano (Constituição II) exige teste HTTP das 5 rotas e a validação manual do [quickstart.md](quickstart.md).

**Organization**: Agrupadas por história de usuário. Todos os caminhos são relativos à raiz do repositório. O dashboard nunca escreve na base (Princípio V).

## Format: `[ID] [P?] [Story] Descrição com caminho`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência de tarefa incompleta)
- **[Story]**: US1 (uma tabela com filtros), US2 (tamanho antes de baixar), US3 (várias tabelas)

---

## Phase 1: Setup

**Purpose**: esqueleto dos arquivos novos e dados de teste

- [x] T001 [P] Criar `dashboard/services/export.py` com docstring do módulo, constantes (`SERVER_SALT`, `SESSION_TTL_S=43200`, `TICKET_TTL_S=60`, `LARGE_ROWS=1_000_000`, `BATCH_ROWS=5000`, `MAX_LIST_ITEMS=200`) e o dicionário `EXPORT_TABLES` (ids `unique`, `active`, `api`, `pay`) com tabela, nome de exibição, nome de arquivo, colunas em português (sem `fetched_at`), filtros aceitos e ordenação, conforme [data-model.md](data-model.md)
- [x] T002 [P] Criar `dashboard/routers/export.py` com `APIRouter(prefix="/api/v2/export")` vazio e a dependência `require_session` (lê `X-Export-Token`; implementada na T006)
- [x] T003 [P] Estender `dashboard/tests/v2_fixtures.py` com dados sintéticos de `payment_api_requests` (semanas 2026-01-02 a 2026-03-27), de `fetch_attempts`/`run_summary` (para provar que não saem) e linhas de `api_requests` nos dois níveis (`endpoint_id = 0` e por endpoint) e com zeros
- [x] T004 [P] Criar `dashboard/tests/test_v2_export.py` com o cliente httpx `ASGITransport`, a fixture que define `OPF_EXPORT_CODE` e uma fixture `session_token` que troca o código por um token

---

## Phase 2: Foundational (bloqueia todas as histórias)

**Purpose**: acesso por código, whitelist e montagem segura do SQL

- [x] T005 Em `dashboard/services/export.py`, implementar `export_code()` (lê `OPF_EXPORT_CODE`; ausente = não configurado), `derive_key()`, `make_token(kind, payload, ttl)` e `verify_token(kind, token)` com HMAC-SHA256 e `hmac.compare_digest`, conforme "Credenciais" do [data-model.md](data-model.md); token e ticket de código antigo ou vencido são recusados
- [x] T006 Em `dashboard/services/export.py`, implementar o limitador de tentativas por IP em memória (janela 10 min, 5 erros, bloqueio 60 s) e `check_code(code, ip)`; em `dashboard/routers/export.py`, implementar `POST /session` (200 com token e `expires_at`, 401, 429 com `Retry-After: 60`), 503 "Exportação não configurada." em todas as rotas sem o código, e `require_session` (401 com a mensagem de código mudado/sessão expirada), conforme [contracts/export-api.md](contracts/export-api.md)
- [x] T007 Em `dashboard/services/export.py`, implementar o modelo `ExportRequest` (pydantic) com validação: `tables` 1–4 e dentro da whitelist, UUID 8-4-4-4-12, slug `[a-z0-9-]+`, listas ≤ 200, `start <= end`, `status` e `level` enumerados; erro vira 422
- [x] T008 Em `dashboard/services/export.py`, implementar `build_query(table_id, req, count=False)`: devolve `(sql, params)` só com nome de tabela e de coluna vindos de `EXPORT_TABLES`, valores por placeholder `?`, listas `IN` só de `?`, filtros que não se aplicam ignorados e devolvidos em `ignored_filters`, nível por `endpoint_id = 0` / `<> 0`, sem filtro em `total` (zeros entram), ordem estável; abrir a base em `mode=ro`
- [x] T009 Em `dashboard/server.py`, incluir o router de export, registrar a rota `/v2/exportar` em `_V2_PAGES` e garantir cabeçalho `Cache-Control: no-store` nas rotas de export
- [x] T010 [P] Em `dashboard/tests/test_v2_export.py`, testes de acesso: código certo (200), errado (401 igual para qualquer erro), 5 erros seguidos (429 + `Retry-After`), sem `OPF_EXPORT_CODE` (503), token ausente/adulterado/vencido/de outro código (401), rota sem token recusada (SC-007)
- [x] T011 [P] Em `dashboard/tests/test_v2_export.py`, testes de whitelist (SC-003): `tables=fetch_attempts`, `run_summary`, `endpoint_history`, `api_group_weekly`, `behavior_signals` e um id inexistente dão 422 em `count` e `ticket`; ticket forjado com tabela fora da whitelist dá 401; `fetched_at` nunca aparece nas colunas

**Checkpoint**: acesso e SQL seguro prontos.

---

## Phase 3: User Story 1 — Exportar uma tabela com filtros (P1) 🎯 MVP

**Goal**: com o código, escolher uma tabela, filtrar por período/receptores (e os filtros próprios da tabela) e baixar um CSV correto.

**Independent Test**: "Consentimentos únicos", 12 meses, receptor NUBANK: o CSV traz só essas semanas e esse receptor, e os totais batem com o painel.

### Tests

- [x] T012 [P] [US1] Em `dashboard/tests/test_v2_export.py`, teste de conteúdo do CSV de `unique`: BOM, linhas `#`, cabeçalho em português, separador `;`, só as linhas dentro do período/receptor, zeros presentes, semana ausente sem linha, totais iguais aos de `GET /api/v2/institution/{uuid}` para a mesma semana (SC-002)
- [x] T013 [P] [US1] Em `dashboard/tests/test_v2_export.py`, testes do nível das chamadas (FR-009, SC-006): `level=api` só com `endpoint_id = 0` e Endpoint vazio; `level=endpoint` só com `<> 0`; nunca os dois no mesmo arquivo; o cabeçalho `#` diz o nível; filtros de transmissor, API e status aplicados em `api` e `pay`
- [x] T014 [P] [US1] Em `dashboard/tests/test_v2_export.py`, testes de `ticket` e `file`: ticket vence em 60 s (401 com a mensagem de link expirado), parâmetros do ticket não mudam pela URL, `Content-Disposition` com `opf-dados-<tabela>-<data>.csv`, `X-Rows-Total`, sem `Content-Length`, 429 com 2 exportações já em andamento

### Implementation

- [x] T015 [US1] Em `dashboard/services/export.py`, implementar `iter_csv(table_id, req, meta)`: gerador que lê com `fetchmany(BATCH_ROWS)` e emite BOM, linhas `#` de descrição (data dos dados, exportado em, tabela e nível, período, filtros, nota de zeros), o cabeçalho e as linhas com `;` e vírgula decimal quando houver decimais (FR-012, FR-014)
- [x] T016 [US1] Em `dashboard/services/export.py`, implementar `ExportSlots` (semáforo de 2 exportações por instância, `try_acquire`/`release`) e `data_through()` (última data da base)
- [x] T017 [US1] Em `dashboard/routers/export.py`, implementar `GET /options` (catálogo: tabelas, colunas, filtros, primeira e última semana, transmissores e APIs) e `POST /ticket` (valida o `ExportRequest`, assina o ticket de 60 s, devolve `url`, `filename`, `expires_in`)
- [x] T018 [US1] Em `dashboard/routers/export.py`, implementar `GET /file?ticket=` com `StreamingResponse` do CSV, headers do contrato (`Content-Type`, `Content-Disposition`, `X-Rows-Total`, `X-Bytes-Estimate`, `Cache-Control: no-store`), 401 de link expirado, 429 quando o semáforo está cheio, e liberação do slot ao fim ou ao desconectar
- [x] T019 [US1] Em `dashboard/routers/export.py`, implementar `GET /count` mínimo (linhas por tabela, `total_rows`, `data_through`, `ignored_filters`; 422 de validação) usando o `build_query(count=True)`
- [x] T020 [P] [US1] Em `dashboard/gui/v2/shell.js`, adicionar a aba "Exportar dados" (`/v2/exportar`) depois de "Como opera uma instituição?" em `TABS`
- [x] T021 [P] [US1] Em `dashboard/gui/v2/v2.css`, adicionar os componentes novos de [ux-handoff.md](ux-handoff.md): `.ex-pick` (opção de tabela com caixa de seleção), `.ex-row` (linha do resumo), `.ex-layout` (duas colunas, resumo fixo ao rolar), `.ex-gate` (card de acesso), usando só tokens do `v2.css`
- [x] T022 [US1] Criar `dashboard/gui/v2/exportar.html` com a casca v2 e a tela 1 "Acesso com código": campo de senha, "Entrar", erros (`role="alert"`, `aria-invalid`), espera de 1 min no 429 com campo desabilitado, token em `sessionStorage['opf:v2:export']`, link "Sair", estado "Exportação não configurada" no 503
- [x] T023 [US1] Em `dashboard/gui/v2/exportar.html`, tela 2: barra de filtros com o período compartilhado e os receptores via `sessionStorage['opf:v2:filters']` (spread, só `period`, `start`, `end`, `receptors`), cards "1. Tabelas" (abre só com "Consentimentos únicos", FR-026) e "2. Filtros" (só os filtros das tabelas marcadas, rótulo com as tabelas a que se aplica, transmissores, APIs, status, nível `.v2-accent` com a ajuda correta do "Por endpoint")
- [x] T024 [US1] Em `dashboard/gui/v2/exportar.html`, card "3. Resumo" básico: contagem por tabela via `/count` a cada mudança de filtro (debounce), botão "Exportar CSV" desabilitado sem tabela ou com 0 linhas, mensagem "Não há dados para os filtros escolhidos", nome do arquivo, download pelo ticket (navegação nativa, `a[download]`); 401 em qualquer rota volta ao estado `locked` mantendo os filtros e mostrando "O código de acesso mudou…" (FR-029)

**Checkpoint**: US1 funciona e se testa sozinha (quickstart passos 1, 2, 5, 7, 8).

---

## Phase 4: User Story 2 — Ver o tamanho antes de baixar (P2)

**Goal**: mostrar linhas e tamanho aproximado, avisar quando grande, e baixar grandes com progresso sem derrubar o painel.

**Independent Test**: "Chamadas de API" sem filtros mostra linhas, tamanho e o aviso de arquivo grande, e o botão segue habilitado; ao restringir o período os números caem e o aviso some.

- [x] T025 [P] [US2] Em `dashboard/tests/test_v2_export.py`, testes de `count`: `bytes_estimate` = linhas × média por tabela, `large` quando `total_rows > 1_000_000` (monkeypatch do limite), `pay` fora de 02/01–27/03/2026 dá `rows: 0`, resposta em cache por parâmetros e mtime da base, período fora da base ajustado
- [x] T026 [US2] Em `dashboard/services/export.py`, adicionar as constantes de média de bytes por linha por tabela (medidas conforme [research.md](research.md) R1/R2), `bytes_estimate()` e o cache `TTLCache` da contagem chaveado por `(request, mtime da base)`; completar `GET /count` em `dashboard/routers/export.py` com `bytes_estimate`, `total_bytes_estimate`, `large` e `period` efetivo
- [x] T027 [US2] Em `dashboard/gui/v2/exportar.html`, completar o resumo: linhas por tabela com observação ("linhas", "linhas · total por API", "sem dados no período"), tamanho aproximado, linha "Total" em 22 px, aviso de arquivo grande em `--osc-bg` com tamanho e tempo estimado (não bloqueia), card em `.loading` e números "—" enquanto conta, rodapé sobre CSV, zeros e descrição
- [x] T028 [US2] Em `dashboard/gui/v2/exportar.html`, download com progresso no Chrome/Edge via `showSaveFilePicker` + `fetch` em streaming: bloco "Baixando…" (`role="progressbar"`, baixado de cerca de total usando `X-Rows-Total`/`X-Bytes-Estimate`), "Cancelar download" (`AbortController`), filtros e tabelas travados até o fim ou cancelamento (FR-027), "Download concluído." e "Exportar de novo"; estado "download interrompido" com "Tentar de novo"
- [x] T029 [US2] Em `dashboard/gui/v2/exportar.html`, fallback de download nativo (Safari, Firefox): iniciar pela navegação do ticket, mostrar "Download iniciado: acompanhe o progresso e cancele pelo gerenciador de downloads do navegador." e destravar os filtros em 3 s (research R5)
- [x] T030 [P] [US2] Em `dashboard/deploy.sh` e `dashboard/deploy.ps1`, adicionar `--timeout 3600` e `--set-secrets OPF_EXPORT_CODE=opf-export-code:latest` ao `gcloud run deploy`, sem o código em nenhum arquivo do repositório (FR-021)

**Checkpoint**: US2 funciona (quickstart passos 3 e 6).

---

## Phase 5: User Story 3 — Exportar várias tabelas de uma vez (P3)

**Goal**: um único `.zip` com um CSV por tabela e um `LEIAME.txt`.

**Independent Test**: "Consentimentos únicos" + "Consentimentos ativos" baixam um `.zip` com 2 CSVs e o `LEIAME.txt`; o filtro de transmissor aparece como "não se aplica" para os únicos.

- [x] T031 [P] [US3] Em `dashboard/tests/test_v2_export.py`, teste do ZIP: nome `opf-dados-<data>.zip`, `Content-Type: application/zip`, conteúdo `LEIAME.txt` + um CSV por tabela (sem linhas `#`), cada CSV só com as linhas filtradas, "não se aplica" no `LEIAME.txt` para filtros que a tabela não aceita, colunas explicadas
- [x] T032 [US3] Em `dashboard/services/export.py`, implementar `iter_zip(req, meta)`: ZIP em streaming (`zipfile` com buffer sem seek, `ZIP_DEFLATED`), `LEIAME.txt` primeiro (data dos dados, filtros efetivos por tabela, "não se aplica", dicionário de colunas) e depois um CSV por tabela reutilizando `iter_csv(..., with_header_comments=False)`
- [x] T033 [US3] Em `dashboard/routers/export.py`, fazer `GET /file` e `POST /ticket` escolherem CSV ou ZIP conforme o número de tabelas, com `filename` e `Content-Type` do contrato
- [x] T034 [US3] Em `dashboard/gui/v2/exportar.html`, botão "Exportar N arquivos (.zip)" e nome `opf-dados-<data>.zip`, mais a linha de rodapé que diz que a descrição vai num arquivo dentro do `.zip`; manter as preferências (tabelas e nível) em `localStorage['opf:v2:export-prefs']`

**Checkpoint**: US3 funciona (quickstart passo 4).

---

## Phase 6: Polish e governança

- [x] T035 [P] Em `dashboard/gui/v2/exportar.html` e `dashboard/gui/v2/v2.css`, layout de celular abaixo de 720 px: coluna única, período em duas linhas, "De/Até" lado a lado, barra fixa no rodapé (`.ex-mobilebar`) com total, tamanho, nº de arquivos e botão, alvos de toque ≥ 44 px
- [x] T036 [P] Em `dashboard/gui/v2/exportar.html`, revisão de acessibilidade e tema: `aria-pressed` nos segmentados, `role="status"`/`aria-live="polite"` no resumo, `role="alert"` nos erros, tema claro/escuro só com tokens existentes
- [x] T037 [P] Em `dashboard/tests/test_v2_export.py`, teste de concorrência: com 2 exportações abertas a terceira recebe 429, e `/api/v2/meta` continua respondendo enquanto elas rodam (SC-005a)
- [x] T038 [P] Emendar `.specify/memory/constitution.md` §6.8 (MINOR): incluir "Exportar dados → `/v2/exportar`" como quinta aba e isentar essa aba do botão "Exportar CSV" na barra de filtros (o botão fica no card "3. Resumo"), atualizando a versão e a data da emenda
- [x] T039 [P] Em `CLAUDE.md`, na seção Dashboard 2.0, adicionar a aba "Exportar dados" na tabela de páginas, descrever `routers/export.py`, `services/export.py`, `OPF_EXPORT_CODE` (Secret Manager) e `--timeout 3600`
- [x] T040 Rodar `cd dashboard && pytest tests/ -q` e corrigir regressões nas abas existentes
- [x] T041 Executar o roteiro manual de [quickstart.md](quickstart.md) (9 passos) no navegador, incluindo a exportação completa de "Chamadas de API", "Tudo", "Por endpoint", e registrar o resultado em `specs/015-export-portal/checklists/requirements.md`

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** → histórias. Phase 2 bloqueia todas.
- **US1 (P1)** depende só da Phase 2. É o MVP.
- **US2 (P2)** depende da US1 (`/count` e a página). T030 (deploy) não depende de nada além da Phase 1.
- **US3 (P3)** depende da US1 (`iter_csv`, `/ticket`, `/file`); independe da US2.
- **Polish** depois das histórias desejadas. T038 e T039 podem ir em paralelo desde a Phase 3.

Dentro de cada história: testes primeiro (devem falhar), depois serviço, router, página.

### Parallel opportunities

- Phase 1: T001–T004 juntas.
- Phase 2: T010 e T011 juntas, depois de T005–T009.
- US1: T012–T014 juntas; T020 e T021 juntas e em paralelo com T015–T019.
- US2: T025 e T030 em paralelo com T026.
- Polish: T035–T039 juntas.

## Implementation Strategy

1. **MVP**: Phases 1, 2 e 3. Já entrega a aba com código, uma ou mais tabelas em CSV (várias tabelas só com US3) e filtros.
2. Acrescentar US2 (tamanho, aviso e progresso) e validar com a tabela grande.
3. Acrescentar US3 (ZIP).
4. Polish e governança no mesmo PR. A emenda do §6.8 (T038) é obrigatória antes do merge.

Antes do deploy: criar o segredo `opf-export-code` e dar acesso à conta do Cloud Run ([quickstart.md](quickstart.md)).

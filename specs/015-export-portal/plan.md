# Implementation Plan: Portal de exportação de dados

**Branch**: `015-export-portal` | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/015-export-portal/spec.md` · UX: [ux-handoff.md](ux-handoff.md)

## Summary

Nova quinta aba do Dashboard 2.0, "Exportar dados" (`/v2/exportar`), protegida por um código de acesso. O usuário escolhe uma ou mais das quatro tabelas coletadas (consentimentos únicos, consentimentos ativos, chamadas de API e iniciação de pagamento), aplica filtros, vê quantas linhas e quanto espaço a exportação terá e baixa um CSV, ou um `.zip` quando escolhe várias tabelas.

O backend é um router novo, `/api/v2/export/*`, somente leitura. A whitelist de tabelas e colunas é fechada, os SQLs são parametrizados e o arquivo sai em streaming com memória constante. O acesso usa um token HMAC derivado do código e, para baixar, um ticket de 60 s, sem estado no servidor, então funciona entre as instâncias do Cloud Run e se invalida sozinho quando o código muda. Não há limite de linhas, mas no máximo 2 exportações simultâneas por instância e tempo limite de 1 h no Cloud Run.

## Technical Context

**Language/Version**: Python 3.11+ (dashboard), JavaScript ES2020 sem build (frontend)

**Primary Dependencies**: FastAPI + Uvicorn (já existentes), `cachetools.TTLCache`; da biblioteca padrão, `csv`, `zipfile`, `hmac`, `hashlib`, `io` e `sqlite3`. Nenhuma dependência nova.

**Storage**: SQLite `consents.db`, só leitura (`mode=ro`). Nenhuma tabela, coluna ou índice novo.

**Testing**: pytest + httpx `ASGITransport` contra uma base SQLite sintética (`tests/v2_fixtures.py`, estendida), mais a validação manual em [quickstart.md](quickstart.md).

**Target Platform**: Cloud Run (us-central1, 2 vCPU, 8 GiB, até 3 instâncias) e navegadores modernos. O progresso dentro da página existe só no Chrome e no Edge (`showSaveFilePicker`).

**Project Type**: web service (FastAPI) + páginas estáticas do Dashboard 2.0

**Performance Goals**: contagem ≤ 500 ms p95 no período padrão e ≤ 2 s em qualquer filtro (SC-004); primeiro byte do download em ≤ 10 s (SC-005); a tabela de chamadas inteira (6,3 M linhas, ~1 GB) termina sem erro (SC-005a).

**Constraints**: memória constante por exportação (lotes de 5.000 linhas); no máximo 2 exportações simultâneas por instância; `--timeout 3600` no Cloud Run; o dashboard nunca escreve na base; o código nunca fica no repositório.

**Scale/Scope**: 4 tabelas, a maior com 6.277.798 linhas; 1 aba nova; 5 rotas novas; 1 emenda na constituição.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verificado contra `.specify/memory/constitution.md`:

- [x] **I. Code Quality**: um módulo de serviço (`services/export.py`) e um router (`routers/export.py`), sem abstração nova além da whitelist, que é um dado. Assinaturas públicas tipadas.
- [x] **II. Testing**: sem upsert novo. Teste HTTP para as 5 rotas (caminho feliz e erros: código errado, bloqueio, token de outro código, tabela fora da whitelist, ticket vencido, conteúdo do CSV e do ZIP). Validação manual no navegador ([quickstart.md](quickstart.md)).
- [x] **III. UX Consistency**: sem cores de série, só os tokens do `v2.css`. O período e os receptores usam `sessionStorage['opf:v2:filters']` com spread. Carregamento com `.v2-card.loading` e erros legíveis.
- [x] **IV. Performance**: a exportação lê linha a linha e não agrega entre dimensões, então a regra de pré-agregação não se aplica. A contagem é `COUNT(*)` coberto por índices que já existem (R1, até 0,53 s no pior caso) e fica em cache. A coleta não muda.
- [x] **V. Paradigm**: nenhum import entre componentes; SQL parametrizado (as listas `IN` só com placeholders e os nomes de tabela e coluna vindos da whitelist, nunca do usuário); nenhuma mudança de schema; o código vem de variável de ambiente (`OPF_EXPORT_CODE`), seguindo o padrão env → padrão local → Cloud Run.
- [ ] **VI. UI Shell**: **precisa de emenda**. O §6.8 lista quatro abas e exige um "Exportar CSV" na barra de filtros de toda página v2. A emenda MINOR (R8) entra no mesmo PR: inclui "Exportar dados → `/v2/exportar`" e isenta esta aba do botão na barra, porque o botão fica no card "3. Resumo". Ver Complexity Tracking.

**Pós-design (Phase 1)**: os mesmos resultados. O contrato não cria rota que aceite nome de tabela livre, e o streaming não escreve na base nem em disco. O único item pendente é a emenda do VI, que é uma tarefa explícita.

## Project Structure

### Documentation (this feature)

```text
specs/015-export-portal/
├── spec.md
├── ux-handoff.md          # layout aprovado (protótipo no canvas)
├── plan.md                # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── export-api.md
├── checklists/requirements.md
└── tasks.md               # /speckit-tasks
```

### Source Code (repository root)

```text
dashboard/
├── services/
│   └── export.py           # NOVO: EXPORT_TABLES (whitelist), montagem do SQL, contagem,
│                           #       geradores CSV/ZIP em streaming, token/ticket HMAC, limitador
├── routers/
│   └── export.py           # NOVO: /api/v2/export/{session,options,count,ticket,file}
├── server.py               # inclui o router; rota /v2/exportar em _V2_PAGES
├── gui/v2/
│   ├── exportar.html       # NOVO: a aba (blocos 1–3, estados, download)
│   ├── shell.js            # TABS ganha "Exportar dados"
│   └── v2.css              # componentes novos: .ex-pick, .ex-row, .ex-progress, .ex-mobilebar
├── tests/
│   ├── v2_fixtures.py      # + payment_api_requests e fetch_attempts sintéticas
│   └── test_v2_export.py   # NOVO
├── deploy.sh / deploy.ps1  # --set-secrets OPF_EXPORT_CODE=…, --timeout 3600
.specify/memory/constitution.md   # emenda §6.8 (MINOR)
CLAUDE.md                         # seção Dashboard 2.0: a nova aba
```

**Structure Decision**: segue a divisão do Dashboard 2.0, com router fino, regras em `services/` e uma página HTML por aba que usa `shell.js` e `v2.css`. O router fica separado de `routers/v2.py`, que já tem 800 linhas, mas sob o mesmo prefixo `/api/v2`.

## Fases de implementação (para /speckit-tasks)

1. **Base e acesso**: `services/export.py` (whitelist, token, ticket, limitador de tentativas), as rotas `session` e `options`, a página com a tela de código e a aba nova no `shell.js`. Testes de acesso.
2. **US1, uma tabela**: SQL por tabela e filtro, `count`, `ticket`, `file` (CSV em streaming com cabeçalho `#`), os blocos "1. Tabelas", "2. Filtros" e "3. Resumo" e o download (nativo e com progresso). Testes de conteúdo e conferência de totais com o `/api/v2`.
3. **US2, tamanho**: estimativa de bytes, aviso acima de 1 M linhas, cache da contagem, estados de carregamento e vazio.
4. **US3, várias tabelas**: ZIP em streaming com `LEIAME.txt`, filtros "não se aplica".
5. **Robustez**: semáforo de 2 exportações, `--timeout 3600`, `--set-secrets`, erros e estados do [ux-handoff.md](ux-handoff.md), layout de celular.
6. **Governança**: emenda §6.8, `CLAUDE.md`, `quickstart.md` revisado.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| §6.8: uma quinta aba e o botão de exportar fora da barra de filtros | O usuário pediu "nova tab", e o conteúdo da aba é a própria exportação | Pôr a exportação dentro de uma aba existente não tem lugar natural para escolher tabelas, e um botão "Exportar CSV" na barra duplicaria o botão do resumo. Resolvido por emenda MINOR no mesmo PR. |
| Estado em memória para as tentativas de código (por instância) | FR-028 pede desacelerar tentativa e erro | Um contador compartilhado exigiria um serviço externo ou escrita na base (proibida). Com 3 instâncias o limite efetivo é 15 tentativas por 10 min, aceitável com um código longo (R4). |

# Tasks: Revisão do Deploy no Google Cloud

**Input**: Design documents from `/specs/008-revise-gcp-deploy/`

**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/deploy-script.md ✅

**Status pré-existente**: `entrypoint.sh`, `entrypoint.py`, `Dockerfile` e memória `4Gi` já aplicados na branch. O trabalho restante concentra-se em `deploy.ps1`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependências)
- **[Story]**: User story a que a task pertence

---

## Phase 1: Setup (Pré-requisito de infraestrutura)

**Purpose**: Garantir que o Cloud Build API esteja habilitado no projeto GCP antes de qualquer deploy.

- [ ] T001 Habilitar Cloud Build API no projeto: `gcloud services enable cloudbuild.googleapis.com --project opf-dash`

**Checkpoint**: `gcloud services list --project opf-dash | grep cloudbuild` retorna `ENABLED`.

---

## Phase 2: Foundational (Verificação dos artefatos já aplicados)

**Purpose**: Confirmar que entrypoint.py, entrypoint.sh e Dockerfile estão corretos antes de ajustar o deploy.ps1.

- [x] T002 [P] Verificar que `dashboard/entrypoint.sh` contém apenas `exec python /app/entrypoint.py`
- [x] T003 [P] Verificar que `dashboard/entrypoint.py` existe e contém `threading.Thread(target=_download_db, daemon=True)` + `os.execvp("uvicorn", ...)`
- [x] T004 [P] Verificar que `dashboard/Dockerfile` inclui `COPY entrypoint.py /app/entrypoint.py`

**Checkpoint**: Os três arquivos estão corretos — pode prosseguir com deploy.ps1.

---

## Phase 3: User Story 1 — Deploy sem Docker local (Priority: P1) 🎯 MVP

**Goal**: `.\deploy.ps1` conclui com sucesso sem Docker instalado ou em execução.

**Independent Test**: Executar `.\deploy.ps1 -SkipSync` em máquina sem Docker ativo; revisão Cloud Run fica "Healthy".

### Implementation

- [x] T005 [US1] Remover bloco "Verificar Docker" de `dashboard/deploy.ps1` (linhas com `docker info`, erro se Docker não estiver rodando)
- [x] T006 [US1] Substituir etapa `docker build` em `dashboard/deploy.ps1`: trocar `docker build -t $IMAGE .` por `& $GCLOUD builds submit --tag $IMAGE . --project $PROJECT_ID`
- [x] T007 [US1] Remover etapa "Autenticar Docker no Artifact Registry" de `dashboard/deploy.ps1` (bloco `docker login`)
- [x] T008 [US1] Remover etapa "Enviar imagem" de `dashboard/deploy.ps1` (bloco `docker push $IMAGE`)
- [x] T009 [US1] Atualizar numeração dos passos e mensagens `Write-Step` em `dashboard/deploy.ps1` para refletir o novo fluxo: Sync → Build (Cloud Build) → Deploy
- [ ] T010 [US1] Executar `.\deploy.ps1 -SkipSync` e confirmar que o build ocorre via Cloud Build sem Docker

**Checkpoint**: Deploy completa sem Docker. Revisão aparece como "Healthy" no Cloud Run.

---

## Phase 4: User Story 2 — Cloud Run com 4 GiB fixo (Priority: P2)

**Goal**: Toda revisão criada pelo script tem exatamente 4 GiB de memória.

**Independent Test**: Após deploy, `gcloud run services describe opf-dashboard --region us-central1 --format "value(spec.template.spec.containers[0].resources.limits.memory)"` retorna `4Gi`.

### Implementation

- [x] T011 [US2] Confirmar que `dashboard/deploy.ps1` contém `--memory 4Gi` e `--cpu-boost` no bloco `gcloud run deploy`
- [ ] T012 [US2] Executar deploy completo e verificar no Cloud Run Console que a nova revisão tem 4 GiB de memória alocada

**Checkpoint**: Memória = 4 GiB em todas as revisões criadas pelo script.

---

## Phase 5: User Story 3 — Flags -SkipSync e -SyncOnly (Priority: P3)

**Goal**: As flags de controle de sync continuam funcionando com o novo mecanismo de build remoto.

**Independent Test**: `.\deploy.ps1 -SyncOnly` termina sem acionar build; `.\deploy.ps1 -SkipSync` termina sem acionar sync.

### Implementation

- [ ] T013 [US3] Executar `.\deploy.ps1 -SyncOnly` e confirmar que apenas `sync_to_gcs.py` é chamado (sem `gcloud builds submit` nem `gcloud run deploy`)
- [ ] T014 [US3] Executar `.\deploy.ps1 -SkipSync` e confirmar que `gcloud builds submit` e `gcloud run deploy` ocorrem sem chamada a `sync_to_gcs.py`

**Checkpoint**: Flags funcionam corretamente — fluxos parciais operacionais.

---

## Phase 6: Polish & Cross-Cutting

**Purpose**: Limpeza final e documentação.

- [x] T015 [P] Atualizar comentário de cabeçalho em `dashboard/deploy.ps1` removendo menções a Docker Desktop
- [x] T016 [P] Atualizar `CLAUDE.md` (seção "Commands > dashboard") para refletir que o deploy não requer Docker local
- [ ] T017 Executar validação do `specs/008-revise-gcp-deploy/quickstart.md`: testar o dev local com `uvicorn` sem Docker e confirmar que funciona

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Sem dependências — executar imediatamente
- **Phase 2 (Foundational)**: Depende de Phase 1 · T002–T004 paralelos entre si
- **Phase 3 (US1)**: Depende de Phase 2 · T005–T009 sequenciais (mesmo arquivo) · T010 após T009
- **Phase 4 (US2)**: Depende de Phase 3 (precisa de deploy funcional para verificar memória)
- **Phase 5 (US3)**: Pode rodar em paralelo com Phase 4 após Phase 3
- **Phase 6 (Polish)**: Após Phases 4 e 5

### Dentro de Phase 3 (US1)

T005 → T006 → T007 → T008 → T009 → T010 (mesmo arquivo `deploy.ps1`; estritamente sequencial)

---

## Parallel Example: Phase 2

```
T002: verificar entrypoint.sh
T003: verificar entrypoint.py      ← rodar em paralelo
T004: verificar Dockerfile
```

---

## Implementation Strategy

### MVP (User Story 1 apenas)

1. Phase 1: Habilitar Cloud Build API (T001)
2. Phase 2: Verificar artefatos existentes (T002–T004)
3. Phase 3: Atualizar deploy.ps1 (T005–T010)
4. **PARAR e VALIDAR**: deploy funciona sem Docker
5. Prosseguir com US2 e US3 (verificações de configuração já aplicada)

### Entrega Incremental

1. T001–T004 → pré-condições verificadas
2. T005–T010 → deploy sem Docker funcionando (MVP!)
3. T011–T012 → memória 4Gi confirmada
4. T013–T014 → flags de sync validadas
5. T015–T017 → polish e documentação

---

## Notes

- T005–T009 modificam o mesmo arquivo (`deploy.ps1`) → sequenciais obrigatórios
- T002–T004 são verificações (leitura de arquivo) → paralelos seguros
- T010, T012, T013, T014 são testes manuais (execução do script) → não paralelos (mesmo ambiente)
- Steps de validação (T010, T012–T014) requerem acesso ao GCP autenticado

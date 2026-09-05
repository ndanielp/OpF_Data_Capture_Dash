# Implementation Plan: Revisão do Deploy no Google Cloud

**Branch**: `008-revise-gcp-deploy` | **Date**: 2026-05-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-revise-gcp-deploy/spec.md`

## Summary

Eliminar a dependência do Docker Desktop no fluxo de deploy local, substituindo `docker build` + `docker push` por `gcloud builds submit --tag $IMAGE .` (Google Cloud Build). Ao mesmo tempo, fixar a memória do Cloud Run em 4 GiB e garantir que o container suba rapidamente via entrypoint Python que inicia uvicorn imediatamente (download do DB em background).

## Technical Context

**Language/Version**: PowerShell 7+ (deploy script) · Python 3.11 (entrypoint)

**Primary Dependencies**: `gcloud` CLI · Google Cloud Build API · Artifact Registry · Cloud Run

**Storage**: N/A (esta feature não altera o banco de dados)

**Testing**: Manual — executar `.\deploy.ps1` sem Docker ativo e verificar revisão "Healthy" no Cloud Run com 4 GiB.

**Target Platform**: Windows (script local) + Linux (container Cloud Run)

**Project Type**: Infrastructure / DevOps script

**Performance Goals**: Container startup < 4 min (timeout Cloud Run); uvicorn deve vincular à porta em < 30 s.

**Constraints**: Sem Docker Desktop no ambiente local; máximo 4 GiB de memória no Cloud Run.

**Scale/Scope**: Pipeline de deploy de um único desenvolvedor.

## Constitution Check

*GATE: Verificado antes do Phase 0. Re-verificado após Phase 1.*

- [x] **I. Code Quality**: Nenhuma nova abstração. `entrypoint.py` é um script simples, sem helpers desnecessários. Remoção de código morto (bloco Docker no deploy.ps1).
- [x] **II. Testing**: Feature de infraestrutura — teste é manual (deploy end-to-end). Sem novos endpoints FastAPI nem upserts SQLite.
- [x] **III. UX Consistency**: N/A — não há mudança em UI.
- [x] **IV. Performance**: O entrypoint inicia uvicorn imediatamente (< 30 s); download do DB ocorre em background, dentro do timeout de startup de 4 min do Cloud Run.
- [x] **V. Paradigm**: Nenhuma mudança em imports entre componentes. Nenhuma query SQL nova. `entrypoint.py` pertence ao componente `dashboard/`.
- [x] **VI. UI Shell Contract**: N/A — não há mudança em páginas HTML.

Nenhuma violação. Nenhuma justificativa de complexidade necessária.

## Project Structure

### Documentation (this feature)

```text
specs/008-revise-gcp-deploy/
├── plan.md              ← este arquivo
├── research.md          ← decisões de tecnologia (Cloud Build, entrypoint)
├── data-model.md        ← entidades de configuração e fluxo de dados
├── quickstart.md        ← como usar o deploy revisado
├── contracts/
│   └── deploy-script.md ← interface pública de deploy.ps1 e entrypoint.py
└── tasks.md             ← gerado por /speckit-tasks
```

### Source Code (arquivos alterados)

```text
dashboard/
├── deploy.ps1           # Remove Docker; usa gcloud builds submit
├── entrypoint.sh        # 1 linha: exec python /app/entrypoint.py
├── entrypoint.py        # NOVO: startup Python com download GCS em background
└── Dockerfile           # Adiciona COPY entrypoint.py /app/entrypoint.py
```

## Implementation Steps

### Step 1 — Habilitar Cloud Build API (pré-requisito manual)

```powershell
gcloud services enable cloudbuild.googleapis.com --project opf-dash
```

Executar uma única vez. Pode já estar habilitado.

### Step 2 — Atualizar deploy.ps1

1. **Remover** bloco "Verificar Docker" (`docker info`).
2. **Substituir** `docker build -t $IMAGE .` por `gcloud builds submit --tag $IMAGE . --project $PROJECT_ID`.
3. **Remover** bloco `docker login` inteiro.
4. **Remover** bloco `docker push $IMAGE` inteiro.
5. **Atualizar** numeração e mensagens dos passos restantes.
6. **Manter** `gcloud run deploy` com `--memory 4Gi` e `--cpu-boost`.

### Step 3 — entrypoint.sh (já aplicado)

```sh
#!/bin/sh
exec python /app/entrypoint.py
```

### Step 4 — entrypoint.py (já aplicado)

Inicia download do DB em daemon thread e chama `os.execvp("uvicorn", ...)` imediatamente.

### Step 5 — Dockerfile (já aplicado)

```dockerfile
COPY entrypoint.py /app/entrypoint.py
```

### Step 6 — Validação

```powershell
cd dashboard
.\deploy.ps1 -SkipSync
```

Verificar: build sem Docker · revisão "Healthy" · memória = 4 GiB · dashboard acessível.

## Complexity Tracking

Nenhuma violação de constituição identificada. Seção omitida.

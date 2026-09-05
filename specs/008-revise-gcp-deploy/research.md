# Research: Revisão do Deploy no Google Cloud

## Decision 1: Mecanismo de build da imagem sem Docker local

**Decision**: Substituir `docker build` + `docker push` por `gcloud builds submit --tag $IMAGE .`

**Rationale**: O `gcloud builds submit` envia o código-fonte para o Google Cloud Build, que constrói a imagem usando o Dockerfile existente e faz push direto para o Artifact Registry. Não há dependência do daemon Docker local. O restante do pipeline (`gcloud run deploy --image $IMAGE`) permanece igual.

**Alternatives considered**:
- `gcloud run deploy --source`: faz build + deploy em um passo, porém menos controle; em projetos sem Dockerfile explícito pode usar buildpacks. Descartado por não seguir a separação atual de etapas.
- Manter Docker local: descartado — é exatamente o requisito que queremos eliminar.

**Prerequisite no GCP**: Cloud Build API (`cloudbuild.googleapis.com`) deve estar habilitada no projeto `opf-dash`. O service account do Cloud Build (`<project-number>@cloudbuild.gserviceaccount.com`) precisa da role `Artifact Registry Writer` no repositório `opf-repo`.

---

## Decision 2: Entrypoint do container

**Decision**: Manter a abordagem com `entrypoint.sh` (1 linha: `exec python /app/entrypoint.py`) + `entrypoint.py` (download GCS em background thread + `os.execvp` para uvicorn).

**Rationale**: A causa raiz dos timeouts de startup foi o download síncrono do DB antes de uvicorn vincular à porta. O Python entrypoint inicia o download em uma daemon thread e chama `os.execvp("uvicorn", ...)` imediatamente — o container fica "Healthy" em segundos. Eliminando heredocs no shell também remove uma fonte de bugs de CRLF/indentação.

**Alternatives considered**:
- Shell com download em background (`python script &`): funciona, mas heredocs em Windows-CRLF introduziram falhas silenciosas.
- Mover download para o lifespan FastAPI: mais elegante a longo prazo, mas exige refatoração de `config.py` (DB_PATH resolução em runtime) — escopo maior que o necessário.

---

## Decision 3: Configuração de memória do Cloud Run

**Decision**: Fixar `--memory 4Gi` no `deploy.ps1` (já aplicado). Manter `--cpu-boost` para reduzir cold start.

**Rationale**: Revisões com 2048Mi falhavam consistentemente. A revisão 00029 com 4Gi foi estável. O pandas + DB na memória durante a inicialização exige > 2Gi.

---

## Decision 4: Remoção da dependência de Docker no prereq check

**Decision**: Remover o bloco que verifica se o Docker Desktop está rodando (`docker info`). Substituir por verificação de que `gcloud` CLI está disponível e autenticado.

**Rationale**: Com Cloud Build, não há necessidade de Docker local em nenhuma etapa do pipeline.

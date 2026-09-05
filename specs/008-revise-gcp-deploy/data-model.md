# Data Model: Revisão do Deploy no Google Cloud

Esta feature não introduz novos modelos de dados no banco SQLite. Os "dados" desta feature são configurações de infraestrutura e arquivos de script.

## Entidades de Configuração

### Cloud Run Service (opf-dashboard)

| Campo | Valor fixado | Nota |
|---|---|---|
| `--memory` | `4Gi` | Mínimo viável para pandas + DB em memória |
| `--cpu` | `1` | Sem mudança |
| `--cpu-boost` | presente | Reduz cold start |
| `--min-instances` | `0` | Sem mudança |
| `--max-instances` | `3` | Sem mudança |
| `--port` | `8000` | Sem mudança |

### Arquivos alterados

| Arquivo | Papel | Mudança |
|---|---|---|
| `dashboard/deploy.ps1` | Script de deploy principal | Remove Docker; usa Cloud Build |
| `dashboard/entrypoint.sh` | Entrypoint shell do container | Delega para entrypoint.py |
| `dashboard/entrypoint.py` | Lógica de startup do container | Download GCS em background |
| `dashboard/Dockerfile` | Definição da imagem | Inclui entrypoint.py no COPY |

### Fluxo de dados pós-mudança

```
deploy.ps1
  ├─ (sync) sync_to_gcs.py → GCS bucket
  ├─ (build) gcloud builds submit --tag $IMAGE .
  │     └─ Cloud Build lê Dockerfile → build → push para Artifact Registry
  └─ (deploy) gcloud run deploy --image $IMAGE
        └─ Cloud Run puxa imagem do Artifact Registry → inicia container
              └─ entrypoint.sh → entrypoint.py
                    ├─ thread: download consents.db do GCS (background)
                    └─ os.execvp → uvicorn server:app (imediato)
```

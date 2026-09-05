# Contract: deploy.ps1

## Interface pública

```powershell
.\deploy.ps1              # Fluxo completo: sync → build (Cloud Build) → deploy
.\deploy.ps1 -SkipSync   # Build + deploy sem sincronizar dados no GCS
.\deploy.ps1 -SyncOnly   # Apenas sincroniza dados no GCS; sem build nem deploy
```

## Pré-requisitos (máquina local)

| Requisito | Verificação |
|---|---|
| `gcloud` CLI instalado | `Test-Path $GCLOUD` |
| Autenticado no GCP | `gcloud auth print-access-token` retorna token |
| Cloud Build API habilitada | falha na etapa de build com erro descritivo |
| **Docker NÃO é necessário** | — |

## Etapas e saídas esperadas

| Etapa | Comando | Saída esperada |
|---|---|---|
| Sync dados | `python sync_to_gcs.py` | `[OK] Dados sincronizados` |
| Build remoto | `gcloud builds submit --tag $IMAGE .` | Build ID + `SUCCESS` |
| Deploy | `gcloud run deploy ...` | URL do serviço |

## Comportamento de erro

- Falha na autenticação (`gcloud auth`) → mensagem clara + exit 1
- Falha no Cloud Build → log de erro do gcloud + exit 1
- Falha no sync → aviso (não bloqueia deploy; continua com dados existentes no bucket)

## Variáveis configuráveis (topo do script)

| Variável | Valor padrão |
|---|---|
| `$PROJECT_ID` | `opf-dash` |
| `$REGION` | `us-central1` |
| `$REPO` | `opf-repo` |
| `$SERVICE_NAME` | `opf-dashboard` |
| `$GCS_BUCKET` | `opf-data-bucket` |
| `$MEMORY` | `4Gi` |

## Contract: entrypoint.py

Invocado pelo container via `entrypoint.sh → exec python /app/entrypoint.py`.

| Comportamento | Detalhe |
|---|---|
| Inicia uvicorn imediatamente | `os.execvp("uvicorn", ...)` — não espera download |
| Download do DB em background | `threading.Thread(target=_download_db, daemon=True)` |
| Porta | Lida de `$PORT` (padrão: `8000`) |
| Sem GCS_BUCKET | Aviso impresso; continua com DB local se existir |
| Falha no download | Aviso impresso; uvicorn já está rodando |

# Quickstart: Deploy revisado (sem Docker)

## Pré-requisito único: gcloud CLI

```powershell
# Verificar autenticação
gcloud auth print-access-token

# Se não autenticado:
gcloud auth login
gcloud config set project opf-dash
```

## Deploy completo

```powershell
cd dashboard
.\deploy.ps1
```

O que acontece:
1. Sincroniza `consents.db` para `gs://opf-data-bucket/data/`
2. Envia código-fonte para o Google Cloud Build (sem Docker local)
3. Cloud Build constrói a imagem e faz push para o Artifact Registry
4. Cloud Run cria nova revisão com 4 GiB de memória

## Variantes

```powershell
.\deploy.ps1 -SkipSync   # só rebuild + deploy (sem atualizar dados)
.\deploy.ps1 -SyncOnly   # só sobe dados para o GCS
```

## Habilitar Cloud Build API (uma vez)

```powershell
gcloud services enable cloudbuild.googleapis.com --project opf-dash
```

## Teste local (sem Docker, sem deploy)

```powershell
cd dashboard
# ativa o venv
.\.venv\Scripts\Activate.ps1
uvicorn server:app --reload --port 8000
```

O DB é lido automaticamente de `../data-loader/data/consents.db`.

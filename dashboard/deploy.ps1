# deploy.ps1 - Build e deploy do Dashboard no Google Cloud Run via Cloud Build
# =================================================================
# Uso: .\deploy.ps1
# Flags opcionais:
#   -SkipSync   Nao sincroniza dados para o GCS (so build + deploy)
#   -SyncOnly   So sobe dados para o GCS, sem build nem deploy
#
# Pre-requisito: gcloud CLI instalado e autenticado (nao requer Docker)
# =================================================================

param(
    [switch]$SkipSync,
    [switch]$SyncOnly
)

# -- Configuracao -----------------------------------------------------------
$PROJECT_ID   = "opf-dash"
$REGION       = "us-central1"
$REPO         = "opf-repo"
$SERVICE_NAME = "opf-dashboard"
$GCS_BUCKET   = "opf-data-bucket"
$IMAGE        = "us-central1-docker.pkg.dev/$PROJECT_ID/$REPO/${SERVICE_NAME}:latest"
$GCLOUD       = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

# -- Helpers de output ------------------------------------------------------
function Write-Step { param($msg) Write-Host "" ; Write-Host ">>> $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Fail { param($msg) Write-Host "  [ERRO] $msg" -ForegroundColor Red; exit 1 }
function Write-Warn { param($msg) Write-Host "  [AVISO] $msg" -ForegroundColor Yellow }
function Write-Info { param($msg) Write-Host "  $msg" -ForegroundColor Gray }

# -- Inicio -----------------------------------------------------------------
$startTime = Get-Date
Write-Host ""
Write-Host "========================================================" -ForegroundColor Blue
Write-Host "   OPF Dashboard - Deploy para Google Cloud Run         " -ForegroundColor Blue
Write-Host "========================================================" -ForegroundColor Blue
Write-Host ""
Write-Info "Projeto  : $PROJECT_ID"
Write-Info "Regiao   : $REGION"
Write-Info "Servico  : $SERVICE_NAME"
Write-Info "Bucket   : $GCS_BUCKET"
Write-Info "Imagem   : $IMAGE"

# -- Verificar pre-requisitos -----------------------------------------------
Write-Step "Verificando pre-requisitos..."

if (-not (Test-Path $GCLOUD)) {
    Write-Fail "gcloud CLI nao encontrado em: $GCLOUD | Instale em: https://cloud.google.com/sdk/docs/install"
}
Write-OK "gcloud CLI encontrado"

& $GCLOUD auth print-access-token 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Nao autenticado no GCP. Execute: gcloud auth login"
}
Write-OK "Autenticado no GCP"

# -- Passo 1: Sync dos dados para o GCS ------------------------------------
if ($SkipSync -and -not $SyncOnly) {
    Write-Warn "Sync de dados ignorado (-SkipSync)"
} else {
    Write-Step "Sincronizando dados locais -> GCS (gs://$GCS_BUCKET/data/)..."
    $env:GCS_BUCKET = $GCS_BUCKET
    $env:GOOGLE_CLOUD_PROJECT = $PROJECT_ID
    python ..\data-loader\sync_to_gcs.py
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Falha no sync de dados - continuando com os dados existentes no bucket."
    } else {
        Write-OK "Dados sincronizados com sucesso"
    }
    if ($SyncOnly) {
        Write-Host ""
        Write-Host "[CONCLUIDO] Sync finalizado (-SyncOnly). Deploy nao executado." -ForegroundColor Green
        exit 0
    }
}

# -- Passo 2: Build da imagem via Cloud Build --------------------------------
Write-Step "Fazendo build da imagem via Cloud Build (sem Docker local)..."
Write-Info "Isso pode levar alguns minutos..."

# gcloud builds submit envia o codigo-fonte para o Cloud Build,
# constroi a imagem usando o Dockerfile e faz push para o Artifact Registry.
& $GCLOUD builds submit --tag $IMAGE . --project $PROJECT_ID `
    2>&1 | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) { Write-Fail "Falha no Cloud Build." }
Write-OK "Build concluido e imagem enviada para o Artifact Registry"

# -- Passo 3: Deploy no Cloud Run -------------------------------------------
Write-Step "Fazendo deploy no Cloud Run ($REGION)..."

# Nota: gcloud.cmd escreve progresso no stderr; redirecionar com 2>&1 | ForEach-Object
# evita o falso erro NativeCommandError do PowerShell
& $GCLOUD run deploy $SERVICE_NAME `
    --image $IMAGE `
    --platform managed `
    --region $REGION `
    --port 8000 `
    --memory 4Gi `
    --cpu 1 `
    --set-env-vars "GCS_BUCKET=$GCS_BUCKET,GOOGLE_CLOUD_PROJECT=$PROJECT_ID" `
    --allow-unauthenticated `
    --min-instances 0 `
    --max-instances 3 `
    --cpu-boost `
    --quiet 2>&1 | ForEach-Object { Write-Host $_ }

if ($LASTEXITCODE -ne 0) { Write-Fail "Falha no deploy do Cloud Run." }

# -- Obter URL do servico ---------------------------------------------------
$serviceUrl = (& $GCLOUD run services describe $SERVICE_NAME `
    --region $REGION `
    --format "value(status.url)" 2>&1 | Where-Object { $_ -notmatch '^WARNING' } | Select-Object -Last 1)

# -- Resumo -----------------------------------------------------------------
$elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds)
Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "   [OK] Deploy Concluido com Sucesso!                   " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  URL    : $serviceUrl" -ForegroundColor Cyan
Write-Host "  Tempo  : ${elapsed}s" -ForegroundColor Gray
Write-Host ""

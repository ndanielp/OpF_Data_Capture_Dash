#!/usr/bin/env bash
# deploy.sh - Build e deploy do Dashboard no Google Cloud Run via Cloud Build
# =================================================================
# Equivalente macOS/Linux do deploy.ps1.
#
# Uso: ./deploy.sh
# Flags opcionais:
#   --skip-sync   Nao sincroniza dados para o GCS (so build + deploy)
#   --sync-only   So sobe dados para o GCS, sem build nem deploy
#
# Pre-requisito: gcloud CLI instalado e autenticado (nao requer Docker)
#   brew install --cask google-cloud-sdk
#   gcloud auth login
#   gcloud auth application-default login   (usado pelo sync_to_gcs.py)
# =================================================================

set -euo pipefail

SKIP_SYNC=0
SYNC_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --skip-sync) SKIP_SYNC=1 ;;
        --sync-only) SYNC_ONLY=1 ;;
        -h|--help)
            sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Argumento desconhecido: $arg (use --skip-sync, --sync-only ou --help)" >&2
            exit 2
            ;;
    esac
done

# -- Configuracao -----------------------------------------------------------
PROJECT_ID="opf-dash"
REGION="us-central1"
REPO="opf-repo"
SERVICE_NAME="opf-dashboard"
# Bucket na mesma regiao do Cloud Run: o download da base a cada inicio de instancia
# nao paga transferencia entre regioes (o bucket antigo ficava em southamerica-east1).
GCS_BUCKET="opf-data-bucket-us"
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}:latest"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOADER_DIR="${HERE}/../data-loader"

# -- Helpers de output ------------------------------------------------------
if [ -t 1 ]; then
    C_BLUE=$'\033[34m'; C_CYAN=$'\033[36m'; C_GREEN=$'\033[32m'
    C_RED=$'\033[31m';  C_YELLOW=$'\033[33m'; C_GRAY=$'\033[90m'; C_OFF=$'\033[0m'
else
    C_BLUE=""; C_CYAN=""; C_GREEN=""; C_RED=""; C_YELLOW=""; C_GRAY=""; C_OFF=""
fi
step() { printf '\n%s>>> %s%s\n' "$C_CYAN" "$1" "$C_OFF"; }
ok()   { printf '  %s[OK] %s%s\n' "$C_GREEN" "$1" "$C_OFF"; }
fail() { printf '  %s[ERRO] %s%s\n' "$C_RED" "$1" "$C_OFF" >&2; exit 1; }
warn() { printf '  %s[AVISO] %s%s\n' "$C_YELLOW" "$1" "$C_OFF"; }
info() { printf '  %s%s%s\n' "$C_GRAY" "$1" "$C_OFF"; }

# -- Inicio -----------------------------------------------------------------
START_TIME=$(date +%s)
printf '\n%s========================================================%s\n' "$C_BLUE" "$C_OFF"
printf '%s   OPF Dashboard - Deploy para Google Cloud Run         %s\n' "$C_BLUE" "$C_OFF"
printf '%s========================================================%s\n\n' "$C_BLUE" "$C_OFF"
info "Projeto  : ${PROJECT_ID}"
info "Regiao   : ${REGION}"
info "Servico  : ${SERVICE_NAME}"
info "Bucket   : ${GCS_BUCKET}"
info "Imagem   : ${IMAGE}"

# -- Verificar pre-requisitos -----------------------------------------------
step "Verificando pre-requisitos..."

command -v gcloud >/dev/null 2>&1 \
    || fail "gcloud CLI nao encontrado | Instale com: brew install --cask google-cloud-sdk"
ok "gcloud CLI encontrado"

gcloud auth print-access-token >/dev/null 2>&1 \
    || fail "Nao autenticado no GCP. Execute: gcloud auth login"
ok "Autenticado no GCP"

# -- Passo 1: Sync dos dados para o GCS ------------------------------------
if [ "$SKIP_SYNC" -eq 1 ] && [ "$SYNC_ONLY" -eq 0 ]; then
    warn "Sync de dados ignorado (--skip-sync)"
else
    step "Sincronizando dados locais -> GCS (gs://${GCS_BUCKET}/data/)..."

    # Usa o venv do data-loader (tem google-cloud-storage); cai para python3 do sistema.
    if [ -x "${LOADER_DIR}/.venv/bin/python" ]; then
        PYTHON="${LOADER_DIR}/.venv/bin/python"
    else
        PYTHON="python3"
    fi

    if GCS_BUCKET="$GCS_BUCKET" GOOGLE_CLOUD_PROJECT="$PROJECT_ID" \
        "$PYTHON" "${LOADER_DIR}/sync_to_gcs.py"; then
        ok "Dados sincronizados com sucesso"
    else
        warn "Falha no sync de dados - continuando com os dados existentes no bucket."
    fi

    if [ "$SYNC_ONLY" -eq 1 ]; then
        printf '\n%s[CONCLUIDO] Sync finalizado (--sync-only). Deploy nao executado.%s\n' "$C_GREEN" "$C_OFF"
        exit 0
    fi
fi

# -- Passo 2: Build da imagem via Cloud Build --------------------------------
step "Fazendo build da imagem via Cloud Build (sem Docker local)..."
info "Isso pode levar alguns minutos..."

# gcloud builds submit envia o codigo-fonte para o Cloud Build,
# constroi a imagem usando o Dockerfile e faz push para o Artifact Registry.
(cd "$HERE" && gcloud builds submit --tag "$IMAGE" . --project "$PROJECT_ID") \
    || fail "Falha no Cloud Build."
ok "Build concluido e imagem enviada para o Artifact Registry"

# -- Passo 3: Deploy no Cloud Run -------------------------------------------
step "Fazendo deploy no Cloud Run (${REGION})..."

# Memoria: a base (~3,9 GiB) e baixada para o filesystem em memoria da instancia;
# 8 GiB deixa folga para o Python e o cache do Dashboard 2.0 (8 GiB exige 2 CPUs).
gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE" \
    --platform managed \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --port 8000 \
    --memory 8Gi \
    --cpu 2 \
    --set-env-vars "GCS_BUCKET=${GCS_BUCKET},GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
    --allow-unauthenticated \
    --min-instances 0 \
    --max-instances 3 \
    --cpu-boost \
    --quiet \
    || fail "Falha no deploy do Cloud Run."

# -- Obter URL do servico ---------------------------------------------------
SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --format 'value(status.url)' 2>/dev/null | tail -n 1)"

# -- Resumo -----------------------------------------------------------------
ELAPSED=$(( $(date +%s) - START_TIME ))
printf '\n%s========================================================%s\n' "$C_GREEN" "$C_OFF"
printf '%s   [OK] Deploy Concluido com Sucesso!                   %s\n' "$C_GREEN" "$C_OFF"
printf '%s========================================================%s\n\n' "$C_GREEN" "$C_OFF"
printf '  %sURL    : %s%s\n' "$C_CYAN" "$SERVICE_URL" "$C_OFF"
printf '  %sTempo  : %ss%s\n\n' "$C_GRAY" "$ELAPSED" "$C_OFF"

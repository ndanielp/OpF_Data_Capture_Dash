#!/bin/sh
# entrypoint.sh — Baixa consents.db do GCS antes de iniciar o servidor
# O dashboard usa apenas este arquivo; CSVs nao sao necessarios no Cloud Run.
set -e

GCS_BUCKET="${GCS_BUCKET:-}"
GCS_DB_BLOB="data/consents.db"
LOCAL_DB="/app/data/consents.db"

mkdir -p /app/data

if [ -z "$GCS_BUCKET" ]; then
    echo "[AVISO] GCS_BUCKET nao definido — usando dados locais (se existirem)."
else
    echo "[INFO] Baixando gs://$GCS_BUCKET/$GCS_DB_BLOB ..."
    python - <<EOF
import os, sys
try:
    from google.cloud import storage
    client = storage.Client()
    blob   = client.bucket("$GCS_BUCKET").blob("$GCS_DB_BLOB")
    blob.download_to_filename("$LOCAL_DB")
    size = os.path.getsize("$LOCAL_DB") / 1_048_576
    print(f"[OK] consents.db baixado ({size:.1f} MB)")
except Exception as e:
    print(f"[AVISO] Falha ao baixar do GCS: {e}")
    print("        Continuando com dados locais (se existirem)...")
EOF
fi

echo "[INFO] Iniciando servidor..."
exec "$@"

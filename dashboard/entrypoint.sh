#!/bin/sh
# entrypoint.sh — Baixa consents.db do GCS antes de iniciar o servidor
set -e

GCS_BUCKET="${GCS_BUCKET:-}"
GCS_DB_BLOB="data/consents.db"
LOCAL_DB="/app/data/consents.db"

mkdir -p /app/data

if [ -z "$GCS_BUCKET" ]; then
    echo "[AVISO] GCS_BUCKET nao definido — usando dados locais (se existirem)."
else
    echo "[INFO] Baixando gs://$GCS_BUCKET/$GCS_DB_BLOB ..."
    python - <<'PYEOF'
import os, sys
try:
    from google.cloud import storage
    bucket = os.environ["GCS_BUCKET"]
    blob_path = "data/consents.db"
    local_path = "/app/data/consents.db"
    client = storage.Client()
    blob = client.bucket(bucket).blob(blob_path)
    blob.download_to_filename(local_path)
    size = os.path.getsize(local_path) / 1_048_576
    print(f"[OK] consents.db baixado ({size:.1f} MB)")
except Exception as e:
    print(f"[AVISO] Falha ao baixar do GCS: {e}")
    print("        Continuando com dados locais (se existirem)...")
PYEOF
fi

PORT="${PORT:-8000}"
echo "[INFO] Iniciando servidor na porta $PORT ..."
exec uvicorn server:app --host 0.0.0.0 --port "$PORT"

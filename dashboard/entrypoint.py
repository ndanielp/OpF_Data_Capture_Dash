"""Entrypoint do container: baixa consents.db do GCS e inicia uvicorn."""
import os

def _download_db():
    bucket = os.environ.get("GCS_BUCKET", "")
    if not bucket:
        print("[AVISO] GCS_BUCKET nao definido — usando dados locais.", flush=True)
        return
    print(f"[INFO] Baixando gs://{bucket}/data/consents.db ...", flush=True)
    try:
        from google.cloud import storage
        os.makedirs("/app/data", exist_ok=True)
        client = storage.Client()
        blob = client.bucket(bucket).blob("data/consents.db")
        blob.download_to_filename("/app/data/consents.db")
        size = os.path.getsize("/app/data/consents.db") / 1_048_576
        print(f"[OK] consents.db baixado ({size:.1f} MB)", flush=True)
    except Exception as e:
        print(f"[AVISO] Falha ao baixar do GCS: {e}", flush=True)

os.makedirs("/app/data", exist_ok=True)
_download_db()

port = os.environ.get("PORT", "8000")
print(f"[INFO] Iniciando servidor na porta {port} ...", flush=True)
os.execvp("uvicorn", ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", port])

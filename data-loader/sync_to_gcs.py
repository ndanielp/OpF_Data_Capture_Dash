"""
sync_to_gcs.py — Script local para sincronizar data/ com o GCS
===============================================================
Execute após cada rodada do batch para atualizar os dados no Cloud:

    python sync_to_gcs.py

Requer:
    - google-cloud-storage instalado  (pip install google-cloud-storage)
    - Autenticação configurada:        gcloud auth application-default login
    - Variável de ambiente:           GCS_BUCKET=<nome-do-bucket>
      (ou edite DEFAULT_BUCKET abaixo)
"""

import os
import sys
import logging
from pathlib import Path

# -- Configuracao -----------------------------------------------------------
DEFAULT_BUCKET  = "opf-data-bucket"   # <- edite se quiser evitar variavel de ambiente
DEFAULT_PROJECT = "opf-dash"          # <- ID do projeto GCP
GCS_DB_BLOB     = "data/consents.db"  # unico arquivo que o dashboard usa

# ── Setup ─────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def main():
    bucket  = os.environ.get("GCS_BUCKET", DEFAULT_BUCKET)
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT)

    if not bucket:
        log.error("Defina a variavel GCS_BUCKET ou edite DEFAULT_BUCKET em sync_to_gcs.py")
        sys.exit(1)

    # Garante que o SDK Python encontra o projeto correto
    if project and not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        os.environ["GOOGLE_CLOUD_PROJECT"] = project

    local_db = _HERE / "data" / "consents.db"
    if not local_db.exists():
        log.error("Arquivo nao encontrado: %s", local_db)
        sys.exit(1)

    log.info("Iniciando sync: %s -> gs://%s/%s  (projeto: %s)",
             local_db, bucket, GCS_DB_BLOB, project)

    try:
        from google.cloud import storage
    except ImportError:
        log.error("Instale o pacote: pip install google-cloud-storage")
        sys.exit(1)

    try:
        client = storage.Client()
        blob   = client.bucket(bucket).blob(GCS_DB_BLOB)
        blob.upload_from_filename(str(local_db))
        size_mb = local_db.stat().st_size / 1_048_576
        log.info("[OK] consents.db enviado (%.1f MB)", size_mb)
    except Exception as e:
        log.error("[ERRO] Falha no sync: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
gcs_sync.py — Sincronização com Google Cloud Storage
=====================================================
Módulo compartilhado para upload (local → GCS) e download (GCS → local).
Usado por:
  - sync_to_gcs.py   : script local para subir dados após cada coleta
  - dashboard_server : para baixar dados ao inicializar no Cloud Run
"""

import os
import logging
from pathlib import Path

log = logging.getLogger(__name__)

GCS_BUCKET   = os.environ.get("GCS_BUCKET", "")       # ex: "opf-data-bucket"
GCS_PREFIX   = os.environ.get("GCS_PREFIX", "data/")  # pasta dentro do bucket
LOCAL_DATA   = Path(__file__).parent / "data"


def _client():
    """Retorna um cliente GCS autenticado."""
    from google.cloud import storage
    return storage.Client()


def upload_data_to_gcs(bucket_name: str = GCS_BUCKET, prefix: str = GCS_PREFIX):
    """
    Sobe todos os arquivos em data/ para o bucket GCS.
    Uso: após rodar o batch local, executar sync_to_gcs.py
    """
    if not bucket_name:
        raise ValueError("GCS_BUCKET não definido. Configure a variável de ambiente GCS_BUCKET.")

    client = _client()
    bucket = client.bucket(bucket_name)

    LOCAL_DATA.mkdir(parents=True, exist_ok=True)
    files = list(LOCAL_DATA.rglob("*"))
    files = [f for f in files if f.is_file()]

    if not files:
        log.warning("Nenhum arquivo encontrado em %s para subir.", LOCAL_DATA)
        return []

    uploaded = []
    for local_path in files:
        blob_name = prefix + local_path.relative_to(LOCAL_DATA).as_posix()
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(local_path))
        uploaded.append(blob_name)
        log.info("  ✅  %s → gs://%s/%s", local_path.name, bucket_name, blob_name)

    return uploaded


def download_data_from_gcs(bucket_name: str = GCS_BUCKET, prefix: str = GCS_PREFIX):
    """
    Baixa todos os arquivos de data/ do bucket GCS para o diretório local data/.
    Chamado pelo dashboard no Cloud Run ao inicializar.
    """
    if not bucket_name:
        log.warning("GCS_BUCKET não definido — usando dados locais (se existirem).")
        return []

    client = _client()
    bucket = client.bucket(bucket_name)

    LOCAL_DATA.mkdir(parents=True, exist_ok=True)
    blobs = list(client.list_blobs(bucket_name, prefix=prefix))

    if not blobs:
        log.warning("Nenhum arquivo encontrado em gs://%s/%s", bucket_name, prefix)
        return []

    downloaded = []
    for blob in blobs:
        # Remove o prefixo para obter o caminho relativo
        relative = blob.name[len(prefix):]
        if not relative:
            continue
        local_path = LOCAL_DATA / relative
        local_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(local_path))
        downloaded.append(str(local_path))
        log.info("  ⬇️  gs://%s/%s → %s", bucket_name, blob.name, local_path)

    return downloaded

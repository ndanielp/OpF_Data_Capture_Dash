"""
drive.py — Google Drive via Service Account
============================================
Funções para autenticar, buscar, baixar e fazer upload de arquivos no Drive.
Usa google-auth + google-api-python-client com Service Account (sem interação manual).
"""

import io
import logging
from pathlib import Path

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

_SCOPES = ["https://www.googleapis.com/auth/drive"]
_log = logging.getLogger(__name__)


# ── Auth ───────────────────────────────────────────────────────────────────────

def get_service(service_account_file: str | Path):
    """Retorna Resource autenticado via Service Account JSON."""
    creds = service_account.Credentials.from_service_account_file(
        str(service_account_file), scopes=_SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ── Busca ──────────────────────────────────────────────────────────────────────

def find_file(service, folder_id: str, name: str) -> str | None:
    """Retorna o file_id do arquivo com o nome dado na pasta, ou None se não existe."""
    q = (
        f"name='{name}' and '{folder_id}' in parents "
        f"and trashed=false"
    )
    result = service.files().list(q=q, fields="files(id,name)").execute()
    files = result.get("files", [])
    return files[0]["id"] if files else None


def find_folder(service, parent_id: str, name: str) -> str | None:
    """Retorna o folder_id da subpasta com o nome dado, ou None se não existe."""
    q = (
        f"name='{name}' and '{parent_id}' in parents "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and trashed=false"
    )
    result = service.files().list(q=q, fields="files(id,name)").execute()
    files = result.get("files", [])
    return files[0]["id"] if files else None


def ensure_subfolder(service, parent_id: str, name: str) -> str:
    """Retorna o folder_id da subpasta (cria se não existir)."""
    folder_id = find_folder(service, parent_id, name)
    if folder_id:
        return folder_id
    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = service.files().create(body=meta, fields="id").execute()
    _log.debug(f"Pasta '{name}' criada no Drive (id={created['id']})")
    return created["id"]


# ── Download ───────────────────────────────────────────────────────────────────

def download_as_bytes(service, file_id: str) -> bytes:
    """Baixa o conteúdo de um arquivo como bytes."""
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def download_csv(service, folder_id: str, name: str) -> pd.DataFrame | None:
    """Baixa um CSV do Drive e retorna como DataFrame. Retorna None se não existe."""
    file_id = find_file(service, folder_id, name)
    if not file_id:
        return None
    data = download_as_bytes(service, file_id)
    return pd.read_csv(io.BytesIO(data))


# ── Upload ─────────────────────────────────────────────────────────────────────

def upload_bytes(
    service, folder_id: str, name: str, data: bytes, mime: str = "text/plain"
) -> str:
    """Faz upload de bytes para o Drive. Atualiza o arquivo se já existir."""
    file_id = find_file(service, folder_id, name)
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=False)

    if file_id:
        service.files().update(fileId=file_id, media_body=media).execute()
        _log.debug(f"Arquivo '{name}' atualizado no Drive")
        return file_id
    else:
        meta = {"name": name, "parents": [folder_id]}
        created = service.files().create(
            body=meta, media_body=media, fields="id"
        ).execute()
        _log.debug(f"Arquivo '{name}' criado no Drive (id={created['id']})")
        return created["id"]


def upload_csv(service, folder_id: str, name: str, df: pd.DataFrame) -> str:
    """Serializa DataFrame como CSV e faz upload para o Drive."""
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8")
    return upload_bytes(service, folder_id, name, buf.getvalue(), mime="text/csv")


def upload_local_file(service, folder_id: str, local_path: str | Path) -> str:
    """Lê um arquivo local e faz upload para a pasta indicada no Drive."""
    local_path = Path(local_path)
    data = local_path.read_bytes()
    mime = "text/plain"
    return upload_bytes(service, folder_id, local_path.name, data, mime=mime)


# ── Inspeção ───────────────────────────────────────────────────────────────────

def list_files(service, folder_id: str) -> list[dict]:
    """Lista arquivos (não pastas) na pasta raiz do Drive."""
    q = (
        f"'{folder_id}' in parents "
        f"and mimeType!='application/vnd.google-apps.folder' "
        f"and trashed=false"
    )
    result = service.files().list(
        q=q, fields="files(id,name,size,modifiedTime)"
    ).execute()
    return result.get("files", [])


def get_csv_stats(service, folder_id: str, name: str) -> dict:
    """
    Retorna estatísticas de um CSV no Drive:
    total de linhas, datas cobertas (se coluna 'date' existir).
    Retorna dict vazio se arquivo não existir.
    """
    df = download_csv(service, folder_id, name)
    if df is None:
        return {"exists": False, "rows": 0}
    stats: dict = {"exists": True, "rows": len(df)}
    if "date" in df.columns:
        stats["date_min"] = df["date"].min()
        stats["date_max"] = df["date"].max()
    if "receptor" in df.columns:
        stats["receptors"] = int(df["receptor"].nunique())
    return stats

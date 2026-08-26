import asyncio
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from supabase import Client, create_client

from app.core.config import settings

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}


@lru_cache
def get_supabase_client() -> Client:
    """Cliente singleton de Supabase (URL + KEY del .env)."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def _upload_sync(file_bytes: bytes, path: str, content_type: str) -> str:
    """Sube bytes al bucket y retorna la URL pública."""
    client = get_supabase_client()
    bucket = settings.SUPABASE_STORAGE_BUCKET

    try:
        client.storage.from_(bucket).upload(
            path,
            file_bytes,
            file_options={
                "content-type": content_type or "application/octet-stream",
                "upsert": "false",
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al subir imagen a Supabase Storage: {exc}",
        ) from exc

    public_url = client.storage.from_(bucket).get_public_url(path)
    # Algunas versiones retornan dict; normalizar a str
    if isinstance(public_url, dict):
        public_url = public_url.get("publicUrl") or public_url.get("public_url") or ""
    return str(public_url)


async def upload_image_to_supabase(file: UploadFile, folder: str) -> str:
    """
    Sube una imagen al bucket público 'flayers' (o el configurado en .env).

    - Genera un nombre único con UUID.
    - Preserva la extensión original.
    - Retorna la URL pública de la imagen.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se recibió un archivo de imagen válido",
        )

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extensión no permitida: {extension}. Usa: {sorted(ALLOWED_IMAGE_EXTENSIONS)}",
        )

    unique_name = f"{uuid.uuid4().hex}{extension}"
    # Limpiar carpeta y armar path tipo: promociones/abc123.png
    folder_clean = folder.strip("/").strip() or "general"
    storage_path = f"{folder_clean}/{unique_name}"

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo de imagen está vacío",
        )

    content_type = file.content_type or "application/octet-stream"

    # El cliente de supabase-py es síncrono; se ejecuta en un thread.
    return await asyncio.to_thread(_upload_sync, file_bytes, storage_path, content_type)

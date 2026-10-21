"""
Caché de ETag/Last-Modified/content_hash en memoria de proceso, por rango de fechas.
Permite que verificar_cambios() y el early-return funcionen entre requests y el scheduler.
"""

from __future__ import annotations

from typing import Optional

# key: "DD/MM/YYYY|DD/MM/YYYY" -> {etag, last_modified, content_hash}
_ETAG_CACHE: dict[str, dict[str, Optional[str]]] = {}


def rango_key(fecha_inicio: str, fecha_fin: str) -> str:
    return f"{fecha_inicio.strip()}|{fecha_fin.strip()}"


def obtener_estado(fecha_inicio: str, fecha_fin: str) -> dict[str, Optional[str]]:
    return dict(_ETAG_CACHE.get(rango_key(fecha_inicio, fecha_fin), {}))


def guardar_estado(
    fecha_inicio: str,
    fecha_fin: str,
    etag: Optional[str],
    last_modified: Optional[str],
    content_hash: Optional[str] = None,
) -> None:
    previo = _ETAG_CACHE.get(rango_key(fecha_inicio, fecha_fin), {})
    _ETAG_CACHE[rango_key(fecha_inicio, fecha_fin)] = {
        "etag": etag,
        "last_modified": last_modified,
        "content_hash": content_hash
        if content_hash is not None
        else previo.get("content_hash"),
    }

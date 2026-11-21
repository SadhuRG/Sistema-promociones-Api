"""
Purga automática de promociones Inactivas con más de 30 días.

Nunca borra una promoción Activa. El reloj empieza en inactivado_at
(cuando pasa de Activo a Inactivo), no en updated_at ni fecha_fin.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)

DIAS_INACTIVA_PARA_PURGAR = 30
CARPETA_IMAGENES_PROMOCION = "promociones/"
ESTADO_ACTIVO = "Activo"
ESTADO_INACTIVO = "Inactivo"


def _ahora_utc(now: Optional[datetime] = None) -> datetime:
    momento = now or datetime.now(timezone.utc)
    if momento.tzinfo is None:
        return momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc)


def promo_lista_para_purgar(
    estado: Optional[str],
    inactivado_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> bool:
    """True solo si está Inactivo y lleva al menos 30 días así."""
    if str(estado or "").strip() != ESTADO_INACTIVO:
        return False
    if inactivado_at is None:
        return False
    momento = _ahora_utc(now)
    marca = _ahora_utc(inactivado_at)
    return marca <= momento - timedelta(days=DIAS_INACTIVA_PARA_PURGAR)


def aplicar_cambio_estado(
    promocion: Any,
    nuevo_estado: Optional[str],
    now: Optional[datetime] = None,
) -> None:
    """Marca inactivado_at al pasar a Inactivo; lo limpia al reactivar."""
    if nuevo_estado is None:
        return
    nuevo = str(nuevo_estado).strip()
    if nuevo not in (ESTADO_ACTIVO, ESTADO_INACTIVO):
        promocion.estado = nuevo
        return

    actual = str(promocion.estado or "").strip()
    momento = _ahora_utc(now)
    if nuevo == ESTADO_INACTIVO:
        if actual != ESTADO_INACTIVO or promocion.inactivado_at is None:
            promocion.inactivado_at = momento
        promocion.estado = ESTADO_INACTIVO
        return

    promocion.estado = ESTADO_ACTIVO
    promocion.inactivado_at = None


def extract_promocion_storage_path(
    url: Optional[str],
    bucket: str = "flayers",
) -> str:
    """
    Extrae promociones/{archivo} de la URL pública de flayers.
    Vacío si no hay URL, si no es de esa carpeta o si apunta a informes/.
    """
    text = unquote(str(url or "").strip())
    if not text:
        return ""
    text = text.split("?", 1)[0].split("#", 1)[0]
    bucket_name = (bucket or "flayers").strip("/")

    parsed = urlparse(text)
    candidate = parsed.path if parsed.scheme else text
    candidate = candidate.lstrip("/")

    marker = f"{bucket_name}/"
    if f"/{marker}" in f"/{candidate}":
        candidate = candidate.split(marker, 1)[1]
    elif candidate.startswith(marker):
        candidate = candidate[len(marker) :]

    path = candidate.lstrip("/")
    if not path.startswith(CARPETA_IMAGENES_PROMOCION):
        return ""
    if ".." in path.split("/"):
        return ""
    return path


def _imagen_compartida_por_otra(db: Any, promocion: Any) -> bool:
    from app.models.all_models import Promocion

    url = str(promocion.promocion_img or "").strip()
    if not url:
        return False
    otra = (
        db.query(Promocion.id_promocion)
        .filter(
            Promocion.promocion_img == url,
            Promocion.id_promocion != promocion.id_promocion,
        )
        .first()
    )
    return otra is not None


def _bucket_flayers() -> str:
    from app.core.config import settings

    return (settings.SUPABASE_STORAGE_BUCKET or "flayers").strip()


def borrar_imagen_de_promocion(db: Any, promocion: Any) -> bool:
    """Borra la imagen del bucket flayers/promociones. No toca informes/."""
    from app.core.storage import remove_storage_object

    path = extract_promocion_storage_path(promocion.promocion_img, _bucket_flayers())
    if not path:
        return False
    if _imagen_compartida_por_otra(db, promocion):
        logger.info(
            "Imagen de promoción %s compartida; no se borra del bucket",
            promocion.id_promocion,
        )
        return False
    try:
        remove_storage_object(_bucket_flayers(), path)
        return True
    except Exception:
        logger.exception(
            "No se pudo borrar la imagen %s de la promoción %s",
            path,
            promocion.id_promocion,
        )
        return False


def purgar_promociones_inactivas(
    db: Any,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    Borra promociones Inactivas con inactivado_at de al menos 30 días
    y, si corresponde, su imagen en flayers/promociones.
    """
    from app.core.storage import remove_storage_object
    from app.models.all_models import Promocion

    momento = _ahora_utc(now)
    limite = momento - timedelta(days=DIAS_INACTIVA_PARA_PURGAR)
    candidatas = (
        db.query(Promocion)
        .filter(
            Promocion.estado == ESTADO_INACTIVO,
            Promocion.inactivado_at.isnot(None),
            Promocion.inactivado_at <= limite,
        )
        .all()
    )

    eliminadas: list[int] = []
    imagenes_borradas: list[str] = []
    omitidas: list[int] = []

    for promocion in candidatas:
        if not promo_lista_para_purgar(
            promocion.estado, promocion.inactivado_at, momento
        ):
            omitidas.append(int(promocion.id_promocion))
            continue

        promo_id = int(promocion.id_promocion)
        img_path = extract_promocion_storage_path(
            promocion.promocion_img, _bucket_flayers()
        )
        borrar_img = bool(img_path) and not _imagen_compartida_por_otra(db, promocion)

        db.delete(promocion)
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("No se pudo borrar la promoción inactiva %s", promo_id)
            omitidas.append(promo_id)
            continue

        eliminadas.append(promo_id)
        if borrar_img:
            try:
                remove_storage_object(_bucket_flayers(), img_path)
                imagenes_borradas.append(img_path)
            except Exception:
                logger.exception(
                    "Promoción %s borrada, pero falló la imagen %s",
                    promo_id,
                    img_path,
                )

    logger.info(
        "Purga promociones inactivas: candidatas=%s eliminadas=%s imagenes=%s omitidas=%s",
        len(candidatas),
        len(eliminadas),
        len(imagenes_borradas),
        len(omitidas),
    )
    return {
        "candidatas": len(candidatas),
        "eliminadas": eliminadas,
        "imagenes_borradas": imagenes_borradas,
        "omitidas": omitidas,
    }

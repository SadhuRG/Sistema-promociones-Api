"""
Orquestación del sync de horarios (endpoint admin + scheduler).
Respeta ETag/content_hash: sin cambios reales => no mirror en BD.
Un solo sync a la vez (candado): admin y scheduler no se pisan.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import threading
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.db_horarios_sync import DBHorariosSyncService
from app.services.etag_cache import guardar_estado, obtener_estado
from app.services.procesador_horarios import ProcesadorHorariosService
from app.services.sync_imagina import ImaginaSyncService

# Candado de proceso: evita sync paralelo (botón admin + job cada 2 min).
_SYNC_LOCK = threading.Lock()
_SYNC_EN_CURSO = False


def sync_en_curso() -> bool:
    return _SYNC_EN_CURSO


def rango_mes_actual() -> tuple[str, str]:
    """Primer y último día del mes actual en DD/MM/YYYY."""
    hoy = date.today()
    ultimo = calendar.monthrange(hoy.year, hoy.month)[1]
    inicio = date(hoy.year, hoy.month, 1)
    fin = date(hoy.year, hoy.month, ultimo)
    return inicio.strftime("%d/%m/%Y"), fin.strftime("%d/%m/%Y")


def dd_mm_yyyy_a_sql(fecha: str) -> str:
    return datetime.strptime(fecha.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")


def fingerprint_registros(registros: list[dict[str, Any]]) -> str:
    """
    Huella estable del Excel limpio.
    Imagina regenera el archivo (nuevo ETag/orden de filas) aunque los horarios no cambien.
    """
    serializadas = sorted(
        json.dumps(fila, sort_keys=True, ensure_ascii=False, default=str)
        for fila in registros
    )
    payload = "\n".join(serializadas)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ejecutar_sync_interno(
    db: Session,
    fecha_inicio: str,
    fecha_fin: str,
) -> dict[str, Any]:
    """
    Flujo completo (ya dentro del candado):
      login -> preparar_reporte -> verificar_cambios (ETag)
      si no hay cambios -> up_to_date (sin descarga / sin BD)
      si hay cambios de ETag -> descargar; si content_hash igual -> up_to_date (sin BD)
      si content_hash distinto -> procesar -> mirror BD -> success
    """
    url = settings.IMAGINA_EXCEL_URL
    if not url:
        raise RuntimeError("IMAGINA_EXCEL_URL no está configurada")

    fecha_inicio_sql = dd_mm_yyyy_a_sql(fecha_inicio)
    fecha_fin_sql = dd_mm_yyyy_a_sql(fecha_fin)
    if fecha_fin_sql < fecha_inicio_sql:
        raise ValueError("fecha_fin debe ser posterior o igual a fecha_inicio")

    imagina = ImaginaSyncService()
    cached = obtener_estado(fecha_inicio, fecha_fin)
    imagina.cargar_estado_etag(cached.get("etag"), cached.get("last_modified"))

    if not imagina.login():
        raise RuntimeError("No se pudo iniciar sesión en Imagina")

    if not imagina.preparar_reporte(fecha_inicio, fecha_fin):
        raise RuntimeError("No se pudo preparar el reporte de horarios en Imagina")

    meta = imagina.verificar_cambios(url)
    if meta.get("error"):
        pass
    elif meta.get("hay_cambios") is False:
        return {
            "status": "up_to_date",
            "message": "No hay cambios en Imagina",
            "registros_insertados": 0,
        }

    datos_excel = imagina.descargar_excel(url)
    if datos_excel is None:
        raise RuntimeError("Falló la descarga/limpieza del Excel de Imagina")

    content_hash = fingerprint_registros(datos_excel)
    etag_guardar = imagina.last_etag or meta.get("etag")
    lm_guardar = imagina.last_modified or meta.get("last_modified")

    if cached.get("content_hash") and cached["content_hash"] == content_hash:
        guardar_estado(
            fecha_inicio,
            fecha_fin,
            etag_guardar,
            lm_guardar,
            content_hash,
        )
        return {
            "status": "up_to_date",
            "message": "No hay cambios en Imagina",
            "registros_insertados": 0,
        }

    datos_procesados = ProcesadorHorariosService().procesar(datos_excel, db)
    insertados = DBHorariosSyncService().sincronizar_en_bd(
        datos_procesados=datos_procesados,
        db_session=db,
        fecha_inicio_sql=fecha_inicio_sql,
        fecha_fin_sql=fecha_fin_sql,
    )

    guardar_estado(
        fecha_inicio,
        fecha_fin,
        etag_guardar,
        lm_guardar,
        content_hash,
    )

    return {
        "status": "success",
        "message": "Horarios actualizados correctamente",
        "registros_insertados": insertados,
    }


def ejecutar_sync_horarios(
    db: Session,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
) -> dict[str, Any]:
    """
    Entrada única para admin (/sync-auto) y scheduler.
    Si ya hay un sync en curso -> status=busy (no relanza el trabajo).
    """
    global _SYNC_EN_CURSO

    if not fecha_inicio or not fecha_fin:
        fecha_inicio, fecha_fin = rango_mes_actual()

    adquirido = _SYNC_LOCK.acquire(blocking=False)
    if not adquirido:
        return {
            "status": "busy",
            "message": "Ya se está actualizando los horarios",
            "registros_insertados": 0,
        }

    _SYNC_EN_CURSO = True
    try:
        return _ejecutar_sync_interno(db, fecha_inicio, fecha_fin)
    finally:
        _SYNC_EN_CURSO = False
        _SYNC_LOCK.release()

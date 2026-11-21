"""
Scheduler en background: sync de horarios cada 1 minuto
(mes calendario actual + mes siguiente).
Respeta ETag vía orquestador_horarios (sin trabajo si no hay cambios).
También purga promociones Inactivas con más de 30 días (nunca Activas).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.database import SessionLocal
from app.services.orquestador_horarios import (
    ejecutar_sync_horarios,
    rango_mes_actual_y_siguiente,
)
from app.services.purgar_promociones import purgar_promociones_inactivas

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def job_sync_horarios_mes_actual() -> None:
    """Misma orquestación que /horarios/sync-auto, mes actual + siguiente."""
    fecha_inicio, fecha_fin = rango_mes_actual_y_siguiente()
    db = SessionLocal()
    try:
        resultado = ejecutar_sync_horarios(
            db=db,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        status = resultado.get("status")
        if status == "busy":
            # El admin (u otro job) ya está sincronizando; no se duplica.
            logger.info(
                "Scheduler sync-horarios omitido [%s -> %s]: %s",
                fecha_inicio,
                fecha_fin,
                resultado.get("message"),
            )
        else:
            logger.info(
                "Scheduler sync-horarios [%s -> %s]: %s (%s)",
                fecha_inicio,
                fecha_fin,
                status,
                resultado.get("message"),
            )
    except Exception:
        logger.exception(
            "Scheduler sync-horarios falló [%s -> %s]",
            fecha_inicio,
            fecha_fin,
        )
    finally:
        db.close()


def job_purgar_promociones_inactivas() -> None:
    """Borra Inactivas con inactivado_at de al menos 30 días + su imagen."""
    db = SessionLocal()
    try:
        resultado = purgar_promociones_inactivas(db)
        logger.info(
            "Scheduler purga-promociones: candidatas=%s eliminadas=%s imagenes=%s",
            resultado.get("candidatas"),
            len(resultado.get("eliminadas") or []),
            len(resultado.get("imagenes_borradas") or []),
        )
    except Exception:
        logger.exception("Scheduler purga-promociones falló")
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        job_sync_horarios_mes_actual,
        trigger="interval",
        minutes=1,
        id="sync_horarios_mes_actual",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        job_purgar_promociones_inactivas,
        trigger="interval",
        hours=6,
        id="purgar_promociones_inactivas",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    scheduler.start()
    logger.info(
        "APScheduler iniciado: sync_horarios cada 1 minuto; "
        "purga promociones inactivas cada 6 horas"
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler detenido")

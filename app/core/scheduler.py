"""
Scheduler en background: sync de horarios cada 2 minutos (mes actual).
Respeta ETag vía orquestador_horarios (sin trabajo si no hay cambios).
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.database import SessionLocal
from app.services.orquestador_horarios import ejecutar_sync_horarios, rango_mes_actual

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def job_sync_horarios_mes_actual() -> None:
    """Misma orquestación que /horarios/sync-auto, con el mes calendario actual."""
    fecha_inicio, fecha_fin = rango_mes_actual()
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


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        job_sync_horarios_mes_actual,
        trigger="interval",
        minutes=2,
        id="sync_horarios_mes_actual",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("APScheduler iniciado: sync_horarios cada 2 minutos")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler detenido")

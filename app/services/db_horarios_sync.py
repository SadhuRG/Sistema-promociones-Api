"""
Sincronización por espejo de la tabla horario:
DELETE por rango de fechas + bulk insert.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.all_models import Horario


class DBHorariosSyncService:
    """Espejo temporal: borra el rango y reinserta el lote procesado."""

    def sincronizar_en_bd(
        self,
        datos_procesados: list[dict[str, Any]],
        db_session: Session,
        fecha_inicio_sql: str,
        fecha_fin_sql: str,
    ) -> int:
        """
        DELETE horario WHERE fecha BETWEEN inicio AND fin,
        luego bulk insert de datos_procesados.
        Retorna cantidad insertada.
        """
        inicio = self._parse_fecha(fecha_inicio_sql)
        fin = self._parse_fecha(fecha_fin_sql)
        if inicio is None or fin is None:
            raise ValueError(
                f"Fechas SQL inválidas: {fecha_inicio_sql!r} / {fecha_fin_sql!r}"
            )
        if fin < inicio:
            raise ValueError("fecha_fin_sql debe ser >= fecha_inicio_sql")

        objetos: list[Horario] = []
        for row in datos_procesados:
            horario = self._fila_a_horario(row)
            if horario is not None:
                objetos.append(horario)

        try:
            (
                db_session.query(Horario)
                .filter(Horario.fecha >= inicio, Horario.fecha <= fin)
                .delete(synchronize_session=False)
            )

            if objetos:
                db_session.bulk_save_objects(objetos)

            db_session.commit()
            return len(objetos)
        except Exception:
            db_session.rollback()
            raise

    @staticmethod
    def _parse_fecha(valor: str) -> Optional[date]:
        try:
            return datetime.strptime(valor, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_hora(valor: Any) -> Optional[time]:
        if valor is None:
            return None
        if isinstance(valor, time):
            return valor
        try:
            return datetime.strptime(str(valor), "%H:%M:%S").time()
        except (TypeError, ValueError):
            return None

    def _fila_a_horario(self, row: dict[str, Any]) -> Optional[Horario]:
        dia = row.get("dia_semana")
        hora_inicio = self._parse_hora(row.get("hora_inicio"))
        hora_fin = self._parse_hora(row.get("hora_fin"))
        if not dia or hora_inicio is None or hora_fin is None:
            return None
        if hora_fin <= hora_inicio:
            return None

        fecha_val = row.get("fecha")
        fecha: Optional[date]
        if isinstance(fecha_val, date) and not isinstance(fecha_val, datetime):
            fecha = fecha_val
        elif isinstance(fecha_val, str):
            fecha = self._parse_fecha(fecha_val)
        else:
            fecha = None

        return Horario(
            id_especialidad=row.get("id_especialidad"),
            id_doctor=row.get("id_doctor"),
            fecha=fecha,
            dia_semana=str(dia).strip(),
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            estado="Activo",
        )

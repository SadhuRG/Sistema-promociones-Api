"""
Cruza horarios del Excel (ya limpios) con especialidades/doctores de Supabase
y devuelve registros listos para insertar en la tabla horario.
"""

from __future__ import annotations

import re
from typing import Any, Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models.all_models import Doctor, Especialidad
from app.services.limpieza_horarios import estandarizar_texto

_MEDICO_VACIO = re.compile(r"^[\s\-–—_]*$")
_TITULOS_MEDICO = {
    "DR",
    "DRA",
    "DR.",
    "DRA.",
    "DOCTOR",
    "DOCTORA",
    "MD",
}
_PARTICULAS_NOMBRE = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "E", "DA", "DAS", "DO", "DOS"}
NOMBRE_ANONIMO = "ANONIMO"


class ProcesadorHorariosService:
    """Excel limpio + BD -> filas listas para tabla horario."""

    def procesar(
        self,
        datos_excel: list[dict[str, Any]],
        db_session: Session,
    ) -> list[dict[str, Any]]:
        if not datos_excel:
            return []

        df_excel = pd.DataFrame(datos_excel)

        self._asignar_ids_especialidad(df_excel, db_session)
        self._asignar_ids_doctor(df_excel, db_session)

        # ------------------------------------------------------------------
        # Formateo final -> columnas del modelo horario
        # ------------------------------------------------------------------
        col_dia = "Días de la semana" if "Días de la semana" in df_excel.columns else None
        if col_dia is None:
            # Fallback por encoding raro en algunos entornos
            for c in df_excel.columns:
                if "semana" in str(c).lower() or "dias" in str(c).lower().replace("í", "i"):
                    col_dia = c
                    break
        if col_dia is None:
            raise ValueError("No se encontró la columna 'Días de la semana' en los datos.")

        out = pd.DataFrame(
            {
                "id_especialidad": df_excel.get("id_especialidad"),
                "id_doctor": df_excel.get("id_doctor"),
                "dia_semana": df_excel[col_dia],
                "fecha": self._formatear_fecha(df_excel["Fecha"]),
                "hora_inicio": self._formatear_hora(df_excel["Hora Inicio"]),
                "hora_fin": self._formatear_hora(df_excel["Hora Fin"]),
            }
        )

        # NaN -> None sin upcast a float; IDs como int | None
        registros = out.astype(object).where(pd.notnull(out), None).to_dict(orient="records")
        for row in registros:
            for col in ("id_especialidad", "id_doctor"):
                if row.get(col) is not None:
                    row[col] = int(row[col])
        return registros

    def _asignar_ids_especialidad(
        self,
        df_excel: pd.DataFrame,
        db_session: Session,
    ) -> None:
        filas = db_session.query(Especialidad).all()
        mapa: dict[str, int] = {}
        for fila in filas:
            if self._es_anonimo(fila.nombre):
                continue
            clave = estandarizar_texto(fila.nombre)
            if clave and clave not in mapa:
                mapa[clave] = int(fila.id_especialidad)

        if "Especialidad" in df_excel.columns:
            df_excel["id_especialidad"] = df_excel["Especialidad"].map(
                lambda valor: mapa.get(estandarizar_texto(valor))
            )
        else:
            df_excel["id_especialidad"] = None

        sin_match = df_excel["id_especialidad"].isna()
        if not sin_match.any():
            return
        anonimo_id = self._obtener_o_crear_anonimo(
            db_session, Especialidad, "id_especialidad"
        )
        df_excel.loc[sin_match, "id_especialidad"] = anonimo_id

    def _asignar_ids_doctor(
        self,
        df_excel: pd.DataFrame,
        db_session: Session,
    ) -> None:
        filas = db_session.query(Doctor).all()
        mapa: dict[str, int] = {}
        for fila in filas:
            if self._es_anonimo(fila.nombre):
                continue
            for clave in self._claves_nombre_medico(fila.nombre):
                if clave not in mapa:
                    mapa[clave] = int(fila.id_doctor)

        if "Medico" in df_excel.columns:
            df_excel["id_doctor"] = df_excel["Medico"].map(
                lambda valor: self._resolver_id_medico(valor, mapa)
            )
        else:
            df_excel["id_doctor"] = None

        medico = (
            df_excel["Medico"]
            if "Medico" in df_excel.columns
            else pd.Series(pd.NA, index=df_excel.index)
        )
        sin_match = df_excel["id_doctor"].isna() & medico.map(
            self._tiene_nombre_medico
        ).fillna(False).astype(bool)
        if not bool(sin_match.any()):
            return
        anonimo_id = self._obtener_o_crear_anonimo(db_session, Doctor, "id_doctor")
        df_excel.loc[sin_match, "id_doctor"] = anonimo_id

    @staticmethod
    def _obtener_o_crear_anonimo(
        db_session: Session,
        modelo,
        id_attr: str,
    ) -> int:
        filas = db_session.query(modelo).all()
        for fila in filas:
            if estandarizar_texto(fila.nombre) == NOMBRE_ANONIMO:
                return int(getattr(fila, id_attr))
        nuevo = modelo(nombre=NOMBRE_ANONIMO, estado="Activo")
        db_session.add(nuevo)
        db_session.flush()
        return int(getattr(nuevo, id_attr))

    @classmethod
    def _resolver_id_medico(cls, valor: Any, mapa: dict[str, int]) -> Optional[int]:
        for clave in cls._claves_nombre_medico(valor):
            if clave in mapa:
                return mapa[clave]
        return None

    @classmethod
    def _tiene_nombre_medico(cls, valor: Any) -> bool:
        return bool(cls._claves_nombre_medico(valor))

    @classmethod
    def _claves_nombre_medico(cls, valor: Any) -> list[str]:
        """
        Varias claves para cruzar Excel vs catálogo:
        texto exacto, tokens ordenados y sin partículas (DE/DEL/LA).
        """
        if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
            return []
        texto = estandarizar_texto(valor)
        if texto is None:
            return []
        limpio = re.sub(r"[.,;:/\\-]+", " ", texto)
        limpio = re.sub(r"\s+", " ", limpio).strip()
        if not limpio or _MEDICO_VACIO.match(limpio.replace(" ", "")):
            return []
        if set(limpio.replace(" ", "")) <= {"-"}:
            return []
        tokens = [token for token in limpio.split() if token not in _TITULOS_MEDICO]
        if not tokens:
            return []
        claves = [limpio, " ".join(sorted(tokens))]
        sin_particulas = [token for token in tokens if token not in _PARTICULAS_NOMBRE]
        if sin_particulas:
            claves.append(" ".join(sorted(sin_particulas)))
        vistas: set[str] = set()
        unicas: list[str] = []
        for clave in claves:
            if clave and clave not in vistas:
                vistas.add(clave)
                unicas.append(clave)
        return unicas

    @staticmethod
    def _es_anonimo(nombre: Any) -> bool:
        return estandarizar_texto(nombre) == NOMBRE_ANONIMO

    @staticmethod
    def _formatear_fecha(serie: pd.Series) -> pd.Series:
        """DD/MM/YYYY (u otros) -> YYYY-MM-DD."""
        fechas = pd.to_datetime(serie, dayfirst=True, errors="coerce")
        return fechas.dt.strftime("%Y-%m-%d")

    @staticmethod
    def _formatear_hora(serie: pd.Series) -> pd.Series:
        """'08:30 AM' -> '08:30:00'."""
        horas = pd.to_datetime(serie, format="%I:%M %p", errors="coerce")
        # Fallback si vienen en 24h u otro formato
        mask = horas.isna()
        if mask.any():
            horas.loc[mask] = pd.to_datetime(serie[mask], errors="coerce")
        return horas.dt.strftime("%H:%M:%S")

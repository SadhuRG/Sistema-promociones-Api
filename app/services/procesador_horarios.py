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

        # ------------------------------------------------------------------
        # Extracción de BD
        # ------------------------------------------------------------------
        especialidades = db_session.query(
            Especialidad.id_especialidad,
            Especialidad.nombre,
        ).all()
        doctores = db_session.query(
            Doctor.id_doctor,
            Doctor.nombre,
        ).all()

        df_especialidades = pd.DataFrame(
            [{"id_especialidad": e.id_especialidad, "nombre": e.nombre} for e in especialidades]
        )
        df_doctores = pd.DataFrame(
            [{"id_doctor": d.id_doctor, "nombre": d.nombre} for d in doctores]
        )

        # ------------------------------------------------------------------
        # Cruce especialidades
        # ------------------------------------------------------------------
        if df_especialidades.empty:
            df_excel["id_especialidad"] = None
        else:
            df_especialidades["nombre_std"] = df_especialidades["nombre"].apply(
                estandarizar_texto
            )
            df_especialidades = (
                df_especialidades.dropna(subset=["nombre_std"])
                .drop_duplicates(subset=["nombre_std"], keep="first")
            )
            df_excel = pd.merge(
                df_excel,
                df_especialidades[["id_especialidad", "nombre_std"]],
                left_on="Especialidad",
                right_on="nombre_std",
                how="left",
            )
            df_excel = df_excel.drop(columns=["nombre_std"], errors="ignore")

        self._asignar_anonimo_especialidad(df_excel, db_session)

        # ------------------------------------------------------------------
        # Cruce doctores
        # ------------------------------------------------------------------
        if "Medico" in df_excel.columns:
            df_excel["Medico"] = df_excel["Medico"].apply(self._normalizar_medico)

        if df_doctores.empty:
            df_excel["id_doctor"] = None
        else:
            df_doctores["nombre_std"] = df_doctores["nombre"].apply(estandarizar_texto)
            df_doctores = (
                df_doctores.dropna(subset=["nombre_std"])
                .drop_duplicates(subset=["nombre_std"], keep="first")
            )
            df_excel = pd.merge(
                df_excel,
                df_doctores[["id_doctor", "nombre_std"]],
                left_on="Medico",
                right_on="nombre_std",
                how="left",
            )
            df_excel = df_excel.drop(columns=["nombre_std"], errors="ignore")

        self._asignar_anonimo_doctor(df_excel, db_session)

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

    def _asignar_anonimo_especialidad(
        self,
        df_excel: pd.DataFrame,
        db_session: Session,
    ) -> None:
        if "id_especialidad" not in df_excel.columns:
            df_excel["id_especialidad"] = None
        sin_match = df_excel["id_especialidad"].isna()
        if not sin_match.any():
            return
        anonimo_id = self._obtener_o_crear_anonimo(
            db_session, Especialidad, "id_especialidad"
        )
        df_excel.loc[sin_match, "id_especialidad"] = anonimo_id

    def _asignar_anonimo_doctor(
        self,
        df_excel: pd.DataFrame,
        db_session: Session,
    ) -> None:
        if "id_doctor" not in df_excel.columns:
            df_excel["id_doctor"] = None
        medico = (
            df_excel["Medico"]
            if "Medico" in df_excel.columns
            else pd.Series(pd.NA, index=df_excel.index)
        )
        sin_match = df_excel["id_doctor"].isna() & medico.notna()
        if not sin_match.any():
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

    @staticmethod
    def _normalizar_medico(valor: Any) -> Optional[str]:
        """Estandariza; '-- -- --' / solo guiones -> None."""
        if pd.isna(valor):
            return None
        texto = estandarizar_texto(valor)
        if texto is None:
            return None
        if _MEDICO_VACIO.match(texto.replace(" ", "")) or texto.replace(" ", "") == "":
            return None
        # Casos tipo "-- -- --"
        if set(texto.replace(" ", "")) <= {"-"}:
            return None
        return texto

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

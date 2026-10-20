"""
Limpieza del Excel de horarios Imagina (solo RAM).
Recibe bytes / BytesIO, genera DataFrame limpio y list[dict].
"""

from __future__ import annotations

import io
import unicodedata
from typing import Any, Optional, Union

import pandas as pd

COLUMNAS_REQUERIDAS = [
    "Especialidad",
    "Medico",
    "Fecha",
    "Días de la semana",
    "Hora Inicio",
    "Hora Fin",
]


def estandarizar_texto(texto: Any) -> Optional[str]:
    """Mayúsculas, strip y sin tildes/diéresis. NaN -> None."""
    if pd.isna(texto):
        return None
    valor = str(texto).strip().upper()
    normalizado = unicodedata.normalize("NFKD", valor)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


# Alias interno (compatibilidad)
_estandarizar_texto = estandarizar_texto


def limpiar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reglas estrictas:
    - Elimina 'Consultorio'
    - Conserva solo columnas requeridas
    - Estandariza 'Especialidad' y 'Medico'
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "Consultorio" in df.columns:
        df = df.drop(columns=["Consultorio"])

    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas en el Excel: {faltantes}. Tenemos: {list(df.columns)}")

    df = df[COLUMNAS_REQUERIDAS]
    df = df.dropna(how="all")

    df["Especialidad"] = df["Especialidad"].apply(_estandarizar_texto)
    df["Medico"] = df["Medico"].apply(_estandarizar_texto)

    df = df.where(pd.notnull(df), None)
    return df


def excel_bytes_a_registros(
    contenido: Union[bytes, io.BytesIO],
) -> list[dict[str, Any]]:
    """
    Lee el Excel en memoria (skiprows=2), limpia y retorna list[dict].
    No escribe nada en disco.
    """
    buffer = contenido if isinstance(contenido, io.BytesIO) else io.BytesIO(contenido)
    buffer.seek(0)

    df = pd.read_excel(buffer, skiprows=2)
    df = limpiar_dataframe(df)
    return df.to_dict(orient="records")

"""Helpers compartidos para parsers de formularios y especialidades."""

import json
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.all_models import Especialidad


def parse_especialidad_ids(raw: Optional[str]) -> list[int]:
    """
    Acepta:
      - '1,2,3'
      - '[1,2,3]'
      - None / '' -> []
    """
    if raw is None or str(raw).strip() == "":
        return []

    text = str(raw).strip()
    try:
        if text.startswith("["):
            data = json.loads(text)
            if not isinstance(data, list):
                raise ValueError("Se esperaba una lista JSON")
            return [int(x) for x in data]

        return [int(x.strip()) for x in text.split(",") if x.strip()]
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="especialidad_ids inválido. Usa '1,2,3' o '[1,2,3]'",
        ) from exc


def get_especialidades_by_ids(db: Session, ids: list[int]) -> list[Especialidad]:
    """Obtiene especialidades y valida que todos los IDs existan."""
    if not ids:
        return []

    especialidades = (
        db.query(Especialidad)
        .filter(Especialidad.id_especialidad.in_(ids))
        .all()
    )
    encontrados = {esp.id_especialidad for esp in especialidades}
    faltantes = set(ids) - encontrados
    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Especialidades no encontradas: {sorted(faltantes)}",
        )
    return especialidades

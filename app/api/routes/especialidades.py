from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_admin_user
from app.db.database import get_db
from app.models.all_models import Especialidad, User
from app.schemas.all_schemas import (
    EspecialidadCreate,
    EspecialidadResponse,
    EspecialidadUpdate,
    EstadoUpdate,
)

router = APIRouter(prefix="/especialidades", tags=["Especialidades"])


def _get_especialidad_or_404(db: Session, id_especialidad: int) -> Especialidad:
    especialidad = (
        db.query(Especialidad)
        .filter(Especialidad.id_especialidad == id_especialidad)
        .first()
    )
    if not especialidad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Especialidad no encontrada",
        )
    return especialidad


@router.get("/", response_model=list[EspecialidadResponse])
def listar_especialidades(
    estado: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> list[Especialidad]:
    """Público: lista especialidades. Usa ?estado=Activo para selectores."""
    query = db.query(Especialidad)
    if estado:
        query = query.filter(Especialidad.estado == estado)
    return query.order_by(Especialidad.id_especialidad.asc()).all()


@router.get("/{id_especialidad}", response_model=EspecialidadResponse)
def obtener_especialidad(
    id_especialidad: int,
    db: Session = Depends(get_db),
) -> Especialidad:
    """Público: obtiene una especialidad por ID."""
    return _get_especialidad_or_404(db, id_especialidad)


@router.post("/", response_model=EspecialidadResponse, status_code=status.HTTP_201_CREATED)
def crear_especialidad(
    payload: EspecialidadCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Especialidad:
    """Admin: crea una especialidad."""
    especialidad = Especialidad(**payload.model_dump())
    db.add(especialidad)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo crear la especialidad: {exc}",
        ) from exc

    db.refresh(especialidad)
    return especialidad


@router.put("/{id_especialidad}", response_model=EspecialidadResponse)
def actualizar_especialidad(
    id_especialidad: int,
    payload: EspecialidadUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Especialidad:
    """Admin: actualiza una especialidad."""
    especialidad = _get_especialidad_or_404(db, id_especialidad)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(especialidad, campo, valor)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo actualizar la especialidad: {exc}",
        ) from exc

    db.refresh(especialidad)
    return especialidad


@router.put("/{id_especialidad}/estado", response_model=EspecialidadResponse)
def actualizar_estado_especialidad(
    id_especialidad: int,
    payload: EstadoUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Especialidad:
    """Admin: cambia el estado lógico (Activo / Inactivo)."""
    especialidad = _get_especialidad_or_404(db, id_especialidad)
    especialidad.estado = payload.estado

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo actualizar el estado: {exc}",
        ) from exc

    db.refresh(especialidad)
    return especialidad


@router.delete("/{id_especialidad}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_especialidad(
    id_especialidad: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> None:
    """Admin: elimina una especialidad."""
    especialidad = _get_especialidad_or_404(db, id_especialidad)
    db.delete(especialidad)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo eliminar la especialidad: {exc}",
        ) from exc

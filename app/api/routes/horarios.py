from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_admin_user
from app.db.database import get_db
from app.models.all_models import Doctor, Horario, User
from app.schemas.all_schemas import HorarioCreate, HorarioResponse, HorarioUpdate

router = APIRouter(prefix="/horarios", tags=["Horarios"])


def _get_horario_or_404(db: Session, id_horario: int) -> Horario:
    horario = db.query(Horario).filter(Horario.id_horario == id_horario).first()
    if not horario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Horario no encontrado",
        )
    return horario


def _validar_doctor(db: Session, id_doctor: Optional[int]) -> None:
    if id_doctor is None:
        return
    doctor = db.query(Doctor).filter(Doctor.id_doctor == id_doctor).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Doctor con id {id_doctor} no existe",
        )


def _validar_cruce_horarios(
    db: Session,
    id_doctor: Optional[int],
    dia_semana: Optional[str],
    hora_inicio,
    hora_fin,
    exclude_id: Optional[int] = None,
) -> None:
    if not id_doctor or not dia_semana or not hora_inicio or not hora_fin:
        return

    query = db.query(Horario).filter(
        Horario.id_doctor == id_doctor,
        Horario.dia_semana == dia_semana,
        Horario.hora_inicio < hora_fin,
        Horario.hora_fin > hora_inicio,
    )
    if exclude_id is not None:
        query = query.filter(Horario.id_horario != exclude_id)

    conflicto = query.first()
    if conflicto:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El doctor ya tiene un horario que se cruza ese día "
                f"({conflicto.hora_inicio} - {conflicto.hora_fin})."
            ),
        )


@router.get("/", response_model=list[HorarioResponse])
def listar_horarios(
    id_doctor: Optional[int] = Query(None),
    estado: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> list[Horario]:
    """Público: lista horarios con filtros opcionales."""
    query = db.query(Horario)

    if id_doctor is not None:
        query = query.filter(Horario.id_doctor == id_doctor)
    if estado:
        query = query.filter(Horario.estado == estado)

    return query.order_by(Horario.id_horario.desc()).all()


@router.get("/{id_horario}", response_model=HorarioResponse)
def obtener_horario(id_horario: int, db: Session = Depends(get_db)) -> Horario:
    """Público: obtiene un horario por ID."""
    return _get_horario_or_404(db, id_horario)


@router.post("/", response_model=HorarioResponse, status_code=status.HTTP_201_CREATED)
def crear_horario(
    payload: HorarioCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Horario:
    """Admin: crea un horario."""
    _validar_doctor(db, payload.id_doctor)
    _validar_cruce_horarios(
        db,
        payload.id_doctor,
        payload.dia_semana,
        payload.hora_inicio,
        payload.hora_fin,
    )

    horario = Horario(**payload.model_dump())
    db.add(horario)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo crear el horario: {exc}",
        ) from exc

    db.refresh(horario)
    return horario


@router.put("/{id_horario}", response_model=HorarioResponse)
def actualizar_horario(
    id_horario: int,
    payload: HorarioUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Horario:
    """Admin: actualiza un horario."""
    horario = _get_horario_or_404(db, id_horario)
    data = payload.model_dump(exclude_unset=True)

    if "id_doctor" in data:
        _validar_doctor(db, data["id_doctor"])

    hora_inicio = data.get("hora_inicio", horario.hora_inicio)
    hora_fin = data.get("hora_fin", horario.hora_fin)
    if hora_inicio and hora_fin and hora_fin <= hora_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="hora_fin debe ser posterior a hora_inicio",
        )

    _validar_cruce_horarios(
        db,
        data.get("id_doctor", horario.id_doctor),
        data.get("dia_semana", horario.dia_semana),
        hora_inicio,
        hora_fin,
        exclude_id=id_horario,
    )

    for campo, valor in data.items():
        setattr(horario, campo, valor)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo actualizar el horario: {exc}",
        ) from exc

    db.refresh(horario)
    return horario


@router.delete("/{id_horario}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_horario(
    id_horario: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> None:
    """Admin: elimina un horario."""
    horario = _get_horario_or_404(db, id_horario)
    db.delete(horario)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo eliminar el horario: {exc}",
        ) from exc

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_admin_user
from app.db.database import get_db
from app.models.all_models import Doctor, Horario, User
from app.schemas.all_schemas import DoctorCreate, DoctorResponse, DoctorUpdate

router = APIRouter(prefix="/doctores", tags=["Doctores"])


def _get_doctor_or_404(db: Session, id_doctor: int) -> Doctor:
    doctor = db.query(Doctor).filter(Doctor.id_doctor == id_doctor).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor no encontrado",
        )
    return doctor


@router.get("/", response_model=list[DoctorResponse])
def listar_doctores(
    estado: Optional[str] = Query(None),
    especialidad_id: Optional[int] = Query(
        None,
        description="Filtra doctores que tengan al menos un horario con esa especialidad",
    ),
    db: Session = Depends(get_db),
) -> list[Doctor]:
    """Público: lista doctores. En V2 ya no existe doctor_especialidad."""
    query = db.query(Doctor)

    if estado:
        query = query.filter(Doctor.estado == estado)

    # Relación doctor↔especialidad ahora pasa por horario
    if especialidad_id is not None:
        query = (
            query.join(Horario, Horario.id_doctor == Doctor.id_doctor)
            .filter(Horario.id_especialidad == especialidad_id)
            .distinct()
        )

    return query.order_by(Doctor.id_doctor.asc()).all()


@router.get("/{id_doctor}", response_model=DoctorResponse)
def obtener_doctor(id_doctor: int, db: Session = Depends(get_db)) -> Doctor:
    """Público: obtiene un doctor por ID."""
    return _get_doctor_or_404(db, id_doctor)


@router.post("/", response_model=DoctorResponse, status_code=status.HTTP_201_CREATED)
def crear_doctor(
    payload: DoctorCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Doctor:
    """Admin: crea un doctor."""
    doctor = Doctor(nombre=payload.nombre, estado=payload.estado)
    db.add(doctor)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo crear el doctor: {exc}",
        ) from exc

    db.refresh(doctor)
    return doctor


@router.put("/{id_doctor}", response_model=DoctorResponse)
def actualizar_doctor(
    id_doctor: int,
    payload: DoctorUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Doctor:
    """Admin: actualiza nombre/estado del doctor."""
    doctor = _get_doctor_or_404(db, id_doctor)
    data = payload.model_dump(exclude_unset=True)

    for campo, valor in data.items():
        setattr(doctor, campo, valor)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo actualizar el doctor: {exc}",
        ) from exc

    db.refresh(doctor)
    return doctor


@router.delete("/{id_doctor}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_doctor(
    id_doctor: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> None:
    """Admin: elimina un doctor."""
    doctor = _get_doctor_or_404(db, id_doctor)
    db.delete(doctor)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo eliminar el doctor: {exc}",
        ) from exc

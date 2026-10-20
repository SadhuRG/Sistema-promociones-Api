from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_admin_user
from app.db.database import get_db
from app.models.all_models import Doctor, Especialidad, Horario, User
from app.schemas.all_schemas import (
    HorarioCreate,
    HorarioResponse,
    HorarioSyncAutoRequest,
    HorarioSyncAutoResponse,
    HorarioUpdate,
)
from app.services.db_horarios_sync import DBHorariosSyncService
from app.services.procesador_horarios import ProcesadorHorariosService
from app.services.sync_imagina import ImaginaSyncService

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


def _validar_especialidad(db: Session, id_especialidad: Optional[int]) -> None:
    if id_especialidad is None:
        return
    especialidad = (
        db.query(Especialidad)
        .filter(Especialidad.id_especialidad == id_especialidad)
        .first()
    )
    if not especialidad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Especialidad con id {id_especialidad} no existe",
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
    id_especialidad: Optional[int] = Query(None),
    estado: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> list[Horario]:
    """Público: lista horarios con filtros opcionales (campos V2 incluidos en response)."""
    query = db.query(Horario)

    if id_doctor is not None:
        query = query.filter(Horario.id_doctor == id_doctor)
    if id_especialidad is not None:
        query = query.filter(Horario.id_especialidad == id_especialidad)
    if estado:
        query = query.filter(Horario.estado == estado)

    return query.order_by(Horario.id_horario.desc()).all()


def _dd_mm_yyyy_a_sql(fecha: str) -> str:
    """DD/MM/YYYY -> YYYY-MM-DD."""
    try:
        return datetime.strptime(fecha.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fecha inválida '{fecha}'. Usa DD/MM/YYYY.",
        ) from exc


@router.post("/sync-auto", response_model=HorarioSyncAutoResponse)
def sync_auto_horarios(
    payload: HorarioSyncAutoRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> HorarioSyncAutoResponse:
    """
    Admin: sincronización por espejo desde Imagina.
    login -> preparar_reporte -> verificar_cambios -> descargar -> procesar -> DELETE+INSERT.
    """
    url = settings.IMAGINA_EXCEL_URL
    if not url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="IMAGINA_EXCEL_URL no está configurada",
        )

    fecha_inicio_sql = _dd_mm_yyyy_a_sql(payload.fecha_inicio)
    fecha_fin_sql = _dd_mm_yyyy_a_sql(payload.fecha_fin)
    if fecha_fin_sql < fecha_inicio_sql:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_fin debe ser posterior o igual a fecha_inicio",
        )

    imagina = ImaginaSyncService()

    if not imagina.login():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo iniciar sesión en Imagina",
        )

    if not imagina.preparar_reporte(payload.fecha_inicio, payload.fecha_fin):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo preparar el reporte de horarios en Imagina",
        )

    meta = imagina.verificar_cambios(url)
    if meta.get("error"):
        # Si HEAD falla, continuamos con descarga (misma política que el servicio)
        pass
    elif not meta.get("hay_cambios", True):
        return HorarioSyncAutoResponse(
            status="up_to_date",
            message="Los horarios ya están actualizados",
            registros_insertados=0,
        )

    datos_excel = imagina.descargar_excel(url)
    if datos_excel is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Falló la descarga/limpieza del Excel de Imagina",
        )

    try:
        datos_procesados = ProcesadorHorariosService().procesar(datos_excel, db)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar horarios: {exc}",
        ) from exc

    try:
        insertados = DBHorariosSyncService().sincronizar_en_bd(
            datos_procesados=datos_procesados,
            db_session=db,
            fecha_inicio_sql=fecha_inicio_sql,
            fecha_fin_sql=fecha_fin_sql,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sincronizar en base de datos: {exc}",
        ) from exc

    return HorarioSyncAutoResponse(
        status="success",
        message="Sincronización completa",
        registros_insertados=insertados,
    )


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
    """Admin: crea un horario (campos V2: fecha, id_especialidad aceptados)."""
    _validar_doctor(db, payload.id_doctor)
    _validar_especialidad(db, payload.id_especialidad)
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
    if "id_especialidad" in data:
        _validar_especialidad(db, data["id_especialidad"])

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

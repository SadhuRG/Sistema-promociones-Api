from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.api.routes.helpers import get_especialidades_by_ids, parse_especialidad_ids
from app.core.security import get_current_admin_user
from app.core.storage import upload_image_to_supabase
from app.db.database import get_db
from app.models.all_models import Promocion, User, promocion_especialidad
from app.schemas.all_schemas import PromocionResponse

router = APIRouter(prefix="/promociones", tags=["Promociones"])


def _get_promocion_or_404(db: Session, id_promocion: int) -> Promocion:
    promocion = (
        db.query(Promocion)
        .options(joinedload(Promocion.especialidades))
        .filter(Promocion.id_promocion == id_promocion)
        .first()
    )
    if not promocion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promoción no encontrada",
        )
    return promocion


@router.get("/", response_model=list[PromocionResponse])
def listar_promociones(
    especialidad_id: Optional[int] = Query(None, description="Filtrar por especialidad"),
    estado: Optional[str] = Query(None, description="Activo | Inactivo"),
    titulo: Optional[str] = Query(None, description="Busca en el nombre (ILIKE)"),
    db: Session = Depends(get_db),
) -> list[Promocion]:
    """Público: lista promociones con especialidades y filtros opcionales."""
    query = db.query(Promocion).options(joinedload(Promocion.especialidades))

    if estado:
        query = query.filter(Promocion.estado == estado)

    if titulo:
        query = query.filter(Promocion.nombre.ilike(f"%{titulo}%"))

    if especialidad_id is not None:
        query = (
            query.join(promocion_especialidad)
            .filter(promocion_especialidad.c.id_especialidad == especialidad_id)
            .distinct()
        )

    return query.order_by(Promocion.id_promocion.desc()).all()


@router.get("/{id_promocion}", response_model=PromocionResponse)
def obtener_promocion(id_promocion: int, db: Session = Depends(get_db)) -> Promocion:
    """Público: obtiene una promoción por ID."""
    return _get_promocion_or_404(db, id_promocion)


@router.post("/", response_model=PromocionResponse, status_code=status.HTTP_201_CREATED)
async def crear_promocion(
    nombre: str = Form(...),
    fecha_inicio: Optional[date] = Form(None),
    fecha_fin: Optional[date] = Form(None),
    estado: str = Form("Activo"),
    especialidad_ids: Optional[str] = Form(
        None,
        description="IDs separados por coma o JSON: 1,2,3 ó [1,2,3]",
    ),
    imagen: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Promocion:
    """Admin: crea promoción, sube imagen opcional y relaciona especialidades."""
    if fecha_inicio and fecha_fin and fecha_fin <= fecha_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_fin debe ser posterior a fecha_inicio",
        )

    ids = parse_especialidad_ids(especialidad_ids)
    especialidades = get_especialidades_by_ids(db, ids)

    imagen_url: Optional[str] = None
    if imagen and imagen.filename:
        imagen_url = await upload_image_to_supabase(imagen, folder="promociones")

    promocion = Promocion(
        nombre=nombre,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        estado=estado,
        promocion_img=imagen_url,
    )
    promocion.especialidades = especialidades

    db.add(promocion)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo crear la promoción: {exc}",
        ) from exc

    return _get_promocion_or_404(db, promocion.id_promocion)


@router.put("/{id_promocion}", response_model=PromocionResponse)
async def actualizar_promocion(
    id_promocion: int,
    nombre: Optional[str] = Form(None),
    fecha_inicio: Optional[date] = Form(None),
    fecha_fin: Optional[date] = Form(None),
    estado: Optional[str] = Form(None),
    especialidad_ids: Optional[str] = Form(None),
    imagen: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Promocion:
    """Admin: actualiza datos, imagen y sincroniza especialidades."""
    promocion = _get_promocion_or_404(db, id_promocion)

    if nombre is not None:
        promocion.nombre = nombre
    if fecha_inicio is not None:
        promocion.fecha_inicio = fecha_inicio
    if fecha_fin is not None:
        promocion.fecha_fin = fecha_fin
    if estado is not None:
        promocion.estado = estado

    fi = promocion.fecha_inicio
    ff = promocion.fecha_fin
    if fi and ff and ff <= fi:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_fin debe ser posterior a fecha_inicio",
        )

    if imagen and imagen.filename:
        promocion.promocion_img = await upload_image_to_supabase(
            imagen, folder="promociones"
        )

    # Si se envía especialidad_ids (incluso vacío), se sincroniza
    if especialidad_ids is not None:
        ids = parse_especialidad_ids(especialidad_ids)
        promocion.especialidades = get_especialidades_by_ids(db, ids)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo actualizar la promoción: {exc}",
        ) from exc

    return _get_promocion_or_404(db, id_promocion)


@router.delete("/{id_promocion}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_promocion(
    id_promocion: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> None:
    """Admin: borrado físico de la promoción."""
    promocion = db.query(Promocion).filter(Promocion.id_promocion == id_promocion).first()
    if not promocion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promoción no encontrada",
        )

    db.delete(promocion)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo eliminar la promoción: {exc}",
        ) from exc

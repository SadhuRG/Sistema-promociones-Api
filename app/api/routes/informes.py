from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.api.routes.helpers import get_especialidades_by_ids, parse_especialidad_ids
from app.core.security import get_current_admin_user
from app.core.storage import upload_image_to_supabase
from app.db.database import get_db
from app.models.all_models import Informe, User, informe_especialidad
from app.schemas.all_schemas import InformeResponse

router = APIRouter(prefix="/informes", tags=["Informes"])


def _get_informe_or_404(db: Session, id_informe: int) -> Informe:
    informe = (
        db.query(Informe)
        .options(joinedload(Informe.especialidades))
        .filter(Informe.id_informe == id_informe)
        .first()
    )
    if not informe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Informe no encontrado",
        )
    return informe


@router.get("/", response_model=list[InformeResponse])
def listar_informes(
    especialidad_id: Optional[int] = Query(None),
    titulo: Optional[str] = Query(None, description="Busca en el título (ILIKE)"),
    db: Session = Depends(get_db),
) -> list[Informe]:
    """Público: lista informes con especialidades."""
    query = db.query(Informe).options(joinedload(Informe.especialidades))

    if titulo:
        query = query.filter(Informe.titulo.ilike(f"%{titulo}%"))

    if especialidad_id is not None:
        query = (
            query.join(informe_especialidad)
            .filter(informe_especialidad.c.id_especialidad == especialidad_id)
            .distinct()
        )

    return query.order_by(Informe.id_informe.desc()).all()


@router.get("/{id_informe}", response_model=InformeResponse)
def obtener_informe(id_informe: int, db: Session = Depends(get_db)) -> Informe:
    """Público: obtiene un informe por ID."""
    return _get_informe_or_404(db, id_informe)


@router.post("/", response_model=InformeResponse, status_code=status.HTTP_201_CREATED)
async def crear_informe(
    titulo: str = Form(...),
    descripcion: Optional[str] = Form(None),
    especialidad_ids: Optional[str] = Form(None),
    imagen: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Informe:
    """Admin: crea informe con imagen opcional y especialidades."""
    ids = parse_especialidad_ids(especialidad_ids)
    especialidades = get_especialidades_by_ids(db, ids)

    imagen_url: Optional[str] = None
    if imagen and imagen.filename:
        imagen_url = await upload_image_to_supabase(imagen, folder="informes")

    informe = Informe(
        titulo=titulo,
        descripcion=descripcion,
        informe_img=imagen_url,
    )
    informe.especialidades = especialidades

    db.add(informe)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo crear el informe: {exc}",
        ) from exc

    return _get_informe_or_404(db, informe.id_informe)


@router.put("/{id_informe}", response_model=InformeResponse)
async def actualizar_informe(
    id_informe: int,
    titulo: Optional[str] = Form(None),
    descripcion: Optional[str] = Form(None),
    especialidad_ids: Optional[str] = Form(None),
    imagen: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Informe:
    """Admin: actualiza informe, imagen y especialidades."""
    informe = _get_informe_or_404(db, id_informe)

    if titulo is not None:
        informe.titulo = titulo
    if descripcion is not None:
        informe.descripcion = descripcion

    if imagen and imagen.filename:
        informe.informe_img = await upload_image_to_supabase(imagen, folder="informes")

    if especialidad_ids is not None:
        ids = parse_especialidad_ids(especialidad_ids)
        informe.especialidades = get_especialidades_by_ids(db, ids)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo actualizar el informe: {exc}",
        ) from exc

    return _get_informe_or_404(db, id_informe)


@router.delete("/{id_informe}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_informe(
    id_informe: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> None:
    """Admin: elimina un informe."""
    informe = db.query(Informe).filter(Informe.id_informe == id_informe).first()
    if not informe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Informe no encontrado",
        )

    db.delete(informe)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo eliminar el informe: {exc}",
        ) from exc

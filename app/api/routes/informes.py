from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.api.routes.helpers import get_especialidades_by_ids, parse_especialidad_ids
from app.core.security import get_current_admin_user, get_optional_user
from app.core.storage import upload_image_to_supabase
from app.db.database import get_db
from app.models.all_models import Informe, User, informe_especialidad
from app.schemas.all_schemas import InformeEstadoUpdate, InformeResponse

router = APIRouter(prefix="/informes", tags=["Informes"])


def _is_admin(user: Optional[User]) -> bool:
    return bool(user and user.rol == "Admin")


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
    estado: Optional[bool] = Query(
        None,
        description=(
            "Filtra por estado booleano. El público y los usuarios solo ven activos. "
            "Un Admin sin este parámetro recibe todos."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
) -> list[Informe]:
    """Lista informes. Usuarios: solo activos. Admin: todos, salvo que envíe ?estado=."""
    query = db.query(Informe).options(joinedload(Informe.especialidades))

    if _is_admin(current_user):
        if estado is not None:
            query = query.filter(Informe.estado.is_(estado))
    else:
        query = query.filter(Informe.estado.is_(True))

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
def obtener_informe(
    id_informe: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
) -> Informe:
    """Público/usuario: solo si está activo. Admin: cualquiera."""
    informe = _get_informe_or_404(db, id_informe)
    if not _is_admin(current_user) and not informe.estado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Informe no encontrado",
        )
    return informe


@router.post("/", response_model=InformeResponse, status_code=status.HTTP_201_CREATED)
async def crear_informe(
    titulo: str = Form(...),
    descripcion: Optional[str] = Form(None),
    especialidad_ids: Optional[str] = Form(None),
    imagen: Optional[UploadFile] = File(None),
    estado: Optional[bool] = Form(True),
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
        estado=True if estado is None else estado,
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


@router.put("/{id_informe}/estado", response_model=InformeResponse)
def actualizar_estado_informe(
    id_informe: int,
    payload: InformeEstadoUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Informe:
    """Admin: activa o desactiva un informe."""
    informe = _get_informe_or_404(db, id_informe)
    informe.estado = payload.estado

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo actualizar el estado: {exc}",
        ) from exc

    return _get_informe_or_404(db, id_informe)


@router.put("/{id_informe}", response_model=InformeResponse)
async def actualizar_informe(
    id_informe: int,
    titulo: Optional[str] = Form(None),
    descripcion: Optional[str] = Form(None),
    especialidad_ids: Optional[str] = Form(None),
    imagen: Optional[UploadFile] = File(None),
    estado: Optional[bool] = Form(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> Informe:
    """Admin: actualiza informe, imagen, especialidades y estado."""
    informe = _get_informe_or_404(db, id_informe)

    if titulo is not None:
        informe.titulo = titulo
    if descripcion is not None:
        informe.descripcion = descripcion
    if estado is not None:
        informe.estado = estado
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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_admin_user
from app.db.database import get_db
from app.models.all_models import User
from app.schemas.all_schemas import UserResponse, UserRolUpdate, UserUpdate

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

SELF_ACTION_DETAIL = "No puedes modificar ni eliminar tu propio usuario administrador"


def _ensure_not_self(target_id: int, current_user: User) -> None:
    if target_id == current_user.id_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=SELF_ACTION_DETAIL,
        )


def _get_usuario_or_404(db: Session, id_user: int) -> User:
    usuario = db.query(User).filter(User.id_user == id_user).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return usuario


@router.get("/", response_model=list[UserResponse])
def listar_usuarios(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> list[User]:
    """Admin: lista todos los usuarios."""
    return db.query(User).order_by(User.id_user.asc()).all()


@router.put("/{id_user}", response_model=UserResponse)
def actualizar_usuario(
    id_user: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> User:
    """Admin: actualiza nombre, rol y estado. Sobre uno mismo solo aplica el nombre."""
    usuario = _get_usuario_or_404(db, id_user)
    data = payload.model_dump(exclude_unset=True)
    is_self = id_user == current_user.id_user

    if "nombre_usuario" in data and data["nombre_usuario"]:
        usuario.nombre_usuario = data["nombre_usuario"].strip()

    if not is_self:
        if "rol" in data and data["rol"]:
            usuario.rol = data["rol"]
        if "estado" in data and data["estado"]:
            usuario.estado = data["estado"]

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo actualizar el usuario: {exc}",
        ) from exc

    db.refresh(usuario)
    return usuario


@router.put("/{id_user}/rol", response_model=UserResponse)
def actualizar_rol_usuario(
    id_user: int,
    payload: UserRolUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> User:
    """Admin: actualiza el rol de otro usuario (Admin | User | Marketing)."""
    _ensure_not_self(id_user, current_user)
    usuario = _get_usuario_or_404(db, id_user)
    usuario.rol = payload.rol

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo actualizar el rol: {exc}",
        ) from exc

    db.refresh(usuario)
    return usuario


@router.delete("/{id_user}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(
    id_user: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> None:
    """Admin: borrado físico de otro usuario."""
    _ensure_not_self(id_user, current_user)
    usuario = _get_usuario_or_404(db, id_user)
    db.delete(usuario)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo eliminar el usuario: {exc}",
        ) from exc

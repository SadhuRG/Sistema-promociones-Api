from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_admin_user
from app.db.database import get_db
from app.models.all_models import User
from app.schemas.all_schemas import UserResponse, UserRolUpdate, UserUpdate

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

SELF_DELETE_DETAIL = "No puedes eliminar tu propio usuario"
SUPERADMIN_EDIT_DETAIL = "No puedes modificar a un SuperAdmin"
SUPERADMIN_DELETE_DETAIL = "No puedes eliminar a un SuperAdmin"
SUPERADMIN_ASSIGN_DETAIL = "No puedes asignar el rol SuperAdmin"
ROLE_ESCALATION_DETAIL = "No puedes asignar un rol superior al tuyo"

ROLE_RANK = {
    "User": 1,
    "Marketing": 1,
    "Admin": 2,
    "SuperAdmin": 3,
}


def _rank(rol: str) -> int:
    return ROLE_RANK.get(str(rol or ""), 0)


def _get_usuario_or_404(db: Session, id_user: int) -> User:
    usuario = db.query(User).filter(User.id_user == id_user).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return usuario


def _ensure_can_edit(actor: User, target: User) -> None:
    if actor.id_user == target.id_user:
        return
    if target.rol == "SuperAdmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=SUPERADMIN_EDIT_DETAIL,
        )


def _ensure_can_delete(actor: User, target: User) -> None:
    if actor.id_user == target.id_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=SELF_DELETE_DETAIL,
        )
    if target.rol == "SuperAdmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=SUPERADMIN_DELETE_DETAIL,
        )


def _ensure_can_assign_role(actor: User, new_rol: str) -> None:
    if not new_rol:
        return
    if new_rol == "SuperAdmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=SUPERADMIN_ASSIGN_DETAIL,
        )
    if _rank(new_rol) > _rank(actor.rol):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ROLE_ESCALATION_DETAIL,
        )


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
    """Actualiza nombre, rol y estado. Un SuperAdmin ajeno no se toca; sobre uno mismo solo el nombre."""
    usuario = _get_usuario_or_404(db, id_user)
    _ensure_can_edit(current_user, usuario)
    data = payload.model_dump(exclude_unset=True)
    is_self = id_user == current_user.id_user

    if "nombre_usuario" in data and data["nombre_usuario"]:
        usuario.nombre_usuario = data["nombre_usuario"].strip()

    if not is_self:
        if "rol" in data and data["rol"]:
            _ensure_can_assign_role(current_user, data["rol"])
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
    """Actualiza el rol de otro usuario. Nadie cambia a un SuperAdmin ni asigna SuperAdmin."""
    usuario = _get_usuario_or_404(db, id_user)
    _ensure_can_edit(current_user, usuario)
    if current_user.id_user == usuario.id_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes cambiar tu propio rol",
        )
    _ensure_can_assign_role(current_user, payload.rol)
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
    """Borrado físico de otro usuario. Nadie elimina a un SuperAdmin."""
    usuario = _get_usuario_or_404(db, id_user)
    _ensure_can_delete(current_user, usuario)
    db.delete(usuario)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo eliminar el usuario: {exc}",
        ) from exc

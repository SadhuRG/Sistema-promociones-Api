from fastapi import APIRouter, Depends

from app.core.security import get_current_superadmin_user
from app.models.all_models import User

router = APIRouter(prefix="/cierres", tags=["Cierres de Caja"])


@router.get("/verify-access")
def verify_access(
    current_user: User = Depends(get_current_superadmin_user),
) -> dict:
    """Confirma que el JWT corresponde a un SuperAdmin activo."""
    return {
        "ok": True,
        "mensaje": "Acceso autorizado al módulo de Cierres de Caja",
        "rol": current_user.rol,
        "nombre_usuario": current_user.nombre_usuario,
    }

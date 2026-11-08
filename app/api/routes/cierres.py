from fastapi import APIRouter, Depends

from app.core.security import get_current_superadmin_user, verify_finance_pin
from app.models.all_models import User

router = APIRouter(
    prefix="/cierres",
    tags=["Cierres de Caja"],
    dependencies=[Depends(get_current_superadmin_user), Depends(verify_finance_pin)],
)


@router.get("/verify-access")
def verify_access(
    current_user: User = Depends(get_current_superadmin_user),
) -> dict:
    """Confirma SuperAdmin + PIN financiero para el módulo de cierres."""
    return {
        "ok": True,
        "mensaje": "Acceso autorizado al módulo de Cierres de Caja",
        "rol": current_user.rol,
        "nombre_usuario": current_user.nombre_usuario,
    }

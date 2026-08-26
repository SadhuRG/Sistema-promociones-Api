from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.all_models import User
from app.schemas.all_schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Devuelve el perfil del usuario autenticado (validado vía JWT de Supabase)."""
    return current_user

from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.all_models import User

security_scheme = HTTPBearer(auto_error=True)
optional_security_scheme = HTTPBearer(auto_error=False)

_jwks_client = PyJWKClient(settings.SUPABASE_JWKS_URL)


def _decode_supabase_token(token: str) -> dict:
    """Valida el JWT de Supabase usando el JWKS público."""
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience="authenticated",
            options={"verify_aud": True},
        )
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _load_user_from_token(token: str, db: Session) -> User:
    payload = _decode_supabase_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario (sub)",
        )

    try:
        user_uuid = UUID(str(sub))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="UUID de usuario inválido en el token",
        ) from exc

    user = (
        db.query(User)
        .filter(User.id_user_supabase == user_uuid)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en la base de datos",
        )
    if user.estado != "Activo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Valida el JWT y retorna el usuario local vinculado a Supabase Auth."""
    return _load_user_from_token(credentials.credentials, db)


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Igual que get_current_user, pero sin token (o token inválido) retorna None."""
    if not credentials or not credentials.credentials:
        return None
    try:
        return _load_user_from_token(credentials.credentials, db)
    except HTTPException:
        return None


def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Exige rol Admin o SuperAdmin (el SuperAdmin hereda el panel administrativo)."""
    if current_user.rol not in ("Admin", "SuperAdmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador",
        )
    return current_user


def get_current_superadmin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Exige que el usuario autenticado tenga rol SuperAdmin."""
    if current_user.rol != "SuperAdmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de SuperAdmin",
        )
    return current_user

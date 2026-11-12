from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_superadmin_user, verify_finance_pin
from app.db.database import get_db
from app.models.all_models import CierreCaja, User
from app.schemas.all_schemas import (
    CierreCajaResponse,
    CierreExtraerRequest,
    CierreExtraerResponse,
    CierreRegistrarRequest,
)
from app.services_cierres.extraer_cierres import calcular_total_neto, extraer_cajeros_imagina

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


@router.post("/extraer", response_model=CierreExtraerResponse)
def extraer_cierres(
    payload: CierreExtraerRequest,
    _: User = Depends(get_current_superadmin_user),
) -> CierreExtraerResponse:
    """Descarga el Excel de Imagina (rango de fechas) y resume cajeros. No escribe en BD."""
    try:
        resultado = extraer_cajeros_imagina(
            fecha_inicio=payload.fecha_inicio,
            fecha_fin=payload.fecha_fin,
            empresa_id=payload.empresa_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al extraer cierres: {exc}",
        ) from exc
    return CierreExtraerResponse(**resultado)


@router.post("/registrar", response_model=CierreCajaResponse, status_code=status.HTTP_201_CREATED)
def registrar_cierre(
    payload: CierreRegistrarRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin_user),
) -> CierreCaja:
    """Inserta un cierre en cierres_caja. No actualiza ni borra filas previas."""
    tipo = payload.devolucion_tipo or ""
    afecta = payload.devolucion_afecta or ""
    dev = float(payload.devolucion_monto or 0)
    if "otra caja" in tipo.lower() and dev > 0 and afecta.strip().lower() not in ("efectivo", "pos"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seleccione a qué medio afecta la devolución (Efectivo o POS).",
        )

    efectivo_final, pos_final, total_neto = calcular_total_neto(
        efectivo=float(payload.efectivo or 0),
        pos=float(payload.pos or 0),
        yape=float(payload.yape or 0),
        transferencia=float(payload.transferencia or 0),
        deposito=float(payload.deposito or 0),
        devolucion_monto=dev,
        devolucion_tipo=tipo,
        devolucion_afecta=afecta,
    )

    cierre = CierreCaja(
        nombre_cajero=payload.nombre_cajero.strip(),
        area_cajero=(payload.area_cajero or None),
        id_admin_registro=current_user.id_user,
        fecha_cierre=payload.fecha_cierre,
        efectivo=efectivo_final,
        pos=pos_final,
        yape=float(payload.yape or 0),
        transferencia=float(payload.transferencia or 0),
        deposito=float(payload.deposito or 0),
        devolucion_monto=dev,
        devolucion_tipo=tipo or None,
        devolucion_afecta=afecta or None,
        total_neto=total_neto,
        estado="Completado",
    )
    db.add(cierre)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo registrar el cierre: {exc}",
        ) from exc
    db.refresh(cierre)
    return cierre

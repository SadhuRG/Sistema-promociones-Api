from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_superadmin_user, verify_finance_pin
from app.db.database import get_db
from app.models.all_models import CierreCaja, User
from app.schemas.all_schemas import (
    CierreCajaResponse,
    CierreCajaUpdate,
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


@router.get("", response_model=list[CierreCajaResponse], include_in_schema=False)
@router.get("/", response_model=list[CierreCajaResponse])
def listar_cierres(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin_user),
) -> list[CierreCaja]:
    """Lista cierres guardados, del más reciente al más antiguo. No altera filas."""
    return (
        db.query(CierreCaja)
        .order_by(CierreCaja.fecha_cierre.desc(), CierreCaja.id_cierre.desc())
        .all()
    )


@router.put("/{id_cierre}", response_model=CierreCajaResponse)
def actualizar_cierre(
    id_cierre: int,
    payload: CierreCajaUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin_user),
) -> CierreCaja:
    """Actualiza montos y/o URL del PDF de un cierre existente."""
    cierre = db.query(CierreCaja).filter(CierreCaja.id_cierre == id_cierre).first()
    if not cierre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cierre de caja no encontrado",
        )

    cambios = payload.model_dump(exclude_unset=True)
    if "pdf_informe_url" in cambios:
        cierre.pdf_informe_url = cambios["pdf_informe_url"]

    montos = {
        "efectivo": float(cambios["efectivo"]) if "efectivo" in cambios else float(cierre.efectivo or 0),
        "pos": float(cambios["pos"]) if "pos" in cambios else float(cierre.pos or 0),
        "yape": float(cambios["yape"]) if "yape" in cambios else float(cierre.yape or 0),
        "transferencia": float(cambios["transferencia"]) if "transferencia" in cambios else float(cierre.transferencia or 0),
        "deposito": float(cambios["deposito"]) if "deposito" in cambios else float(cierre.deposito or 0),
        "devolucion_monto": float(cambios["devolucion_monto"]) if "devolucion_monto" in cambios else float(cierre.devolucion_monto or 0),
        "devolucion_tipo": cambios["devolucion_tipo"] if "devolucion_tipo" in cambios else (cierre.devolucion_tipo or ""),
        "devolucion_afecta": cambios["devolucion_afecta"] if "devolucion_afecta" in cambios else (cierre.devolucion_afecta or ""),
    }

    hay_montos = any(
        campo in cambios
        for campo in (
            "efectivo",
            "pos",
            "yape",
            "transferencia",
            "deposito",
            "devolucion_monto",
            "devolucion_tipo",
            "devolucion_afecta",
            "total_neto",
        )
    )
    if hay_montos:
        tipo = montos["devolucion_tipo"] or ""
        afecta = montos["devolucion_afecta"] or ""
        dev = montos["devolucion_monto"]
        if "otra caja" in tipo.lower() and dev > 0 and afecta.strip().lower() not in ("efectivo", "pos"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Seleccione a qué medio afecta la devolución (Efectivo o POS).",
            )
        efectivo_final, pos_final, total_neto = calcular_total_neto(
            efectivo=montos["efectivo"],
            pos=montos["pos"],
            yape=montos["yape"],
            transferencia=montos["transferencia"],
            deposito=montos["deposito"],
            devolucion_monto=dev,
            devolucion_tipo=tipo,
            devolucion_afecta=afecta,
        )
        cierre.efectivo = efectivo_final
        cierre.pos = pos_final
        cierre.yape = montos["yape"]
        cierre.transferencia = montos["transferencia"]
        cierre.deposito = montos["deposito"]
        cierre.devolucion_monto = dev
        cierre.devolucion_tipo = tipo or None
        cierre.devolucion_afecta = afecta or None
        cierre.total_neto = total_neto

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo actualizar el cierre: {exc}",
        ) from exc
    db.refresh(cierre)
    return cierre

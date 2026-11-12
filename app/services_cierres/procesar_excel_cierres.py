"""
Resume el Excel de Cierre de Caja de Imagina (en RAM),
con la misma lógica del sistema de escritorio.
No escribe archivos ni toca la tabla cierres_caja.
"""

from __future__ import annotations

import io
from typing import Any, Optional, Union

import pandas as pd


def clasificar_pago(raw: Any) -> str:
    if isinstance(raw, pd.Series):
        raw = raw.iloc[0] if not raw.empty else None
    if raw is None or (not isinstance(raw, str) and pd.isna(raw)):
        return ""
    texto = str(raw).strip().lower()
    if "yape" in texto:
        return "YAPE"
    if "transferencia" in texto:
        return "TRANSFERENCIA"
    if "pos" in texto or "ticket pos" in texto:
        return "POS"
    if "depósito" in texto or "deposito" in texto:
        return "DEPOSITO"
    if "efectivo" in texto:
        return "EFECTIVO"
    return ""


def _to_float(valor: Any) -> float:
    try:
        if valor is None or pd.isna(valor):
            return 0.0
        return round(float(valor), 2)
    except (TypeError, ValueError):
        return 0.0


def _encontrar_header(df_preview: pd.DataFrame) -> Optional[int]:
    for indice, fila in df_preview.iterrows():
        celdas = [str(x).strip().lower() for x in fila.fillna("")]
        tiene_usuario = any(
            "usuario" in x or "user" in x or "cajero" in x or "vendedor" in x
            for x in celdas
        )
        tiene_total = any(
            x == "total" or "monto" in x or "importe" in x or "valor" in x
            for x in celdas
        )
        if tiene_usuario and tiene_total:
            return int(indice)
    return None


def _resolver_columnas(df: pd.DataFrame) -> dict[str, Optional[str]]:
    user_col = total_col = tipo_col = detalle_col = cuenta_col = None
    for columna in df.columns:
        nombre = str(columna).strip().lower()
        if user_col is None and (
            "usuario" in nombre
            or "user" in nombre
            or "vendedor" in nombre
            or "cajero" in nombre
        ):
            user_col = columna
        if total_col is None and (
            nombre == "total" or "monto" in nombre or "importe" in nombre or "valor" in nombre
        ):
            total_col = columna
        if tipo_col is None and (
            nombre == "tipo doc. pago"
            or ("tipo" in nombre and "pag" in nombre)
            or "medio de pago" in nombre
            or "payment" in nombre
        ):
            tipo_col = columna
        if detalle_col is None and (
            "detalle" in nombre or "observ" in nombre or "desc" in nombre
        ):
            detalle_col = columna
        if cuenta_col is None and nombre == "cuenta":
            cuenta_col = columna
    return {
        "usuario": user_col,
        "total": total_col,
        "tipo": tipo_col,
        "detalle": detalle_col,
        "cuenta": cuenta_col,
    }


def _area_frecuente(serie: pd.Series) -> Optional[str]:
    valores = (
        serie.dropna()
        .astype(str)
        .map(lambda item: item.strip())
        .replace("", pd.NA)
        .dropna()
    )
    if valores.empty:
        return None
    cajas = valores[valores.str.lower().str.contains("caja")]
    fuente = cajas if not cajas.empty else valores
    return str(fuente.mode().iloc[0])[:100]


def excel_bytes_a_cajeros(
    contenido: Union[bytes, io.BytesIO],
) -> list[dict[str, Any]]:
    buffer = contenido if isinstance(contenido, io.BytesIO) else io.BytesIO(contenido)
    buffer.seek(0)
    preview = pd.read_excel(buffer, header=None, nrows=40, dtype=str)
    header_row = _encontrar_header(preview)

    buffer.seek(0)
    if header_row is None:
        df = pd.read_excel(buffer)
    else:
        df = pd.read_excel(buffer, header=header_row)
    df.columns = [str(columna).strip() for columna in df.columns]

    columnas = _resolver_columnas(df)
    if columnas["usuario"] is None or columnas["total"] is None:
        raise ValueError(
            "El Excel de cierre debe tener columnas de usuario/cajero y total/importe."
        )

    df = df.rename(
        columns={
            columnas["usuario"]: "Usuario",
            columnas["total"]: "Total",
        }
    )
    if columnas["tipo"]:
        df = df.rename(columns={columnas["tipo"]: "Tipo doc. pago"})
    elif "Tipo doc. pago" not in df.columns:
        df["Tipo doc. pago"] = ""
    if columnas["detalle"]:
        df = df.rename(columns={columnas["detalle"]: "Detalle"})
    elif "Detalle" not in df.columns:
        df["Detalle"] = ""
    if columnas["cuenta"]:
        df = df.rename(columns={columnas["cuenta"]: "Cuenta"})
    elif "Cuenta" not in df.columns:
        df["Cuenta"] = ""

    df["Usuario"] = df["Usuario"].astype(str).str.strip().replace({"nan": "", "None": ""})
    df = df[df["Usuario"] != ""].copy()
    df["Total"] = pd.to_numeric(df["Total"], errors="coerce").fillna(0.0)
    df["es_devolucion"] = df["Detalle"].astype(str).str.lower().str.contains("devolu")
    df["tipo_clasificado"] = df["Tipo doc. pago"].apply(clasificar_pago)

    ventas = df[~df["es_devolucion"]].copy()
    devol = df[df["es_devolucion"]].copy()
    usuarios = sorted(
        pd.concat([ventas["Usuario"], devol["Usuario"]]).dropna().unique()
    )

    cajeros: list[dict[str, Any]] = []
    for usuario in usuarios:
        ventas_u = ventas[ventas["Usuario"] == usuario]
        devol_u = devol[devol["Usuario"] == usuario]
        efectivo = _to_float(ventas_u[ventas_u["tipo_clasificado"] == "EFECTIVO"]["Total"].sum())
        pos = _to_float(ventas_u[ventas_u["tipo_clasificado"] == "POS"]["Total"].sum())
        yape = _to_float(ventas_u[ventas_u["tipo_clasificado"] == "YAPE"]["Total"].sum())
        transferencia = _to_float(
            ventas_u[ventas_u["tipo_clasificado"] == "TRANSFERENCIA"]["Total"].sum()
        )
        deposito = _to_float(ventas_u[ventas_u["tipo_clasificado"] == "DEPOSITO"]["Total"].sum())
        devolucion_monto = _to_float(devol_u["Total"].sum())
        total_neto = round(
            efectivo + pos + yape + transferencia + deposito - devolucion_monto, 2
        )
        area = _area_frecuente(
            pd.concat(
                [
                    ventas_u["Cuenta"] if "Cuenta" in ventas_u.columns else pd.Series(dtype=str),
                    devol_u["Cuenta"] if "Cuenta" in devol_u.columns else pd.Series(dtype=str),
                ]
            )
        )
        cajeros.append(
            {
                "nombre": usuario,
                "area": area,
                "efectivo": efectivo,
                "pos": pos,
                "yape": yape,
                "transferencia": transferencia,
                "deposito": deposito,
                "devolucion_monto": devolucion_monto,
                "total_neto": total_neto,
            }
        )
    return cajeros

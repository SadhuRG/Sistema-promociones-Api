"""
Extrae el Excel de Cierre de Caja desde Imagina (solo RAM) y lo resume.
No modifica download_cierres.py ni escribe en disco.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

import requests
import urllib3

from app.core.config import settings
from app.services_cierres.download_cierres import _login, _preparar_reporte
from app.services_cierres.procesar_excel_cierres import excel_bytes_a_cajeros

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_EXTRACT_LOCK = threading.Lock()
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 15; Pixel 9) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Mobile Safari/537.36"
)


def iso_a_ddmmyyyy(valor: str) -> str:
    texto = str(valor or "").strip()
    if not texto:
        raise ValueError("La fecha es obligatoria")
    if "/" in texto:
        datetime.strptime(texto, "%d/%m/%Y")
        return texto
    return datetime.strptime(texto[:10], "%Y-%m-%d").strftime("%d/%m/%Y")


def calcular_total_neto(
    efectivo: float,
    pos: float,
    yape: float,
    transferencia: float,
    deposito: float,
    devolucion_monto: float,
    devolucion_tipo: str,
    devolucion_afecta: str,
) -> tuple[float, float, float]:
    """
    Réplica del escritorio:
    - 'Es de mi caja' no resta.
    - 'Otra caja' resta del medio (Efectivo/POS) si hay monto.
    Devuelve (efectivo_final, pos_final, total_neto).
    """
    tipo = str(devolucion_tipo or "").strip().lower()
    afecta = str(devolucion_afecta or "").strip().lower()
    dev = round(float(devolucion_monto or 0), 2)
    ef = round(float(efectivo or 0), 2)
    pos_v = round(float(pos or 0), 2)
    es_otra = "otra caja" in tipo
    if es_otra and dev > 0:
        if afecta == "efectivo":
            ef = round(ef - dev, 2)
        elif afecta == "pos":
            pos_v = round(pos_v - dev, 2)
    total = round(
        ef
        + pos_v
        + round(float(yape or 0), 2)
        + round(float(transferencia or 0), 2)
        + round(float(deposito or 0), 2),
        2,
    )
    return ef, pos_v, total


def extraer_cajeros_imagina(
    fecha_inicio: str,
    fecha_fin: str,
    empresa_id: int = 2,
) -> dict[str, Any]:
    inicio = iso_a_ddmmyyyy(fecha_inicio)
    fin = iso_a_ddmmyyyy(fecha_fin)
    inicio_iso = datetime.strptime(inicio, "%d/%m/%Y").date()
    fin_iso = datetime.strptime(fin, "%d/%m/%Y").date()
    if fin_iso < inicio_iso:
        raise ValueError("fecha_fin debe ser posterior o igual a fecha_inicio")

    url = settings.IMAGINA_CIERRE_EXCEL_URL
    if not url:
        raise RuntimeError("IMAGINA_CIERRE_EXCEL_URL no está configurada")

    adquirido = _EXTRACT_LOCK.acquire(blocking=False)
    if not adquirido:
        raise RuntimeError("Ya se está extrayendo un cierre de caja")

    session = requests.Session()
    try:
        sid = _login(session)
        if not sid:
            raise RuntimeError("No se pudo iniciar sesión en Imagina")

        if not _preparar_reporte(session, sid, inicio, fin, empresa_id):
            raise RuntimeError("No se pudo preparar el reporte de cierre en Imagina")

        response = session.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
            },
            verify=False,
            allow_redirects=True,
            timeout=120,
        )
        if response.status_code != 200 or not response.content:
            raise RuntimeError("Falló la descarga del Excel de cierre")
        if not response.content.startswith(b"PK"):
            raise RuntimeError("Imagina no devolvió un Excel válido de cierre")

        cajeros = excel_bytes_a_cajeros(response.content)
        return {
            "fecha_inicio": inicio_iso.isoformat(),
            "fecha_fin": fin_iso.isoformat(),
            "cajeros": cajeros,
            "total_cajeros": len(cajeros),
        }
    finally:
        session.close()
        _EXTRACT_LOCK.release()

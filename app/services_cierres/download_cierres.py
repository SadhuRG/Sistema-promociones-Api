"""
Script de prueba: descarga el Excel de Cierre de Caja desde Imagina.

Flujo (igual que horarios):
  1) login (cookies + param_sid)
  2) POST Itec preparar reporte (obtenerReporteCierreCajaExcel)
  3) GET del .xlsx generado
  4) guardar en disco

Ejecutar desde la raíz del proyecto (con venv activo):
  python -m app.services_cierres.download_cierres

Guarda: app/services_cierres/reporte_prueba_cierre.xlsx
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import requests
import urllib3

from app.core.config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OUTPUT_FILE = Path(__file__).resolve().parent / "reporte_prueba_cierre.xlsx"

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 15; Pixel 9) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Mobile Safari/537.36"
)


def _login(session: requests.Session) -> str | None:
    """Login Imagina; retorna param_sid (cookie imaginatecperu_sgiroma_sid)."""
    if not settings.IMAGINA_USUARIO or not settings.IMAGINA_PASSWORD:
        print("[ERROR] Faltan IMAGINA_USUARIO / IMAGINA_PASSWORD en el .env")
        return None

    headers = {
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
    }
    url_login = settings.IMAGINA_URL_LOGIN

    session.get(url_login, headers=headers, verify=False, timeout=30)

    response = session.post(
        url_login,
        data={
            "username": settings.IMAGINA_USUARIO,
            "password": settings.IMAGINA_PASSWORD,
        },
        headers={
            **headers,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": url_login,
        },
        verify=False,
        allow_redirects=False,
        timeout=30,
    )

    location = response.headers.get("Location", "") or ""
    if "error=" in location.lower():
        print(f"[ERROR] Login rechazado (Location={location!r})")
        return None

    if response.status_code in (301, 302, 303, 307, 308) and location:
        next_url = (
            location
            if location.startswith("http")
            else f"https://intranet.romavitalsalud.com/{location.lstrip('/')}"
        )
        session.get(
            next_url, headers=headers, verify=False, allow_redirects=True, timeout=30
        )

    sid = session.cookies.get("imaginatecperu_sgiroma_sid")
    if not sid:
        print(
            f"[ERROR] Sin cookie SID. Cookies={list(session.cookies.keys())} "
            f"HTTP={response.status_code}"
        )
        return None

    print(f"[OK] Sesión activa. SID={sid[:8]}...")
    return sid


def _preparar_reporte(
    session: requests.Session,
    sid: str,
    fecha_emision: str,
    fecha_emision_fin: str,
    empresa_id: int,
) -> bool:
    """POST a Itec: genera el Excel en el servidor Imagina."""
    payload = {
        "param_opcion_id": "213",
        "action_name": "obtenerReporteCierreCajaExcel",
        "criterios[0][actividad]": "",
        "criterios[0][actividadTipo]": "",
        "criterios[0][fechaEmision]": fecha_emision,
        "criterios[0][fechaEmisionFin]": fecha_emision_fin,
        "criterios[0][cuenta]": "",
        "criterios[0][cajaID]": "",
        "criterios[0][empresaId]": str(empresa_id),
        "param_sid": sid,
    }
    headers = {
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    response = session.post(
        settings.IMAGINA_ITEC_URL,
        data=payload,
        headers=headers,
        verify=False,
        timeout=120,
    )

    if response.status_code != 200:
        print(f"[ERROR] Preparar reporte falló. status_code={response.status_code}")
        print(f"[ERROR] Body (preview): {response.text[:300]!r}")
        return False

    try:
        data = response.json()
    except Exception:
        print(f"[ERROR] Respuesta no JSON al preparar: {response.text[:300]!r}")
        return False

    status = str(data.get("status", "")).lower()
    if status != "ok":
        print(
            f"[ERROR] Imagina status={data.get('status')!r} "
            f"message={data.get('message')!r}"
        )
        return False

    print(f"[OK] Reporte preparado ({fecha_emision} -> {fecha_emision_fin}).")
    return True


def descargar_reporte_cierre(
    fecha_emision: str | None = None,
    fecha_emision_fin: str | None = None,
    empresa_id: int = 2,
) -> bool:
    """
    login -> preparar POST -> GET Excel -> guardar reporte_prueba_cierre.xlsx.
    Fechas DD/MM/YYYY; por defecto hoy.
    """
    hoy = date.today().strftime("%d/%m/%Y")
    fecha_emision = fecha_emision or hoy
    fecha_emision_fin = fecha_emision_fin or hoy
    excel_url = settings.IMAGINA_CIERRE_EXCEL_URL

    if not excel_url:
        print("[ERROR] Falta IMAGINA_CIERRE_EXCEL_URL en config/.env")
        return False

    session = requests.Session()
    try:
        sid = _login(session)
        if not sid:
            return False

        print(
            f"[INFO] Preparando cierre {fecha_emision} -> {fecha_emision_fin} "
            f"(empresaId={empresa_id})..."
        )
        if not _preparar_reporte(
            session, sid, fecha_emision, fecha_emision_fin, empresa_id
        ):
            return False

        headers = {
            "User-Agent": USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
        }
        response = session.get(
            excel_url,
            headers=headers,
            verify=False,
            allow_redirects=True,
            timeout=120,
        )

        if response.status_code != 200:
            print(f"[ERROR] Descarga fallida. status_code={response.status_code}")
            print(f"[ERROR] Body (preview): {response.text[:300]!r}")
            return False

        if not response.content:
            print("[ERROR] Respuesta vacía al descargar Excel.")
            return False

        content_type = (response.headers.get("Content-Type") or "").lower()
        # Firma ZIP/XLSX = PK
        if not response.content.startswith(b"PK"):
            print(
                f"[ERROR] No parece un .xlsx "
                f"(Content-Type={content_type!r}). Preview: {response.content[:120]!r}"
            )
            return False

        OUTPUT_FILE.write_bytes(response.content)
        print(
            f"[OK] Descarga exitosa. status_code={response.status_code} "
            f"bytes={len(response.content)} -> {OUTPUT_FILE}"
        )
        return True

    except Exception as exc:
        print(f"[ERROR] Excepción al descargar cierre: {exc}")
        return False
    finally:
        session.close()


if __name__ == "__main__":
    ok = descargar_reporte_cierre()
    raise SystemExit(0 if ok else 1)

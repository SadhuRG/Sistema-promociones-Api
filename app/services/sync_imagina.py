import calendar
import io
from datetime import date
from typing import Any, Optional

import requests
import urllib3

from app.core.config import settings
from app.services.limpieza_horarios import excel_bytes_a_registros

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _normalizar_etag(etag: Optional[str]) -> Optional[str]:
    """
    Comparación débil RFC 7232: W/"abc" y "abc" son equivalentes.
    Imagina suele devolver W/"..." en HEAD y "..." en GET.
    """
    if etag is None:
        return None
    valor = etag.strip()
    if valor.startswith("W/"):
        valor = valor[2:].strip()
    if len(valor) >= 2 and valor[0] == '"' and valor[-1] == '"':
        valor = valor[1:-1]
    return valor or None


class ImaginaSyncService:
    """
    Solo descarga el Excel de Imagina (RAM).
    Flujo: login -> preparar_reporte(fechas) -> HEAD/ETag -> GET bytes -> limpieza.
    """

    def __init__(
        self,
        url_login: Optional[str] = None,
        url_itec: Optional[str] = None,
        usuario: Optional[str] = None,
        password: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.url_login = url_login or settings.IMAGINA_URL_LOGIN
        self.url_itec = url_itec or settings.IMAGINA_ITEC_URL
        self.usuario = usuario or settings.IMAGINA_USUARIO
        self.password = password or settings.IMAGINA_PASSWORD
        self.headers = headers or {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 15; Pixel 9) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Mobile Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
        }
        self.session = requests.Session()
        self._last_etag: Optional[str] = None
        self._last_modified: Optional[str] = None
        self._sid: Optional[str] = None

    @property
    def last_etag(self) -> Optional[str]:
        return self._last_etag

    @property
    def last_modified(self) -> Optional[str]:
        return self._last_modified

    def cargar_estado_etag(
        self,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
    ) -> None:
        """Restaura el último ETag conocido (caché en memoria de proceso)."""
        self._last_etag = etag
        self._last_modified = last_modified

    def login(self) -> bool:
        """Login silencioso; conserva cookies y extrae param_sid Imagina."""
        if not self.usuario or not self.password:
            print("[ERROR] Faltan IMAGINA_USUARIO / IMAGINA_PASSWORD en el .env")
            return False

        try:
            self.session.get(self.url_login, headers=self.headers, verify=False, timeout=30)

            response = self.session.post(
                self.url_login,
                data={"username": self.usuario, "password": self.password},
                headers={
                    **self.headers,
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Referer": self.url_login,
                },
                verify=False,
                allow_redirects=False,
                timeout=30,
            )

            location = response.headers.get("Location", "") or ""
            if "error=" in location.lower() or "error=" in str(response.url).lower():
                print(f"[ERROR] Login rechazado por Imagina (Location={location!r}).")
                print("[ERROR] Revisa IMAGINA_USUARIO / IMAGINA_PASSWORD en el .env")
                return False

            if response.status_code in (301, 302, 303, 307, 308) and location:
                next_url = (
                    location
                    if location.startswith("http")
                    else f"https://intranet.romavitalsalud.com/{location.lstrip('/')}"
                )
                self.session.get(
                    next_url, headers=self.headers, verify=False, allow_redirects=True, timeout=30
                )

            self._sid = self.session.cookies.get("imaginatecperu_sgiroma_sid")
            cookies = list(self.session.cookies.keys())

            if not self._sid:
                print(
                    f"[ERROR] Login sin cookie imaginatecperu_sgiroma_sid. "
                    f"Cookies={cookies} HTTP={response.status_code} Location={location!r}"
                )
                return False

            print(f"[OK] Sesion activa. Cookies: {cookies}")
            print(f"[OK] param_sid listo ({self._sid[:8]}...).")
            return True
        except Exception as exc:
            print(f"[ERROR] Fallo el login: {exc}")
            return False

    def preparar_reporte(self, fecha_inicio: str, fecha_fin: str) -> bool:
        """POST de preparación. Fechas DD/MM/YYYY. True si status == 'ok'."""
        if not self._sid:
            print("[ERROR] preparar_reporte: no hay param_sid (haz login primero).")
            return False

        payload = {
            "param_opcion_id": "358",
            "action_name": "obtenerReporteHorarioPorConsultExcel",
            "criterios[0][medico]": "",
            "criterios[0][consultorio]": "",
            "criterios[0][especialidad]": "",
            "criterios[0][fechaInicio]": fecha_inicio,
            "criterios[0][fechaFin]": fecha_fin,
            "param_sid": self._sid,
        }

        try:
            response = self.session.post(
                self.url_itec,
                data=payload,
                headers={
                    **self.headers,
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                },
                verify=False,
                timeout=60,
            )
            if response.status_code != 200:
                print(f"[ERROR] preparar_reporte HTTP {response.status_code}: {response.text[:200]}")
                return False

            data = response.json()
            if str(data.get("status", "")).lower() == "ok":
                print(f"[OK] Reporte preparado ({fecha_inicio} -> {fecha_fin}).")
                return True

            print(f"[ERROR] preparar_reporte status != ok: {data}")
            return False
        except Exception as exc:
            print(f"[ERROR] preparar_reporte: {exc}")
            return False

    def verificar_cambios(self, url: str) -> dict[str, Any]:
        """HEAD al Excel; compara ETag / Last-Modified."""
        resultado: dict[str, Any] = {
            "hay_cambios": True,
            "etag": None,
            "last_modified": None,
            "status_code": None,
            "error": None,
        }

        try:
            response = self.session.head(
                url,
                headers=self.headers,
                verify=False,
                allow_redirects=True,
                timeout=30,
            )
            resultado["status_code"] = response.status_code

            etag = response.headers.get("ETag") or response.headers.get("etag")
            last_modified = (
                response.headers.get("Last-Modified")
                or response.headers.get("last-modified")
            )
            resultado["etag"] = etag
            resultado["last_modified"] = last_modified

            etag_actual = _normalizar_etag(etag)
            etag_previo = _normalizar_etag(self._last_etag)
            mismo_etag = (
                etag_previo is not None
                and etag_actual is not None
                and etag_previo == etag_actual
            )
            mismo_lm = (
                self._last_modified is not None
                and last_modified is not None
                and self._last_modified == last_modified
            )

            if mismo_etag or (etag_actual is None and mismo_lm):
                resultado["hay_cambios"] = False
                print("[INFO] Sin cambios detectados (ETag/Last-Modified iguales).")
            else:
                resultado["hay_cambios"] = True
                print(
                    f"[INFO] Cambios detectados o primera lectura. "
                    f"ETag={etag!r} Last-Modified={last_modified!r}"
                )
            return resultado
        except Exception as exc:
            resultado["error"] = str(exc)
            print(f"[ERROR] verificar_cambios: {exc}")
            return resultado

    def descargar_excel(self, url: str) -> Optional[list[dict[str, Any]]]:
        """
        GET del Excel -> BytesIO en RAM -> limpieza (modulo aparte) -> list[dict].
        Cero archivos en disco.
        """
        try:
            response = self.session.get(
                url,
                headers=self.headers,
                verify=False,
                allow_redirects=True,
                timeout=60,
            )
            if response.status_code != 200:
                print(f"[ERROR] Descarga HTTP {response.status_code}")
                return None

            if not response.content:
                print("[ERROR] Respuesta vacia.")
                return None

            self._last_etag = response.headers.get("ETag") or response.headers.get("etag")
            self._last_modified = (
                response.headers.get("Last-Modified")
                or response.headers.get("last-modified")
            )

            buffer = io.BytesIO(response.content)
            registros = excel_bytes_a_registros(buffer)
            # Liberar bytes crudos cuanto antes
            del buffer
            del response

            print(f"[OK] Registros limpios en memoria: {len(registros)}")
            if registros:
                print(f"[OK] Columnas: {list(registros[0].keys())}")
            return registros
        except Exception as exc:
            print(f"[ERROR] descargar_excel: {exc}")
            return None

    def sincronizar_si_hay_cambios(
        self,
        url: str,
        fecha_inicio: str,
        fecha_fin: str,
        forzar: bool = False,
    ) -> Optional[list[dict[str, Any]]]:
        """login -> preparar_reporte -> verificar_cambios -> descargar_excel."""
        if not self.login():
            return None

        if not self.preparar_reporte(fecha_inicio, fecha_fin):
            print("[FAIL] No se pudo preparar el reporte; se aborta la sync.")
            return None

        meta = self.verificar_cambios(url)
        if meta.get("error"):
            print("[ADVERTENCIA] HEAD fallo; se intenta descarga de todas formas.")
            forzar = True

        if not forzar and not meta.get("hay_cambios", True):
            print("[INFO] Se omite descarga.")
            return None

        return self.descargar_excel(url)


def _rango_dos_meses() -> tuple[str, str]:
    """Primer dia del mes actual y ultimo dia del siguiente mes (DD/MM/YYYY)."""
    hoy = date.today()
    inicio = date(hoy.year, hoy.month, 1)
    if hoy.month == 12:
        siguiente_mes, siguiente_anio = 1, hoy.year + 1
    else:
        siguiente_mes, siguiente_anio = hoy.month + 1, hoy.year
    ultimo = calendar.monthrange(siguiente_anio, siguiente_mes)[1]
    fin = date(siguiente_anio, siguiente_mes, ultimo)
    return inicio.strftime("%d/%m/%Y"), fin.strftime("%d/%m/%Y")


def _prueba_terminal() -> None:
    """Ejecutar: python -m app.services.sync_imagina"""
    url = settings.IMAGINA_EXCEL_URL
    fecha_inicio, fecha_fin = _rango_dos_meses()

    print("=== Prueba ImaginaSyncService + limpieza ===")
    print(f"Usuario : {settings.IMAGINA_USUARIO or '(vacio)'}")
    print(f"Rango   : {fecha_inicio} -> {fecha_fin}")

    if not url:
        print("[FAIL] Define IMAGINA_EXCEL_URL en el .env")
        return

    service = ImaginaSyncService()
    datos = service.sincronizar_si_hay_cambios(
        url=url,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        forzar=True,
    )

    if datos is None:
        print("[FAIL] No se obtuvieron datos.")
        return

    print(f"[OK] Primer registro: {datos[0]}")
    print(f"[OK] Total registros: {len(datos)}")


if __name__ == "__main__":
    _prueba_terminal()

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.purgar_promociones import (
    aplicar_cambio_estado,
    extract_promocion_storage_path,
    promo_lista_para_purgar,
)

AHORA = datetime(2026, 11, 21, 14, 0, tzinfo=timezone.utc)


def test_activo_nunca_se_purga_aunque_tenga_fecha_vieja():
    viejo = AHORA - timedelta(days=400)
    assert promo_lista_para_purgar("Activo", viejo, AHORA) is False
    assert promo_lista_para_purgar("Activo", None, AHORA) is False


def test_inactivo_sin_fecha_no_se_purga():
    assert promo_lista_para_purgar("Inactivo", None, AHORA) is False


def test_inactivo_de_hoy_no_se_purga():
    assert promo_lista_para_purgar("Inactivo", AHORA, AHORA) is False


def test_inactivo_de_29_dias_no_se_purga():
    marca = AHORA - timedelta(days=29)
    assert promo_lista_para_purgar("Inactivo", marca, AHORA) is False


def test_inactivo_de_30_dias_si_se_purga():
    marca = AHORA - timedelta(days=30)
    assert promo_lista_para_purgar("Inactivo", marca, AHORA) is True


def test_inactivo_de_31_dias_si_se_purga():
    marca = AHORA - timedelta(days=31)
    assert promo_lista_para_purgar("Inactivo", marca, AHORA) is True


def test_extract_path_desde_url_publica():
    url = (
        "https://fbrqboyduretxmxcbhqp.supabase.co/storage/v1/object/public/"
        "flayers/promociones/abc123.webp"
    )
    assert extract_promocion_storage_path(url, "flayers") == "promociones/abc123.webp"


def test_extract_path_ignora_informes():
    url = (
        "https://ejemplo.supabase.co/storage/v1/object/public/"
        "flayers/informes/reporte.webp"
    )
    assert extract_promocion_storage_path(url, "flayers") == ""


def test_extract_path_vacio():
    assert extract_promocion_storage_path(None) == ""
    assert extract_promocion_storage_path("   ") == ""


def test_inactivar_marca_fecha_y_reactivar_la_limpia():
    promo = SimpleNamespace(estado="Activo", inactivado_at=None)
    aplicar_cambio_estado(promo, "Inactivo", AHORA)
    assert promo.estado == "Inactivo"
    assert promo.inactivado_at == AHORA

    aplicar_cambio_estado(promo, "Activo", AHORA + timedelta(days=2))
    assert promo.estado == "Activo"
    assert promo.inactivado_at is None


def test_volver_a_poner_inactivo_no_reinicia_el_reloj():
    original = AHORA - timedelta(days=10)
    promo = SimpleNamespace(estado="Inactivo", inactivado_at=original)
    aplicar_cambio_estado(promo, "Inactivo", AHORA)
    assert promo.inactivado_at == original

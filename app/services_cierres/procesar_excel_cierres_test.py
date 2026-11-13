from app.services_cierres.procesar_excel_cierres import clasificar_pago


def test_solo_efectivo_exacto_cuenta_como_caja():
    assert clasificar_pago("Efectivo") == "EFECTIVO"
    assert clasificar_pago("  Efectivo  ") == "EFECTIVO"
    assert clasificar_pago("Pago en Efectivo") == ""
    assert clasificar_pago("Pago en efectivo") == ""
    assert clasificar_pago("Yape") == "YAPE"
    assert clasificar_pago("Ticket POS") == "POS"

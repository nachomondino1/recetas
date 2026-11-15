"""Bitácora de actualizaciones: se escribe sola, se lee y avisa cuando hace mucho."""

import datetime

import refresh_log

D = datetime.date


def test_registrar_crea_el_log_con_encabezado_y_agrega_filas(tmp_path):
    ruta = tmp_path / "refresh_log.md"
    refresh_log.registrar("Google Doc", "2011 párrafos", fecha=D(2026, 11, 15), ruta=ruta)
    refresh_log.registrar("Google Doc", "sin cambios", fecha=D(2026, 11, 20), ruta=ruta)
    assert ruta.read_text(encoding="utf-8").startswith("# Bitácora")
    assert [f[0] for f in refresh_log.leer(ruta)] == [D(2026, 11, 15), D(2026, 11, 20)]


def test_ultima_por_fuente_y_estado_dice_hace_cuanto(tmp_path):
    ruta = tmp_path / "log.md"
    refresh_log.registrar("Google Doc", "a", fecha=D(2026, 11, 1), ruta=ruta)
    refresh_log.registrar("Google Doc", "b", fecha=D(2026, 11, 15), ruta=ruta)
    refresh_log.registrar("Curado", "c", fecha=D(2026, 11, 10), ruta=ruta)
    ult = refresh_log.ultima_por_fuente(refresh_log.leer(ruta))
    assert ult["Google Doc"] == (D(2026, 11, 15), "b")
    out = "\n".join(refresh_log.estado(hoy=D(2026, 11, 15), ruta=ruta))
    assert "Google Doc: última vez 2026-11-15 (hoy)" in out and "Curado" in out


def test_avisa_si_el_doc_lleva_mas_de_14_dias(tmp_path):
    ruta = tmp_path / "log.md"
    refresh_log.registrar("Google Doc", "x", fecha=D(2026, 10, 1), ruta=ruta)
    assert "⚠" in "\n".join(refresh_log.estado(hoy=D(2026, 11, 15), ruta=ruta))


def test_sin_registros_no_revienta(tmp_path):
    assert "Sin registros" in refresh_log.estado(ruta=tmp_path / "nada.md")[0]


def test_el_detalle_no_rompe_la_tabla(tmp_path):
    ruta = tmp_path / "log.md"
    refresh_log.registrar("Google Doc", "a | b\nc", fecha=D(2026, 11, 15), ruta=ruta)
    assert refresh_log.leer(ruta)[0][2] == "a / b c"

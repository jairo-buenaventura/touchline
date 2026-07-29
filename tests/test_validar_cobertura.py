"""Tests de validar_cobertura.py — alias de nombres y parseo de data/."""
import validar_cobertura as vc


def test_canon_resuelve_alias_conocidos():
    assert vc.canon("Spurs") == "Tottenham"
    assert vc.canon("Man City") == "Manchester City"
    assert vc.canon("Man Utd") == "Manchester United"
    assert vc.canon("Nott'm Forest") == "Nottingham Forest"
    assert vc.canon("1. FC Köln") == "FC Koln"


def test_canon_es_identidad_para_nombre_no_mapeado():
    assert vc.canon("Arsenal") == "Arsenal"


def test_archivos_data_liga_encuentra_partidos_reales():
    existentes = vc.archivos_data_liga("Premier League", "2025_2026")
    assert len(existentes) >= 300, "se esperaba casi una temporada completa (380 partidos)"
    # el propio dataset usa "Man City" y "Manchester City" para el mismo equipo:
    # el alias debe hacer que ambos canonicalicen igual y no se dupliquen ids.
    claves_con_city = [k for k in existentes if "Manchester City" in k]
    assert claves_con_city, "no se encontro ningun partido de Manchester City canonicalizado"

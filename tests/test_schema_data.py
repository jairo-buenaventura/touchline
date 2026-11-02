"""Validaciones de solo lectura sobre data/. No modifica ningun archivo."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ARCHIVOS_NO_PARTIDO = {"jugadores.json", "lista.json", "perfiles_jugadores.json"}

CAMPOS_RAIZ_ESPERADOS = {"marcador", "estadio", "competicion", "temporada", "home", "away"}
CAMPOS_LADO_ESPERADOS = {
    "equipo", "jugadores", "pases", "estadisticas", "tiros",
    "acciones", "recepcion_pases", "alineacion", "fotmob",
}


CARPETAS_NO_PARTIDO = {"corners", "leaders"}


def listar_archivos_partido():
    """
    Los partidos viven en subcarpetas data/<Liga>/<Temporada>/*.json desde
    la reorganizacion por liga/temporada -- ya no estan sueltos en data/.
    Devuelve rutas relativas a DATA_DIR (ej. "LaLiga/2026-2027/X.json"),
    compatibles con DATA_DIR / nombre tal como lo usa el resto del archivo.
    """
    archivos = []
    for p in DATA_DIR.rglob("*.json"):
        if p.name in ARCHIVOS_NO_PARTIDO:
            continue
        rel = p.relative_to(DATA_DIR)
        if rel.parts[0] in CARPETAS_NO_PARTIDO:
            continue
        archivos.append(str(rel))
    return archivos


def test_data_dir_existe_y_tiene_partidos():
    assert DATA_DIR.is_dir()
    archivos = listar_archivos_partido()
    assert len(archivos) > 1000, "se esperaban miles de partidos en data/"


def test_archivos_metadata_no_tienen_esquema_de_partido():
    """jugadores.json y lista.json existen pero NO son partidos (son listas, no dicts con home/away)."""
    for nombre in ARCHIVOS_NO_PARTIDO:
        ruta = DATA_DIR / nombre
        if not ruta.exists():
            continue
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
        assert not (isinstance(contenido, dict) and "home" in contenido and "away" in contenido)


def test_muestra_de_partidos_tiene_esquema_esperado():
    archivos = listar_archivos_partido()
    muestra = archivos[:30] + archivos[-30:]
    for nombre in muestra:
        d = json.loads((DATA_DIR / nombre).read_text(encoding="utf-8"))
        faltantes_raiz = CAMPOS_RAIZ_ESPERADOS - d.keys()
        assert not faltantes_raiz, f"{nombre} le faltan campos raiz: {faltantes_raiz}"
        for lado in ("home", "away"):
            faltantes_lado = CAMPOS_LADO_ESPERADOS - d[lado].keys()
            assert not faltantes_lado, f"{nombre}[{lado}] le faltan campos: {faltantes_lado}"


def test_competicion_y_temporada_no_vacios():
    archivos = listar_archivos_partido()
    muestra = archivos[::len(archivos) // 50] if len(archivos) > 50 else archivos
    for nombre in muestra:
        d = json.loads((DATA_DIR / nombre).read_text(encoding="utf-8"))
        assert d.get("competicion"), f"{nombre} sin competicion"
        assert d.get("temporada"), f"{nombre} sin temporada"

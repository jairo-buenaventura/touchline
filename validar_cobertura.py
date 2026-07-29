#!/usr/bin/env python3
"""Valida la cobertura real de data/ contra las fuentes de fixtures disponibles.

Solo lee data/ y los archivos de fixtures existentes (premier_league_fixtures.csv,
bundesliga_fixtures.csv, ligue1_fixtures.csv, calendario_completo_laliga.json).
No modifica ni toca ningún script de descarga/parseo existente.

Uso:
    python3 validar_cobertura.py

Genera reporte_cobertura.json con partidos faltantes y marcadores que no
coinciden entre la fuente de fixtures y lo que hay en data/.
"""
import csv
import json
import os
import re

DATA_DIR = "data"

# Alias de nombre de equipo -> nombre canónico. Verificado a mano comparando
# cada fuente de fixtures contra los nombres reales que aparecen en data/.
# Ojo: dentro de data/ mismo conviven variantes del mismo equipo (ej. "Man City"
# y "Manchester City" para el mismo Manchester City, "Man Utd" y "Manchester
# United" para el mismo United) — no son duplicados, es solo naming inconsistente
# entre scrapes, así que ambas variantes deben canonicalizar igual.
ALIAS = {
    "Spurs": "Tottenham",
    "Nott'm Forest": "Nottingham Forest",
    "Man City": "Manchester City",
    "Man Utd": "Manchester United",
    "1. FSV Mainz 05": "Mainz 05",
    "1. FC Köln": "FC Koln",
    "SV Werder Bremen": "Werder Bremen",
    "Bayer 04 Leverkusen": "Bayer Leverkusen",
    "1. FC Heidenheim 1846": "FC Heidenheim",
    "1. FC Union Berlin": "Union Berlin",
    "Borussia Mönchengladbach": "Borussia M.Gladbach",
    "FC Bayern München": "Bayern Munich",
    "VfL Wolfsburg": "Wolfsburg",
    "TSG Hoffenheim": "Hoffenheim",
    "Sport-Club Freiburg": "Freiburg",
    "FC St. Pauli": "St. Pauli",
    "FC Augsburg": "Augsburg",
    "OGC Nice": "Nice",
    "LOSC Lille": "Lille",
    "FC Lorient": "Lorient",
    "FC Nantes": "Nantes",
    "Stade Rennais FC": "Rennes",
    "Angers SCO": "Angers",
    "RC Strasbourg Alsace": "Strasbourg",
    "AS Monaco": "Monaco",
    "RC Lens": "Lens",
    "FC Metz": "Metz",
    "Olympique Lyonnais": "Lyon",
    "Toulouse FC": "Toulouse",
    "Stade Brestois 29": "Brest",
    "Havre Athletic Club": "Le Havre",
    "Olympique de Marseille": "Marseille",
    "AJ Auxerre": "Auxerre",
}

# Fuentes de fixtures disponibles hoy en el repo: liga (tal como aparece en los
# nombres de archivo de data/), temporada, tipo de fuente, ruta del archivo.
FUENTES = [
    ("Premier League", "2025_2026", "csv", "premier_league_fixtures.csv"),
    ("Bundesliga", "2025_2026", "csv", "bundesliga_fixtures.csv"),
    ("Ligue 1", "2025_2026", "csv", "ligue1_fixtures.csv"),
    ("LaLiga", "2025-2026", "calendario_json", "calendario_completo_laliga.json"),
]


def canon(nombre):
    return ALIAS.get(nombre, nombre)


def cargar_fixtures_csv(path):
    partidos = []
    with open(path) as f:
        for row in csv.reader(f):
            if len(row) < 5:
                continue
            _, fecha, home, away, marcador = row[:5]
            partidos.append(
                {"fecha": fecha, "home": home, "away": away, "marcador": marcador.replace(" ", "")}
            )
    return partidos


def cargar_fixtures_calendario_json(path):
    data = json.load(open(path))
    partidos = []
    for x in data:
        marcador = x["marcador"].replace(" ", "").replace(":", "-")
        partidos.append(
            {
                "fecha": x["fecha"],
                "home": x["home"],
                "away": x["away"],
                "marcador": marcador,
            }
        )
    return partidos


def archivos_data_liga(liga, temporada):
    """Devuelve {(home_canon, away_canon): (marcador, nombre_archivo)} para una liga/temporada."""
    patron = re.compile(
        r"^(.+?) (\d+)\s*-\s*(\d+) (.+?) - " + re.escape(liga) + r" " + re.escape(temporada) + r"\.json$"
    )
    resultado = {}
    for fn in os.listdir(DATA_DIR):
        m = patron.match(fn)
        if not m:
            continue
        home, gh, ga, away = m.groups()
        resultado[(canon(home), canon(away))] = (f"{gh}-{ga}", fn)
    return resultado


def validar():
    reporte = {"generado_por": "validar_cobertura.py", "ligas": []}
    total_faltantes = 0

    for liga, temporada, tipo, path in FUENTES:
        if not os.path.exists(path):
            print(f"[SKIP] {liga}: no se encontró la fuente {path}")
            continue

        fixtures = (
            cargar_fixtures_csv(path) if tipo == "csv" else cargar_fixtures_calendario_json(path)
        )
        existentes = archivos_data_liga(liga, temporada)

        faltantes = []
        marcador_distinto = []
        for p in fixtures:
            key = (canon(p["home"]), canon(p["away"]))
            if key not in existentes:
                faltantes.append(p)
                continue
            marcador_real, archivo = existentes[key]
            if marcador_real != p["marcador"]:
                marcador_distinto.append(
                    {**p, "marcador_en_data": marcador_real, "archivo": archivo}
                )

        cobertura = 100 * (len(fixtures) - len(faltantes)) / len(fixtures) if fixtures else 0
        total_faltantes += len(faltantes)
        reporte["ligas"].append(
            {
                "liga": liga,
                "temporada": temporada,
                "total_fixtures": len(fixtures),
                "encontrados": len(fixtures) - len(faltantes),
                "cobertura_pct": round(cobertura, 1),
                "faltantes": faltantes,
                "marcador_distinto": marcador_distinto,
            }
        )
        print(
            f"{liga} {temporada}: {len(fixtures) - len(faltantes)}/{len(fixtures)} "
            f"({cobertura:.1f}%) — {len(faltantes)} faltantes, "
            f"{len(marcador_distinto)} con marcador distinto"
        )

    with open("reporte_cobertura.json", "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)
    print(f"\nReporte guardado en reporte_cobertura.json — {total_faltantes} partidos faltantes en total.")


if __name__ == "__main__":
    validar()

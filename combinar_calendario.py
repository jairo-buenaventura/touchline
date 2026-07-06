"""Combina los fixtures de todos los equipos en un calendario unico, sin duplicados."""

import json
from datetime import datetime
from pathlib import Path
from extraer_calendario import extraer_partidos


def parsear_fecha(fecha_str):
    return datetime.strptime(fecha_str, "%d-%m-%y")


def main():
    todos_los_partidos = {}

    archivos = list(Path("fixtures_equipos").glob("*.html"))
    print(f"Procesando {len(archivos)} archivos de equipos...")

    for archivo in archivos:
        partidos = extraer_partidos(str(archivo))
        for p in partidos:
            todos_los_partidos[p["match_id"]] = p

    lista_final = sorted(todos_los_partidos.values(), key=lambda p: parsear_fecha(p["fecha"]))

    print(f"\nTotal de partidos unicos de LaLiga: {len(lista_final)}")

    with open("calendario_completo_laliga.json", "w", encoding="utf-8") as f:
        json.dump(lista_final, f, ensure_ascii=False, indent=2)

    print("Guardado en calendario_completo_laliga.json")


if __name__ == "__main__":
    main()

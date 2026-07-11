import json
from pathlib import Path

CARPETA_DATA = Path("data")

def tiene_fotmob(datos):
    home = datos.get("home", {})
    away = datos.get("away", {})
    return "fotmob" in home and "fotmob" in away

def main():
    archivos = sorted(CARPETA_DATA.glob("*.json"))
    archivos = [f for f in archivos if f.name != "lista.json"]

    faltantes_por_competicion = {}
    total = 0
    con_fotmob = 0

    for archivo in archivos:
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"No se pudo leer {archivo.name}: {e}")
            continue

        total += 1
        competicion = datos.get("competicion", "desconocida")

        if tiene_fotmob(datos):
            con_fotmob += 1
        else:
            faltantes_por_competicion.setdefault(competicion, []).append(archivo.name)

    print(f"Total de partidos en data/: {total}")
    print(f"Con FotMob fusionado: {con_fotmob}")
    print(f"Sin FotMob fusionado: {total - con_fotmob}\n")

    for comp, archivos_faltantes in faltantes_por_competicion.items():
        print(f"=== {comp}: {len(archivos_faltantes)} faltantes ===")
        for nombre in sorted(archivos_faltantes):
            print(f"  - {nombre}")
        print()

if __name__ == "__main__":
    main()
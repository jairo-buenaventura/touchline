#!/usr/bin/env python3
"""
agregar_corners_equipo.py
---------------------------
Recorre todos los partidos en data/ y usa el campo "corners" (por equipo,
con la zona de destino ya clasificada por parser.py) para construir, por
cada competicion+temporada, el desglose de hacia donde apunta cada equipo
con sus corners: % en primer palo / centro / segundo palo / corto.

Solo lee data/*.json -- no modifica ningun archivo existente. Genera un
JSON por competicion+temporada en data/corners/.

Uso:
    python3 agregar_corners_equipo.py
"""
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path("data")
SALIDA_DIR = DATA_DIR / "corners"
ZONAS = ["primer_palo", "centro", "segundo_palo", "corto", "sin_peligro"]


def cargar_partidos():
    for f in DATA_DIR.glob("*.json"):
        if f.name in ("lista.json", "jugadores.json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or "home" not in data or "away" not in data:
            continue
        yield data


def acumular():
    acumulado = {}  # (competicion, temporada, equipo) -> {zona: count, "detalle": [...]}

    for match in cargar_partidos():
        competicion = match.get("competicion")
        temporada = match.get("temporada")
        if not competicion or not temporada:
            continue
        for lado in ("home", "away"):
            equipo_data = match.get(lado) or {}
            equipo_nombre = equipo_data.get("equipo")
            if not equipo_nombre:
                continue
            clave = (competicion, temporada, equipo_nombre)
            if clave not in acumulado:
                acumulado[clave] = {z: 0 for z in ZONAS}
                acumulado[clave]["partidos"] = 0
                acumulado[clave]["detalle"] = []
            acumulado[clave]["partidos"] += 1
            for c in equipo_data.get("corners", []):
                zona = c.get("zona")
                if zona in ZONAS:
                    acumulado[clave][zona] += 1
                if c.get("endX") is not None and c.get("endYNorm") is not None:
                    acumulado[clave]["detalle"].append({
                        "endX": c["endX"],
                        "endYNorm": c["endYNorm"],
                        "zona": zona,
                        "jugador": c.get("jugador"),
                        "minuto": c.get("minuto"),
                    })

    return acumulado


def construir_salida(acumulado):
    por_grupo = defaultdict(dict)
    for (competicion, temporada, equipo), conteos in acumulado.items():
        total = sum(conteos[z] for z in ZONAS)
        fila = {
            "equipo": equipo,
            "partidos": conteos["partidos"],
            "total_corners": total,
        }
        for z in ZONAS:
            fila[z] = conteos[z]
            fila[f"{z}_pct"] = round(100 * conteos[z] / total, 1) if total else 0.0
        fila["detalle"] = conteos["detalle"]
        por_grupo[(competicion, temporada)][equipo] = fila

    SALIDA_DIR.mkdir(exist_ok=True)
    resumen = []
    for (competicion, temporada), equipos in por_grupo.items():
        nombre_archivo = f"{competicion}_{temporada.replace('/', '-')}.json"
        ruta = SALIDA_DIR / nombre_archivo
        ruta.write_text(json.dumps(equipos, ensure_ascii=False, indent=2), encoding="utf-8")
        resumen.append({
            "competicion": competicion,
            "temporada": temporada,
            "archivo": nombre_archivo,
            "equipos": len(equipos),
        })
    return resumen


def main():
    print("Acumulando corners de todos los partidos en data/...")
    acumulado = acumular()
    print(f"Equipo x competicion x temporada acumulados: {len(acumulado)}")

    resumen = construir_salida(acumulado)

    ruta_indice = SALIDA_DIR / "indice.json"
    ruta_indice.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nGenerados {len(resumen)} archivos en '{SALIDA_DIR}/':")
    for r in sorted(resumen, key=lambda r: (r["competicion"], r["temporada"])):
        print(f"  {r['competicion']} {r['temporada']}: {r['equipos']} equipos")


if __name__ == "__main__":
    main()

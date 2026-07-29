#!/usr/bin/env python3
"""Revisa log_errores_backfill.json contra el estado actual de data/.

No modifica backfill_masivo.py ni el log original — es de solo lectura.
Cruza cada error loggeado contra data/ para saber si ya se resolvió en un
run posterior. backfill_masivo.py sobrescribe log_errores_backfill.json en
cada corrida y nadie lo revisa después de un reintento exitoso, así que el
log casi siempre queda desactualizado (falso positivo de "error pendiente").

Uso:
    python3 revisar_errores_backfill.py
"""
import json
import os
import re
from collections import Counter

LOG_PATH = "log_errores_backfill.json"
DATA_DIR = "data"


def cargar_equipos_en_data():
    """Lista (home, away, archivo) de todos los partidos ya descargados, sin importar liga/temporada."""
    equipos_por_archivo = []
    patron = re.compile(r"^(.+?) \d+\s*-\s*\d+ (.+?) - .+\.json$")
    for fn in os.listdir(DATA_DIR):
        m = patron.match(fn)
        if m:
            equipos_por_archivo.append((m.group(1), m.group(2), fn))
    return equipos_por_archivo


def ya_existe(home, away, index):
    home_l, away_l = home.strip().lower(), away.strip().lower()
    for h, a, fn in index:
        h_l, a_l = h.lower(), a.lower()
        if (home_l in h_l or h_l in home_l) and (away_l in a_l or a_l in away_l):
            return fn
        if (home_l in a_l or a_l in home_l) and (away_l in h_l or h_l in away_l):
            return fn
    return None


def clasificar_error(msg):
    if "ERR_ABORTED" in msg or "ERR_CONNECTION" in msg:
        return "conexion_abortada"
    if "Timeout" in msg or "timeout" in msg:
        return "timeout"
    if "FALLO" in msg:
        return "parser_fallo"
    return "otro"


def revisar():
    if not os.path.exists(LOG_PATH):
        print(f"No existe {LOG_PATH} — nada que revisar.")
        return

    errores = json.load(open(LOG_PATH, encoding="utf-8"))
    index = cargar_equipos_en_data()

    resueltos, pendientes = [], []
    categorias = Counter()

    for e in errores:
        partido = e.get("partido", "")
        categorias[clasificar_error(e.get("error", ""))] += 1
        if " vs " not in partido:
            pendientes.append(e)
            continue
        home, away = partido.split(" vs ", 1)
        archivo = ya_existe(home, away, index)
        if archivo:
            resueltos.append({**e, "resuelto_en": archivo})
        else:
            pendientes.append(e)

    print(f"Total errores en el log: {len(errores)}")
    print(f"Ya resueltos en un run posterior (log desactualizado): {len(resueltos)}")
    for r in resueltos:
        print(f"  - {r['partido']} -> {r['resuelto_en']}")
    print(f"Todavía pendientes de verdad: {len(pendientes)}")
    for p in pendientes:
        print(f"  - {p['partido']}: {p.get('error', '')[:80]}")
    print(f"\nCategorías de error: {dict(categorias)}")

    with open("reporte_errores_backfill.json", "w", encoding="utf-8") as f:
        json.dump(
            {"resueltos": resueltos, "pendientes": pendientes, "categorias": dict(categorias)},
            f, indent=2, ensure_ascii=False,
        )
    print("\nReporte guardado en reporte_errores_backfill.json")


if __name__ == "__main__":
    revisar()

"""
calcular_xt_timeline.py
------------------------
Convierte el CSV de eventos con xT ya calculado (que vive en
~/Documents/Mundial/<fase>/<carpeta del partido>/*.csv) en un JSON compacto
con la serie de xT por minuto de cada equipo, listo para animar en
visualizador_xt/index.html.

El CSV ya trae xT evento por evento en la columna "xT" (puede ser negativo).
Este script no calcula ningun modelo de xT, solo lo agrega por minuto.

Como usarlo:
    Un partido (ruta relativa a ~/Documents/Mundial/):
        python3 calcular_xt_timeline.py "Semis/101. Francia vs España 0-2"

    Todos los partidos que tengan un CSV:
        python3 calcular_xt_timeline.py --todos
"""

import ast
import csv
import json
import sys
from pathlib import Path

MUNDIAL_DIR = Path.home() / "Documents" / "Mundial"
CARPETA_SALIDA = Path("data_xt")

FASES = ["Jornada 1", "Jornada 2", "Jornada 3", "16avos", "8vos", "4tos", "Semis", "3ro y 4to", "Final"]


def encontrar_csv(carpeta_partido):
    """
    carpeta_partido: ruta absoluta a la carpeta del partido, o ruta relativa
    a MUNDIAL_DIR (ej. "Semis/101. Francia vs España 0-2").
    Devuelve la ruta al primer .csv que encuentre dentro.
    """
    ruta = Path(carpeta_partido)
    if not ruta.is_absolute():
        ruta = MUNDIAL_DIR / carpeta_partido

    if ruta.is_file() and ruta.suffix == ".csv":
        return ruta

    csvs = sorted(ruta.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No hay ningun CSV dentro de '{ruta}'.")
    return csvs[0]


def parsear_card_type(valor_crudo):
    """
    La columna cardType viene como el string de un dict de Python, ej.
    "{'value': 31, 'displayName': 'Yellow'}". La convertimos a texto simple.
    """
    if not valor_crudo:
        return None
    try:
        return ast.literal_eval(valor_crudo).get("displayName")
    except (ValueError, SyntaxError):
        return valor_crudo


def calcular_timeline(ruta_csv):
    with open(ruta_csv, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))

    equipos_orden = []
    for fila in filas:
        equipo = fila.get("teamName")
        if equipo and equipo not in equipos_orden:
            equipos_orden.append(equipo)
    if len(equipos_orden) != 2:
        raise ValueError(f"Se esperaban 2 equipos en el CSV, se encontraron {equipos_orden}")

    home_nombre, away_nombre = equipos_orden

    minuto_max = max((int(f["minute"]) for f in filas if f.get("minute")), default=0)

    xt_por_minuto = {
        home_nombre: [0.0] * (minuto_max + 1),
        away_nombre: [0.0] * (minuto_max + 1),
    }

    eventos = []
    eventos_xt = []
    goles = {home_nombre: 0, away_nombre: 0}

    for fila in filas:
        equipo = fila.get("teamName")
        if equipo not in (home_nombre, away_nombre):
            continue
        minuto_raw = fila.get("minute")
        if minuto_raw in (None, ""):
            continue
        minuto = int(minuto_raw)
        if minuto > minuto_max:
            minuto = minuto_max

        lado = "home" if equipo == home_nombre else "away"

        xt_raw = fila.get("xT")
        if xt_raw not in (None, ""):
            valor_xt = float(xt_raw)
            xt_por_minuto[equipo][minuto] += valor_xt

            # x/y del CSV estan normalizados 0-100 en la direccion de ataque
            # de CADA equipo (x=100 siempre es "cerca del arco rival"), no en
            # una unica orientacion fisica de cancha. Para ubicar el evento
            # en una cancha compartida, el equipo "away" se voltea (100-x)
            # para que ambos equipos ataquen hacia el mismo lado fisico.
            x_final = fila.get("endX") or fila.get("x")
            y_final = fila.get("endY") or fila.get("y")
            if x_final not in (None, "") and y_final not in (None, "") and abs(valor_xt) > 0.0008:
                x_final = float(x_final)
                y_final = float(y_final)
                if lado == "away":
                    x_final = 100 - x_final
                eventos_xt.append({
                    "minuto": minuto,
                    "equipo": lado,
                    "x": round(x_final, 1),
                    "y": round(y_final, 1),
                    "xt": round(valor_xt, 4),
                })

        es_gol = fila.get("isGoal") == "True"
        es_tiro = fila.get("isShot") == "True"
        tarjeta = parsear_card_type(fila.get("cardType"))

        if es_gol:
            goles[equipo] += 1
            eventos.append({
                "minuto": minuto,
                "tipo": "Goal",
                "equipo": lado,
                "jugador": fila.get("name") or "?",
            })
        elif es_tiro:
            eventos.append({
                "minuto": minuto,
                "tipo": "Shot",
                "equipo": lado,
                "jugador": fila.get("name") or "?",
            })

        if tarjeta:
            eventos.append({
                "minuto": minuto,
                "tipo": f"Card:{tarjeta}",
                "equipo": lado,
                "jugador": fila.get("name") or "?",
            })

    def acumular(serie):
        acumulado = []
        total = 0.0
        for valor in serie:
            total += valor
            acumulado.append(round(total, 4))
        return acumulado

    eventos.sort(key=lambda e: e["minuto"])
    eventos_xt.sort(key=lambda e: e["minuto"])

    return {
        "home": {
            "equipo": home_nombre,
            "xt_por_minuto": [round(v, 4) for v in xt_por_minuto[home_nombre]],
            "xt_acumulado": acumular(xt_por_minuto[home_nombre]),
        },
        "away": {
            "equipo": away_nombre,
            "xt_por_minuto": [round(v, 4) for v in xt_por_minuto[away_nombre]],
            "xt_acumulado": acumular(xt_por_minuto[away_nombre]),
        },
        "marcador_final": f"{goles[home_nombre]}-{goles[away_nombre]}",
        "eventos": eventos,
        "eventos_xt": eventos_xt,
    }


def procesar_un_partido(carpeta_partido, carpeta_salida):
    ruta_csv = encontrar_csv(carpeta_partido)
    resultado = calcular_timeline(ruta_csv)

    carpeta_salida.mkdir(exist_ok=True)
    ruta_salida = carpeta_salida / f"{ruta_csv.stem}.json"
    ruta_salida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  [OK] {ruta_csv.name} -> {ruta_salida}")
    print(f"       {resultado['home']['equipo']} {resultado['marcador_final']} {resultado['away']['equipo']}")
    return ruta_salida


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 calcular_xt_timeline.py \"Semis/101. Francia vs España 0-2\"")
        print("     python3 calcular_xt_timeline.py --todos")
        sys.exit(1)

    if sys.argv[1] == "--todos":
        procesados = 0
        fallidos = 0
        for fase in FASES:
            carpeta_fase = MUNDIAL_DIR / fase
            if not carpeta_fase.exists():
                continue
            for carpeta_partido in sorted(carpeta_fase.iterdir()):
                if not carpeta_partido.is_dir():
                    continue
                try:
                    procesar_un_partido(carpeta_partido, CARPETA_SALIDA)
                    procesados += 1
                except FileNotFoundError:
                    continue
                except Exception as e:
                    print(f"  [ERROR] {carpeta_partido.name}: {e}")
                    fallidos += 1
        print(f"\nListo: {procesados} partido(s) procesados, {fallidos} con error.")
        return

    procesar_un_partido(sys.argv[1], CARPETA_SALIDA)


if __name__ == "__main__":
    main()

"""
parser.py
---------
Este script lee un archivo HTML descargado de WhoScored y extrae:
  1. El nombre de los equipos
  2. La lista de jugadores titulares
  3. La posicion promedio de cada jugador en la cancha
  4. Cuantos pases se hicieron entre cada par de jugadores

El resultado se guarda como un archivo JSON limpio en la carpeta data/,
listo para que una pagina web lo lea y lo dibuje.

Como usarlo:
    Un solo partido:
        python3 parser.py partidos_html/nombre_del_archivo.html

    Todos los partidos de la carpeta partidos_html/ de una vez:
        python3 parser.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path


def extraer_match_data(ruta_html):
    """
    Abre el archivo HTML y busca el bloque de texto que contiene
    todos los datos del partido (matchCentreData). WhoScored guarda
    esto como una variable de JavaScript dentro de un <script>.
    """
    contenido = Path(ruta_html).read_text(encoding="utf-8")

    marcador_inicio = "matchCentreData: "
    inicio = contenido.find(marcador_inicio)
    if inicio == -1:
        raise ValueError("No se encontro 'matchCentreData' en este HTML. ¿Es un archivo de WhoScored?")
    inicio += len(marcador_inicio)

    fin = contenido.find("matchCentreEventTypeJson", inicio)
    if fin == -1:
        raise ValueError("No se pudo encontrar el final del bloque de datos.")

    bloque_json = contenido[inicio:fin].strip().rstrip(",").rstrip()
    return json.loads(bloque_json)


def calcular_posiciones_y_pases(data, lado="home", solo_titulares=True, periodo=None):
    """
    A partir del JSON crudo del partido, calcula:
      - la posicion promedio (x, y) de cada jugador
      - cuantos pases exitosos hubo entre cada par de jugadores

    lado: "home" o "away", para elegir que equipo procesar.
    periodo: None para todo el partido, o "FirstHalf" / "SecondHalf" para un tiempo especifico.
    """
    eventos = data["events"]
    nombres = data["playerIdNameDictionary"]
    equipo = data[lado]
    team_id = equipo["teamId"]

    if solo_titulares:
        jugadores_validos = {
            p["playerId"]: p for p in equipo["players"] if p.get("isFirstEleven")
        }
    else:
        jugadores_validos = {p["playerId"]: p for p in equipo["players"]}

    def evento_aplica(ev):
        if ev.get("teamId") != team_id:
            return False
        if ev.get("playerId") not in jugadores_validos:
            return False
        if periodo is not None and ev.get("period", {}).get("displayName") != periodo:
            return False
        return True

    sumas = defaultdict(lambda: {"x": 0.0, "y": 0.0, "toques": 0})
    for ev in eventos:
        if not evento_aplica(ev):
            continue
        if "x" not in ev or "y" not in ev:
            continue
        pid = ev["playerId"]
        sumas[pid]["x"] += ev["x"]
        sumas[pid]["y"] += ev["y"]
        sumas[pid]["toques"] += 1

    jugadores_salida = []
    for pid, s in sumas.items():
        if s["toques"] == 0:
            continue
        info = jugadores_validos[pid]
        jugadores_salida.append({
            "id": pid,
            "nombre": nombres.get(str(pid), info.get("name", "?")),
            "dorsal": info.get("shirtNo"),
            "x": round(s["x"] / s["toques"], 1),
            "y": round(s["y"] / s["toques"], 1),
            "toques": s["toques"],
        })

    eventos_equipo = [ev for ev in eventos if evento_aplica(ev)]
    eventos_equipo.sort(key=lambda ev: (ev.get("minute", 0), ev.get("second", 0), ev.get("eventId", 0)))

    conteo_pases = defaultdict(int)
    for i in range(len(eventos_equipo) - 1):
        actual = eventos_equipo[i]
        siguiente = eventos_equipo[i + 1]
        es_pase_exitoso = (
            actual["type"]["displayName"] == "Pass"
            and actual["outcomeType"]["displayName"] == "Successful"
        )
        if not es_pase_exitoso:
            continue
        quien_pasa = actual["playerId"]
        quien_recibe = siguiente["playerId"]
        if quien_pasa != quien_recibe:
            clave = tuple(sorted([quien_pasa, quien_recibe]))
            conteo_pases[clave] += 1

    pases_salida = [
        {"de": a, "a": b, "veces": veces}
        for (a, b), veces in conteo_pases.items()
    ]

    return {
        "equipo": equipo.get("name"),
        "jugadores": jugadores_salida,
        "pases": pases_salida,
    }


def procesar_un_archivo(ruta_html, carpeta_salida):
    """
    Procesa un solo archivo HTML y guarda su JSON correspondiente.
    Devuelve True si tuvo exito, False si hubo un error (y lo imprime).
    """
    try:
        data = extraer_match_data(ruta_html)
    except Exception as e:
        print(f"  [ERROR] {ruta_html.name}: {e}")
        return False

    resultado = {
        "marcador": data.get("score"),
        "estadio": data.get("venueName"),
        "home": calcular_posiciones_y_pases(data, lado="home"),
        "away": calcular_posiciones_y_pases(data, lado="away"),
    }

    nombre_base = ruta_html.stem
    ruta_salida = carpeta_salida / f"{nombre_base}.json"

    ruta_salida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"  [OK] {ruta_html.name} -> {ruta_salida.name}")
    print(f"       {resultado['home']['equipo']} {resultado['marcador']} {resultado['away']['equipo']}")
    return True


def main():
    carpeta_salida = Path("data")
    carpeta_salida.mkdir(exist_ok=True)

    if len(sys.argv) >= 2:
        ruta_html = Path(sys.argv[1])
        procesar_un_archivo(ruta_html, carpeta_salida)
        return

    carpeta_html = Path("partidos_html")
    if not carpeta_html.exists():
        print(f"No existe la carpeta '{carpeta_html}'. Creala y pon ahi tus archivos HTML.")
        sys.exit(1)

    archivos_html = sorted(carpeta_html.glob("*.html"))
    if not archivos_html:
        print(f"No hay archivos .html dentro de '{carpeta_html}'.")
        sys.exit(1)

    print(f"Procesando {len(archivos_html)} archivo(s) de '{carpeta_html}'...\n")

    exitosos = 0
    for ruta_html in archivos_html:
        if procesar_un_archivo(ruta_html, carpeta_salida):
            exitosos += 1

    print(f"\nListo: {exitosos}/{len(archivos_html)} partidos procesados correctamente.")
    print(f"Los JSON quedaron guardados en la carpeta '{carpeta_salida}'.")


if __name__ == "__main__":
    main()
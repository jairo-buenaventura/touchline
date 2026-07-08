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
import re
import sys
from collections import defaultdict
from pathlib import Path

from capacidades_estadios import CAPACIDADES


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


def extraer_competicion(ruta_html):
    """
    Detecta la competicion a partir del HTML de WhoScored.
    Devuelve: 'world_cup', 'la_liga', u 'otro'.
    """
    contenido = Path(ruta_html).read_text(encoding="utf-8")
    if re.search(r"LaLiga\s+\d{4}", contenido):
        return "la_liga"
    if "World Cup Grp" in contenido or "FIFA World Cup" in contenido:
        return "world_cup"
    return "otro"

def extraer_temporada(ruta_html):
    contenido = Path(ruta_html).read_text(encoding="utf-8")
    m = re.search(r"LaLiga (\d{4})/(\d{4})", contenido)
    if m:
        return f"{m.group(1)[2:]}/{m.group(2)[2:]}"
    if "World Cup Grp" in contenido or re.search(r"FIFA World Cup 20\d\d", contenido):
        return "2026"
    return None
def extraer_grupo(ruta_html):
    """
    Busca en el HTML crudo el texto 'World Cup Grp. X' para identificar
    a que grupo de la fase de grupos pertenece el partido.
    Devuelve None si no lo encuentra (por ejemplo, en fases eliminatorias).
    """
    contenido = Path(ruta_html).read_text(encoding="utf-8")
    m = re.search(r"World Cup Grp\.\s*([A-Z])", contenido)
    return m.group(1) if m else None


def extraer_fecha(ruta_html):
    """
    Busca en el HTML crudo el campo 'startDate' para saber en que fecha
    se jugo el partido. Se usa para calcular la jornada dentro del grupo.
    Devuelve None si no lo encuentra.
    """
    contenido = Path(ruta_html).read_text(encoding="utf-8")
    m = re.search(r'"startDate":"([\d-]+)T', contenido)
    return m.group(1) if m else None


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


def calcular_ppda(data, lado="home"):
    """
    PPDA (Passes allowed Per Defensive Action): pases del equipo rival
    en su zona de armado (x <= 60, fuera del ultimo 40% de la cancha)
    dividido entre las acciones defensivas de este equipo en esa misma
    zona (x >= 40 en su propia escala, que es la misma zona fisica).
    Mientras mas bajo el numero, mas presiona el equipo arriba en la cancha.
    """
    eventos = data["events"]
    equipo = data[lado]
    team_id = equipo["teamId"]
    home_id = data["home"]["teamId"]
    away_id = data["away"]["teamId"]
    rival_id = away_id if team_id == home_id else home_id

    tipos_defensivos = {"Tackle", "Interception", "Foul", "Challenge"}

    pases_rival_zona = 0
    for ev in eventos:
        if ev.get("teamId") == rival_id and ev["type"]["displayName"] == "Pass":
            x = ev.get("x")
            if x is not None and x <= 60:
                pases_rival_zona += 1

    acciones_defensivas_zona = 0
    for ev in eventos:
        if ev.get("teamId") == team_id and ev["type"]["displayName"] in tipos_defensivos:
            x = ev.get("x")
            if x is not None and x >= 40:
                acciones_defensivas_zona += 1

    if acciones_defensivas_zona == 0:
        return None
    return round(pases_rival_zona / acciones_defensivas_zona, 2)


def calcular_alineacion(data, lado="home"):
    """
    Extrae la alineacion titular (en orden de posicion segun la formacion
    inicial), la banca de suplentes, el nombre de la formacion (ej "4-4-2"),
    el capitan y el entrenador.
    """
    equipo = data[lado]
    jugadores = equipo["players"]
    jugadores_por_id = {p["playerId"]: p for p in jugadores}

    formaciones = equipo.get("formations", [])
    primera_formacion = formaciones[0] if formaciones else {}
    formacion_nombre = primera_formacion.get("formationName")
    formacion_legible = "-".join(list(formacion_nombre)) if formacion_nombre else None
    capitan_id = primera_formacion.get("captainPlayerId")

    slots = primera_formacion.get("formationSlots", [])
    ids_formacion = primera_formacion.get("playerIds", [])
    posiciones_xy = primera_formacion.get("formationPositions", [])

    titulares = []
    for i, slot in enumerate(slots):
        if slot == 0:
            continue
        pid = ids_formacion[i] if i < len(ids_formacion) else None
        info = jugadores_por_id.get(pid, {})
        pos_xy = posiciones_xy[slot - 1] if 0 <= slot - 1 < len(posiciones_xy) else None
        titulares.append({
            "id": pid,
            "nombre": info.get("name"),
            "dorsal": info.get("shirtNo"),
            "posicion": info.get("position"),
            "es_capitan": pid == capitan_id,
            "vertical": pos_xy.get("vertical") if pos_xy else None,
            "horizontal": pos_xy.get("horizontal") if pos_xy else None,
        })

    ids_titulares = {t["id"] for t in titulares}
    banca = []
    for p in jugadores:
        if p["playerId"] not in ids_titulares:
            banca.append({
                "id": p["playerId"],
                "nombre": p.get("name"),
                "dorsal": p.get("shirtNo"),
                "posicion": p.get("position"),
            })

    return {
        "formacion": formacion_legible,
        "entrenador": equipo.get("managerName"),
        "titulares": titulares,
        "banca": banca,
    }


def calcular_estadisticas(data, lado="home"):
    """
    Calcula estadisticas generales del equipo para mostrar en el panel
    de resumen: tiros, tiros al arco, pases totales, precision de pases,
    posesion aproximada (basada en cantidad de toques de balon), y goles
    con su minuto y goleador.
    """
    eventos = data["events"]
    nombres = data["playerIdNameDictionary"]
    equipo = data[lado]
    team_id = equipo["teamId"]
    home_id = data["home"]["teamId"]
    away_id = data["away"]["teamId"]

    tipos_tiro = {"MissedShots", "SavedShot", "ShotOnPost", "Goal"}
    tipos_al_arco = {"SavedShot", "Goal"}

    tiros = 0
    tiros_al_arco = 0
    pases_totales = 0
    pases_exitosos = 0
    toques_equipo = 0
    toques_totales = 0
    goles = []

    for ev in eventos:
        tipo = ev["type"]["displayName"]
        team_ev = ev.get("teamId")

        if team_ev == team_id:
            if tipo in tipos_tiro:
                tiros += 1
            if tipo in tipos_al_arco:
                tiros_al_arco += 1
            if tipo == "Pass":
                pases_totales += 1
                if ev["outcomeType"]["displayName"] == "Successful":
                    pases_exitosos += 1
            if ev.get("playerId"):
                toques_equipo += 1
            if tipo == "Goal":
                goles.append({
                    "minuto": ev.get("minute", 0),
                    "jugador": nombres.get(str(ev.get("playerId")), "?"),
                    "penal": ev.get("isGoalFromPenalty", False),
                })

        if tipo == "OwnGoal" and team_ev != team_id and team_ev in (home_id, away_id):
            goles.append({
                "minuto": ev.get("minute", 0),
                "jugador": nombres.get(str(ev.get("playerId")), "?"),
                "own_goal": True,
            })

        if team_ev in (home_id, away_id) and ev.get("playerId"):
            toques_totales += 1

    precision_pases = round(100 * pases_exitosos / pases_totales, 1) if pases_totales else 0.0
    posesion = round(100 * toques_equipo / toques_totales, 1) if toques_totales else 0.0

    goles.sort(key=lambda g: g["minuto"])

    return {
        "tiros": tiros,
        "tiros_al_arco": tiros_al_arco,
        "pases_totales": pases_totales,
        "precision_pases": precision_pases,
        "posesion": posesion,
        "goles": goles,
        "ppda": calcular_ppda(data, lado=lado),
    }


def calcular_tiros(data, lado="home"):
    """
    Extrae la lista de tiros de un equipo, con su posicion de origen en la
    cancha (x, y) y, cuando esta disponible, hacia donde apuntaba el tiro
    dentro del arco (goal_mouth_y, goal_mouth_z), para poder dibujar tanto
    un mapa de tiros sobre la cancha como un mini-marco de portico.
    """
    eventos = data["events"]
    nombres = data["playerIdNameDictionary"]
    equipo = data[lado]
    team_id = equipo["teamId"]

    tipos_tiro = {"MissedShots", "SavedShot", "ShotOnPost", "Goal"}

    tiros_salida = []
    for ev in eventos:
        if ev.get("teamId") != team_id:
            continue
        tipo = ev["type"]["displayName"]
        if tipo not in tipos_tiro:
            continue

        tiros_salida.append({
            "minuto": ev.get("minute", 0),
            "jugador": nombres.get(str(ev.get("playerId")), "?"),
            "resultado": tipo,
            "x": ev.get("x"),
            "y": ev.get("y"),
            "arco_y": ev.get("goalMouthY"),
            "arco_z": ev.get("goalMouthZ"),
        })

    tiros_salida.sort(key=lambda t: t["minuto"])
    return tiros_salida


def calcular_recepcion_pases(data, lado="home", solo_titulares=True):
    """
    Para cada jugador, calcula todos los puntos donde recibio un pase
    (posicion de destino del pase, endX/endY), distinguiendo pases
    normales, pases clave (key pass) y asistencias (assist).
    Tambien cuenta cuantos pases recibio en el ultimo tercio, en el
    area rival, y cuantos de esos pases fueron centros (crosses).
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

    eventos_equipo = [ev for ev in eventos if ev.get("teamId") == team_id]
    eventos_equipo.sort(key=lambda ev: (ev.get("minute", 0), ev.get("second", 0), ev.get("eventId", 0)))

    resultado_por_jugador = {}

    for i in range(len(eventos_equipo) - 1):
        actual = eventos_equipo[i]
        siguiente = eventos_equipo[i + 1]

        es_pase_exitoso = (
            actual["type"]["displayName"] == "Pass"
            and actual["outcomeType"]["displayName"] == "Successful"
        )
        if not es_pase_exitoso:
            continue

        quien_pasa = actual.get("playerId")
        quien_recibe = siguiente.get("playerId")
        if quien_recibe is None or quien_recibe == quien_pasa:
            continue
        if quien_recibe not in jugadores_validos:
            continue

        nombres_qualifiers = {q["type"]["displayName"] for q in actual.get("qualifiers", [])}
        es_cruce = "Cross" in nombres_qualifiers
        es_pase_clave = "KeyPass" in nombres_qualifiers
        es_asistencia = "IntentionalGoalAssist" in nombres_qualifiers or "IntentionalAssist" in nombres_qualifiers

        end_x = actual.get("endX")
        end_y = actual.get("endY")
        if end_x is None or end_y is None:
            continue

        if quien_recibe not in resultado_por_jugador:
            info = jugadores_validos[quien_recibe]
            resultado_por_jugador[quien_recibe] = {
                "id": quien_recibe,
                "nombre": nombres.get(str(quien_recibe), info.get("name", "?")),
                "recepciones": [],
                "pases_clave_recibidos": [],
                "asistencias_recibidas": [],
                "en_tercio_final": 0,
                "en_area_rival": 0,
                "cruces_recibidos": 0,
            }

        registro = resultado_por_jugador[quien_recibe]
        punto = {"x": round(end_x, 1), "y": round(end_y, 1)}
        punto_con_origen = {
            "x": round(end_x, 1),
            "y": round(end_y, 1),
            "x_inicio": round(actual.get("x", end_x), 1),
            "y_inicio": round(actual.get("y", end_y), 1),
        }

        if es_asistencia:
            registro["asistencias_recibidas"].append(punto_con_origen)
        elif es_pase_clave:
            registro["pases_clave_recibidos"].append(punto_con_origen)
        else:
            registro["recepciones"].append(punto)

        if end_x >= 66.7:
            registro["en_tercio_final"] += 1
        if end_x >= 83.0 and 21.1 <= end_y <= 78.9:
            registro["en_area_rival"] += 1
        if es_cruce:
            registro["cruces_recibidos"] += 1

    return list(resultado_por_jugador.values())


def calcular_acciones(data, lado="home", solo_titulares=True):
    """
    Extrae acciones individuales (regates, recuperaciones, intercepciones,
    tackles, faltas, despejes, aereos, pases bloqueados, perdidas de balon)
    agrupadas por jugador, para dibujar un mapa de acciones de un jugador
    especifico sobre la cancha.
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

    tipos_accion = {
        "TakeOn", "BallRecovery", "Interception", "Tackle", "Foul",
        "Aerial", "Clearance", "BlockedPass", "Dispossessed", "Challenge",
    }

    acciones_por_jugador = {}
    for ev in eventos:
        if ev.get("teamId") != team_id:
            continue
        pid = ev.get("playerId")
        if pid not in jugadores_validos:
            continue
        tipo = ev["type"]["displayName"]
        if tipo not in tipos_accion:
            continue
        if "x" not in ev or "y" not in ev:
            continue

        if pid not in acciones_por_jugador:
            info = jugadores_validos[pid]
            acciones_por_jugador[pid] = {
                "id": pid,
                "nombre": nombres.get(str(pid), info.get("name", "?")),
                "acciones": [],
            }

        acciones_por_jugador[pid]["acciones"].append({
            "tipo": tipo,
            "x": ev["x"],
            "y": ev["y"],
            "exitoso": ev.get("outcomeType", {}).get("displayName") == "Successful",
        })

    return list(acciones_por_jugador.values())


def procesar_un_archivo(ruta_html, carpeta_salida):
    """
    Procesa un solo archivo HTML y guarda su JSON correspondiente.
    Devuelve un resumen del partido si tuvo exito, o None si hubo un error (y lo imprime).
    """
    try:
        data = extraer_match_data(ruta_html)
    except Exception as e:
        print(f"  [ERROR] {ruta_html.name}: {e}")
        return None

    home_datos = calcular_posiciones_y_pases(data, lado="home")
    away_datos = calcular_posiciones_y_pases(data, lado="away")
    home_datos["estadisticas"] = calcular_estadisticas(data, lado="home")
    away_datos["estadisticas"] = calcular_estadisticas(data, lado="away")
    home_datos["tiros"] = calcular_tiros(data, lado="home")
    away_datos["tiros"] = calcular_tiros(data, lado="away")
    home_datos["acciones"] = calcular_acciones(data, lado="home", solo_titulares=False)
    away_datos["acciones"] = calcular_acciones(data, lado="away", solo_titulares=False)
    home_datos["recepcion_pases"] = calcular_recepcion_pases(data, lado="home", solo_titulares=False)
    away_datos["recepcion_pases"] = calcular_recepcion_pases(data, lado="away", solo_titulares=False)
    home_datos["alineacion"] = calcular_alineacion(data, lado="home")
    away_datos["alineacion"] = calcular_alineacion(data, lado="away")

    nombre_estadio = data.get("venueName")
    resultado = {
        "marcador": data.get("score"),
        "estadio": nombre_estadio,
        "capacidad_estadio": CAPACIDADES.get(nombre_estadio),
        "asistencia": data.get("attendance"),
        "competicion": extraer_competicion(ruta_html),
        "temporada": extraer_temporada(ruta_html),
        "home": home_datos,
        "away": away_datos,
    }

    nombre_base = ruta_html.stem
    nombre_json = f"{nombre_base}.json"
    ruta_salida = carpeta_salida / nombre_json

    ruta_salida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"  [OK] {ruta_html.name} -> {ruta_salida.name}")
    print(f"       {resultado['home']['equipo']} {resultado['marcador']} {resultado['away']['equipo']}")

    return {
        "archivo": nombre_json,
        "home": resultado["home"]["equipo"],
        "away": resultado["away"]["equipo"],
        "marcador": resultado["marcador"],
        "estadio": resultado["estadio"],
        "grupo": extraer_grupo(ruta_html),
        "fecha": extraer_fecha(ruta_html),
        "competicion": extraer_competicion(ruta_html),
        "temporada": extraer_temporada(ruta_html),
    }


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

    resumenes = []
    for ruta_html in archivos_html:
        resumen = procesar_un_archivo(ruta_html, carpeta_salida)
        if resumen is not None:
            resumenes.append(resumen)

    por_grupo = defaultdict(list)
    for r in resumenes:
        if r.get("grupo") and r.get("fecha"):
            por_grupo[r["grupo"]].append(r)
    for grupo, partidos in por_grupo.items():
        partidos.sort(key=lambda r: r["fecha"])
        for i, r in enumerate(partidos):
            r["jornada"] = (i // 2) + 1

    ruta_lista = carpeta_salida / "lista.json"
    ruta_lista.write_text(
        json.dumps(resumenes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nListo: {len(resumenes)}/{len(archivos_html)} partidos procesados correctamente.")
    print(f"Los JSON quedaron guardados en la carpeta '{carpeta_salida}'.")
    print(f"Lista de partidos actualizada en '{ruta_lista}'.")


if __name__ == "__main__":
    main()

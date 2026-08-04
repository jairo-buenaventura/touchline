"""
sofascore_parser.py
--------------------
Rescata partidos que WhoScored NO tiene con datos detallados (su
`matchCentreData` viene `null` en vez de un objeto -- confirmado que es
un hueco real del lado de WhoScored, no un bug de descarga nuestro:
la pagina en vivo de esos partidos se queda cargando para siempre).

Sofascore SI tiene datos reales para esos mismos partidos (mapa de
tiros con xG, estadisticas de equipo, alineaciones, posiciones
promedio), pero con un limite importante: no expone el pase-por-pase
individual que usa el resto del pipeline para construir la red de
pases, el mapa de acciones por jugador y la recepcion de pases. Por
eso este modulo es un COMPLEMENTO/fallback, no un reemplazo: llena lo
que puede (marcador, estadio, alineacion, estadisticas, mapa de
tiros, posicion promedio) y deja vacias las listas que necesitarian
el stream completo de eventos (`pases`, `acciones`,
`recepcion_pases`, `corners`, `stats_avanzadas`).

Consecuencias de usar un partido "rescatado" con Sofascore (documentado
para quien audite esto despues):
  - Las pestañas "Passing network" y "Action map"/"Pass receiving" del
    Pitch view quedan sin datos para ESE partido especifico (el
    frontend ya maneja listas vacias de forma segura, mostrando
    "sin datos registrados" en vez de romperse -- verificado en
    index.html antes de escribir este modulo).
  - Los suplentes que SI jugaron no aparecen en el historial de
    apariciones del jugador (jugadores.json), porque
    construir_indice_jugadores() en parser.py solo cuenta un suplente
    como "jugo" si aparece en `acciones`/`recepcion_pases`, que aqui
    quedan vacios. Solo los titulares quedan registrados.
  - Esos jugadores no suman en los rankings agregados (Leaders), ya
    que `stats_avanzadas` tambien queda vacio (no hay forma honesta de
    calcular goles/asistencias/regates por jugador sin el stream de
    eventos).
  - Los IDs de jugador son de Sofascore, prefijados "sofascore-" para
    que NUNCA puedan chocar con un id numerico real de WhoScored. Esto
    significa que un jugador que aparece en un partido rescatado y en
    partidos normales de WhoScored queda con DOS entradas separadas en
    jugadores.json (una por cada fuente) -- no hay forma de unirlas
    sin una base de datos de identidad cruzada entre ambas fuentes,
    que no existe.

Uso (llamado automaticamente desde parser.py, no hace falta correrlo
aparte):
    candidatos = [{"ruta_html": Path(...), "liga": "serie_a", "temporada": "22/23"}, ...]
    resumenes_rescatados = rescatar_partidos(candidatos, Path("data"))
"""

import difflib
import json
import re
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

DEMORA_ENTRE_PARTIDOS = 1.5


def _normalizar(nombre):
    base = (nombre or "").strip().lower()
    base = "".join(c for c in unicodedata.normalize("NFD", base) if unicodedata.category(c) != "Mn")
    return base


def _nombres_coinciden(a, b):
    """
    Compara dos nombres de equipo ya normalizados. No alcanza con
    substring (ej. "Rennes" vs "Stade Rennais" no comparten substring
    pero son el mismo equipo), asi que se agrega una segunda pasada de
    similitud difusa palabra-por-palabra. Esto SOLO decide si un
    candidato pasa a la siguiente validacion (fecha dentro de la
    temporada + marcador exacto) -- ambas son mucho mas estrictas que
    el nombre, asi que un poco de margen aca no genera falsos
    positivos: no hay dos partidos con el mismo marcador exacto y la
    misma fecha aproximada entre equipos completamente distintos.
    """
    if a in b or b in a:
        return True
    palabras_a = a.split()
    palabras_b = b.split()
    for pa in palabras_a:
        if len(pa) < 4:
            continue
        for pb in palabras_b:
            if len(pb) < 4:
                continue
            if difflib.SequenceMatcher(None, pa, pb).ratio() >= 0.75:
                return True
    return False


def _parsear_nombre_archivo(ruta_html):
    """
    Extrae home/away/marcador del nombre de archivo, ej.
    "Atalanta 3 - 2 Spezia - Serie A 2022_2023.html" o
    "Almeria 1-2 Real Madrid - LaLiga 2022-2023.html" (ambos formatos,
    con o sin espacios alrededor del guion del marcador).

    No se usa el nombre de liga/temporada de aqui (eso ya lo calcula
    parser.py con sus propias funciones extraer_competicion/
    extraer_temporada, que SI funcionan sin matchCentreData); esta
    funcion solo necesita separar equipos y marcador.
    """
    stem = ruta_html.stem
    m = re.match(r"^(.*?)\s+(\d+)\s*-\s*(\d+)\s+(.*?)\s+-\s+.+$", stem)
    if not m:
        return None
    home, gh, ga, away = m.groups()
    return {"home": home.strip(), "away": away.strip(), "gh": int(gh), "ga": int(ga)}


def _ventana_temporada(temporada_corta):
    """
    "22/23" -> (date(2022,6,1), date(2023,8,31)), con margen generoso
    a cada lado (transferencias/pretemporada no importan aca, solo
    evitar confundir con la MISMA fecha de OTRA temporada -- ej. dos
    ediciones distintas de "Equipo A vs Equipo B" con el mismo
    marcador en años distintos).
    """
    m = re.match(r"(\d{2})/(\d{2})", temporada_corta or "")
    if not m:
        return None, None
    a1, a2 = int(m.group(1)), int(m.group(2))
    anio1 = 2000 + a1
    anio2 = 2000 + a2 if a2 > a1 else 2000 + a2 + 100  # por si acaso, no deberia pasar en 20xx
    return date(anio1, 6, 1), date(anio2, 8, 31)


def _buscar_candidatos(page, home, away):
    """
    Busca en Sofascore usando su endpoint de busqueda publico. Devuelve
    TODOS los partidos de football que matchean el texto, sin filtrar
    todavia por liga/fecha/marcador (eso lo hace _elegir_evento).
    """
    query = f"{home} {away}"
    resultado = page.evaluate(
        """async (q) => {
            const res = await fetch('https://api.sofascore.com/api/v1/search/all?q=' + encodeURIComponent(q) + '&page=0');
            if (!res.ok) return {status: res.status, results: []};
            const data = await res.json();
            const eventos = (data.results || []).filter(r => r.type === 'event').map(r => r.entity);
            return {status: res.status, results: eventos};
        }""",
        query,
    )
    return resultado.get("results", [])


def _elegir_evento(candidatos, home, away, gh, ga, temporada_corta):
    """
    De la lista de candidatos crudos de Sofascore, elige el que
    corresponde al partido real, validando TRES cosas a la vez (no
    alcanza con el nombre solo, porque el mismo par de equipos puede
    haber jugado varias veces en distintas competiciones/temporadas):
      1. Los nombres de equipo coinciden (substring bidireccional,
         igual que el matcher de fotmob_parser.py).
      2. La fecha cae dentro de la ventana de la temporada pedida.
      3. El marcador final coincide EXACTO con el que ya sabemos que
         es correcto (viene del nombre de archivo, que a su vez viene
         de la propia lista de partidos de WhoScored).

    Si no hay un candidato que cumpla las tres, devuelve None -- mejor
    no rescatar nada que rescatar el partido equivocado.
    """
    home_n, away_n = _normalizar(home), _normalizar(away)
    fecha_min, fecha_max = _ventana_temporada(temporada_corta)

    for c in candidatos:
        home_c = c.get("homeTeam", {}).get("name", "")
        away_c = c.get("awayTeam", {}).get("name", "")
        home_cn, away_cn = _normalizar(home_c), _normalizar(away_c)

        if not (_nombres_coinciden(home_n, home_cn) and _nombres_coinciden(away_n, away_cn)):
            continue

        ts = c.get("startTimestamp")
        if ts is None:
            continue
        fecha_evento = datetime.utcfromtimestamp(ts).date()
        if fecha_min and not (fecha_min <= fecha_evento <= fecha_max):
            continue

        hs = c.get("homeScore", {}).get("display")
        as_ = c.get("awayScore", {}).get("display")
        if hs != gh or as_ != ga:
            continue

        return c.get("id")

    return None


def _dorsal_int(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return valor


def _mapear_resultado_tiro(shot_type):
    return {
        "goal": "Goal",
        "save": "SavedShot",
        "post": "ShotOnPost",
        "miss": "MissedShots",
        # Sofascore distingue tiros bloqueados; WhoScored no tiene esa
        # categoria en su lista de tiros -- el bucket mas parecido
        # visualmente es "MissedShots" (tampoco llego al arco).
        "block": "MissedShots",
    }.get(shot_type, "MissedShots")


def _extraer_lado(page, event_id, team_id, es_home, home_ws, away_ws, lineup_lado):
    """
    Arma el dict de un lado (home o away) con la MISMA forma que
    produce parser.py para un partido normal de WhoScored, dejando
    vacias las listas que necesitan el stream completo de eventos
    (pases, acciones, recepcion_pases, corners, stats_avanzadas).
    """
    equipo_nombre = home_ws if es_home else away_ws

    # --- Alineacion (titulares/banca) ---
    jugadores_lineup = lineup_lado.get("players", [])
    titulares_ids = set()
    titulares, banca = [], []
    for p in jugadores_lineup:
        info = p.get("player", {})
        pid = f"sofascore-{info.get('id')}"
        entrada_base = {
            "id": pid,
            "nombre": info.get("name"),
            "dorsal": _dorsal_int(p.get("shirtNumber") or info.get("jerseyNumber")),
        }
        if not p.get("substitute", True):
            titulares_ids.add(pid)
            titulares.append({
                **entrada_base,
                "posicion": p.get("position") or info.get("position"),
                "es_capitan": bool(p.get("captain")),
                # Sofascore no da la coordenada de formacion (slot
                # vertical/horizontal) que usa WhoScored para dibujar
                # el diagrama de formacion -- se deja en None; el
                # frontend ya tolera esto (no todos los partidos viejos
                # de WhoScored tienen esas coordenadas tampoco).
                "vertical": None,
                "horizontal": None,
            })
        else:
            banca.append({
                **entrada_base,
                "posicion": p.get("position") or info.get("position"),
            })

    formacion = lineup_lado.get("formation")

    # --- Posicion promedio (solo titulares, igual que WhoScored) ---
    avg_res = page.evaluate(
        """async (id) => {
            const res = await fetch(`https://api.sofascore.com/api/v1/event/${id}/average-positions`);
            if (!res.ok) return null;
            return await res.json();
        }""",
        event_id,
    )
    jugadores_salida = []
    if avg_res:
        lado_avg = avg_res.get("home" if es_home else "away", [])
        for entrada in lado_avg:
            info = entrada.get("player", {})
            pid = f"sofascore-{info.get('id')}"
            if pid not in titulares_ids:
                continue  # solo titulares, para calzar con calcular_posiciones_y_pases()
            jugadores_salida.append({
                "id": pid,
                "nombre": info.get("name"),
                "dorsal": _dorsal_int(info.get("jerseyNumber")),
                "x": round(entrada["averageX"], 1) if entrada.get("averageX") is not None else None,
                "y": round(entrada["averageY"], 1) if entrada.get("averageY") is not None else None,
                "toques": entrada.get("pointsCount"),
            })

    return {
        "equipo": equipo_nombre,
        "jugadores": jugadores_salida,
        "pases": [],
        "tiros": [],  # se completa afuera, junto con estadisticas
        "corners": [],
        "acciones": [],
        "recepcion_pases": [],
        "alineacion": {
            "formacion": formacion,
            "entrenador": None,  # se completa afuera (viene del endpoint /event, no de lineups)
            "titulares": titulares,
            "banca": banca,
        },
        "stats_avanzadas": [],
    }


def rescatar_partido(page, ruta_html, liga, temporada):
    """
    Intenta reconstruir UN partido completo usando Sofascore. Devuelve
    (resultado_dict, resumen_dict) si tuvo exito, o (None, None) si no
    encontro un candidato confiable o algo fallo en el camino.
    """
    partes = _parsear_nombre_archivo(ruta_html)
    if partes is None:
        return None, None
    home_ws, away_ws, gh, ga = partes["home"], partes["away"], partes["gh"], partes["ga"]

    candidatos = _buscar_candidatos(page, home_ws, away_ws)
    event_id = _elegir_evento(candidatos, home_ws, away_ws, gh, ga, temporada)
    if event_id is None:
        return None, None

    ev_res = page.evaluate(
        """async (id) => {
            const res = await fetch(`https://api.sofascore.com/api/v1/event/${id}`);
            if (!res.ok) return null;
            return await res.json();
        }""",
        event_id,
    )
    if not ev_res or "event" not in ev_res:
        return None, None
    evento = ev_res["event"]

    # Verificacion final de seguridad: el marcador que YA sabiamos que
    # es correcto (del nombre de archivo) tiene que coincidir con lo
    # que trae este evento especifico, otra vez, ahora sobre el
    # objeto completo (no solo el resumen de busqueda). Si no
    # coincide, algo salio mal en el matching -- mejor abortar.
    if evento.get("homeScore", {}).get("current") != gh or evento.get("awayScore", {}).get("current") != ga:
        return None, None

    lineups_res = page.evaluate(
        """async (id) => {
            const res = await fetch(`https://api.sofascore.com/api/v1/event/${id}/lineups`);
            if (!res.ok) return null;
            return await res.json();
        }""",
        event_id,
    )
    if not lineups_res or not lineups_res.get("home") or not lineups_res.get("away"):
        return None, None

    home_data = _extraer_lado(page, event_id, evento["homeTeam"]["id"], True, home_ws, away_ws, lineups_res["home"])
    away_data = _extraer_lado(page, event_id, evento["awayTeam"]["id"], False, home_ws, away_ws, lineups_res["away"])
    home_data["alineacion"]["entrenador"] = (evento.get("homeTeam", {}).get("manager") or {}).get("name")
    away_data["alineacion"]["entrenador"] = (evento.get("awayTeam", {}).get("manager") or {}).get("name")

    # --- Mapa de tiros ---
    shots_res = page.evaluate(
        """async (id) => {
            const res = await fetch(`https://api.sofascore.com/api/v1/event/${id}/shotmap`);
            if (!res.ok) return null;
            return await res.json();
        }""",
        event_id,
    )
    for s in (shots_res or {}).get("shotmap", []):
        lado_data = home_data if s.get("isHome") else away_data
        coords = s.get("playerCoordinates") or {}
        arco = s.get("goalMouthCoordinates") or {}
        # OJO coordenadas: el shotmap de Sofascore mide x=0 pegado al
        # arco que se esta atacando (0=gol, aumenta hacia mediocancha);
        # WhoScored usa la convencion opuesta, x=100 pegado al arco
        # rival (0=arco propio). Se invierte aca (100-x) para que
        # calcen con aCancha() en index.html. La "y" (ancho de cancha)
        # SI usa la misma convencion en ambas fuentes, no se toca.
        x = coords.get("x")
        lado_data["tiros"].append({
            "minuto": s.get("time", 0),
            "jugador": (s.get("player") or {}).get("name", "?"),
            "resultado": _mapear_resultado_tiro(s.get("shotType")),
            "x": round(100 - x, 1) if x is not None else None,
            "y": round(coords["y"], 1) if coords.get("y") is not None else None,
            "arco_y": arco.get("y"),
            "arco_z": arco.get("z"),
        })
    for lado_data in (home_data, away_data):
        lado_data["tiros"].sort(key=lambda t: t["minuto"])

    # --- Goles (de incidents, no del shotmap, para tener el flag de
    # penal/autogol limpio en vez de tener que inferirlo) ---
    incidents_res = page.evaluate(
        """async (id) => {
            const res = await fetch(`https://api.sofascore.com/api/v1/event/${id}/incidents`);
            if (!res.ok) return null;
            return await res.json();
        }""",
        event_id,
    )
    goles_home, goles_away = [], []
    for inc in (incidents_res or {}).get("incidents", []):
        if inc.get("incidentType") != "goal":
            continue
        minuto = inc.get("time", 0) + (inc.get("addedTime") or 0)
        jugador = (inc.get("player") or {}).get("name", "?")
        es_autogol = inc.get("incidentClass") == "ownGoal"
        if es_autogol:
            # Verificado empiricamente contra un caso real (Julien
            # Laporte, Troyes 2-2 Lorient 22/23): en los incidentes de
            # gol de Sofascore, "isHome" ya indica el lado que SE
            # BENEFICIA del gol (coincide siempre con el lado cuyo
            # homeScore/awayScore sube en ese incidente), sea gol
            # normal o autogol -- NO es el equipo del jugador que lo
            # metio. Por eso NO se invierte aca, al reves de lo que
            # se podria asumir a primera vista.
            entrada = {"minuto": minuto, "jugador": jugador, "own_goal": True}
            (goles_home if inc.get("isHome") else goles_away).append(entrada)
        else:
            entrada = {"minuto": minuto, "jugador": jugador}
            if inc.get("incidentClass") == "penalty":
                entrada["penal"] = True
            (goles_home if inc.get("isHome") else goles_away).append(entrada)
    goles_home.sort(key=lambda g: g["minuto"])
    goles_away.sort(key=lambda g: g["minuto"])

    # --- Estadisticas de equipo ---
    stats_res = page.evaluate(
        """async (id) => {
            const res = await fetch(`https://api.sofascore.com/api/v1/event/${id}/statistics`);
            if (!res.ok) return null;
            return await res.json();
        }""",
        event_id,
    )

    def _item(grupos, nombre_grupo, key):
        grupo = next((g for g in grupos if g.get("groupName") == nombre_grupo), None)
        if not grupo:
            return None, None
        item = next((i for i in grupo.get("statisticsItems", []) if i.get("key") == key), None)
        if not item:
            return None, None
        return item.get("home"), item.get("away")

    def _num(valor):
        if valor is None:
            return None
        m = re.match(r"[\d.]+", str(valor).replace(",", ""))
        return float(m.group(0)) if m else None

    overview = next((s for s in (stats_res or {}).get("statistics", []) if s.get("period") == "ALL"), None)
    grupos = overview.get("groups", []) if overview else []

    posesion_h, posesion_a = _item(grupos, "Match overview", "ballPossession")
    tiros_h, tiros_a = _item(grupos, "Shots", "totalShotsOnGoal")
    tiros_arco_h, tiros_arco_a = _item(grupos, "Shots", "shotsOnGoal")
    pases_h, pases_a = _item(grupos, "Match overview", "passes")
    pases_ok_h, pases_ok_a = _item(grupos, "Passes", "accuratePasses")

    for lado_data, goles, posesion, tiros, tiros_arco, pases, pases_ok in (
        (home_data, goles_home, posesion_h, tiros_h, tiros_arco_h, pases_h, pases_ok_h),
        (away_data, goles_away, posesion_a, tiros_a, tiros_arco_a, pases_a, pases_ok_a),
    ):
        pases_totales = int(_num(pases)) if _num(pases) is not None else 0
        pases_exitosos = int(_num(pases_ok)) if _num(pases_ok) is not None else 0
        lado_data["estadisticas"] = {
            "tiros": int(_num(tiros)) if _num(tiros) is not None else len(lado_data["tiros"]),
            "tiros_al_arco": int(_num(tiros_arco)) if _num(tiros_arco) is not None else 0,
            "pases_totales": pases_totales,
            "precision_pases": round(100 * pases_exitosos / pases_totales, 1) if pases_totales else 0.0,
            "posesion": _num(posesion) or 0.0,
            "goles": goles,
            # PPDA necesita el stream de eventos (pases del rival +
            # acciones defensivas propias en zona) -- no hay forma de
            # calcularlo con lo que da Sofascore. El frontend ya
            # muestra "-" cuando ppda es None (pasa tambien en
            # partidos normales de WhoScored sin acciones defensivas).
            "ppda": None,
        }

    venue = evento.get("venue") or {}
    estadio = (venue.get("stadium") or {}).get("name") or venue.get("name")
    capacidad = (venue.get("stadium") or {}).get("capacity") or venue.get("capacity")
    fecha_iso = datetime.utcfromtimestamp(evento["startTimestamp"]).strftime("%Y-%m-%d") if evento.get("startTimestamp") else None

    resultado = {
        "marcador": f"{gh} : {ga}",
        "estadio": estadio,
        "capacidad_estadio": capacidad,
        "asistencia": evento.get("attendance"),
        "competicion": liga,
        "temporada": temporada,
        "home": home_data,
        "away": away_data,
        "fuente_datos": "sofascore_fallback",
    }

    nombre_json = f"{ruta_html.stem}.json"
    resumen = {
        "archivo": nombre_json,
        "home": home_ws,
        "away": away_ws,
        "marcador": resultado["marcador"],
        "estadio": estadio,
        "grupo": None,
        "fecha": fecha_iso,
        "competicion": liga,
        "temporada": temporada,
    }
    return resultado, resumen


def rescatar_partidos(candidatos, carpeta_salida, silencioso=False):
    """
    candidatos: lista de dicts {"ruta_html": Path, "liga": str, "temporada": str}
    Devuelve la lista de "resumen" (misma forma que procesar_un_archivo)
    de los partidos que SI se pudieron rescatar, para que parser.py los
    sume a lista.json. Los que no se pudieron rescatar se imprimen
    como aviso y quedan fuera (igual que antes: simplemente no existe
    ese partido en data/).
    """
    if not candidatos:
        return []

    resumenes = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto("https://www.sofascore.com", timeout=60000)
            resumenes = _rescatar_con_pagina(page, candidatos, carpeta_salida, silencioso)
            browser.close()
    except Exception as e:
        # Este modulo es un COMPLEMENTO del pipeline principal (ver
        # docstring del archivo) -- si Sofascore esta lento/caido o
        # Playwright falla por lo que sea, nunca debe tumbar main() y
        # dejar sin correr lo que viene despues (lista.json, indice de
        # jugadores, fusion de FotMob). Peor es perder esos pasos que
        # perder el rescate de unos pocos partidos.
        if not silencioso:
            print(f"[Sofascore] [ERROR GENERAL] no se pudo completar el rescate: {e}")
        print(f"[Sofascore] Rescatados {len(resumenes)}/{len(candidatos)} antes de la falla; se sigue con el resto del pipeline.")

    return resumenes


def _rescatar_con_pagina(page, candidatos, carpeta_salida, silencioso):
    """
    Recorre los candidatos con una pagina de Playwright ya lista
    (navegada a sofascore.com). Separado de rescatar_partidos() para
    que el try/except de mas arriba pueda envolver TODO (lanzamiento
    del browser incluido) sin anidar el manejo de errores por partido
    dentro del manejo de errores general.
    """
    resumenes = []
    for i, c in enumerate(candidatos, 1):
        ruta_html = c["ruta_html"]
        etiqueta = f"[Sofascore {i}/{len(candidatos)}] {ruta_html.stem}"
        try:
            resultado, resumen = rescatar_partido(page, ruta_html, c["liga"], c["temporada"])
        except Exception as e:
            resultado, resumen = None, None
            if not silencioso:
                print(f"{etiqueta} -> [ERROR] {e}")

        if resultado is None:
            if not silencioso:
                print(f"{etiqueta} -> [SIN RESCATE] no se encontro un partido confiable en Sofascore")
            time.sleep(DEMORA_ENTRE_PARTIDOS)
            continue

        ruta_salida = carpeta_salida / resumen["archivo"]
        ruta_salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
        resumenes.append(resumen)
        if not silencioso:
            print(f"{etiqueta} -> [OK] rescatado ({resultado['marcador']})")
        time.sleep(DEMORA_ENTRE_PARTIDOS)

    return resumenes

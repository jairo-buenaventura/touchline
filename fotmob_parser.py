"""
fotmob_parser.py
----------------
Lee los HTML guardados manualmente de FotMob (carpeta partidos_fotmob/)
y agrega sus estadisticas avanzadas (xG, xGOT, etc.) a los JSON de
partidos que ya generamos con parser.py (carpeta data/).

Como usarlo:
    python3 fotmob_parser.py
"""

import json
import re
from pathlib import Path


def extraer_datos_fotmob(ruta_html):
    """
    Lee un HTML guardado desde el navegador (con Cmd+S) y extrae los
    datos de FotMob a partir del bloque <script id="__NEXT_DATA__">.
    """
    contenido = Path(ruta_html).read_text(encoding="utf-8")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', contenido, re.DOTALL)
    if not m:
        raise ValueError("No se encontro __NEXT_DATA__ en este HTML.")
    data_completo = json.loads(m.group(1))
    data = data_completo["props"]["pageProps"]
    return _procesar_datos_fotmob(data)


def extraer_datos_fotmob_json(ruta_json):
    """
    Lee un .json guardado copiando la respuesta cruda de la pestaña
    Network -> matchDetails de las Herramientas de Desarrollador de
    Chrome (clic derecho -> Copy -> Copy Response). Este formato trae
    'general' y 'content' directo en la raiz del archivo, sin el
    envoltorio props.pageProps que trae el HTML guardado con Cmd+S.
    """
    contenido = Path(ruta_json).read_text(encoding="utf-8")
    if not contenido.strip():
        raise ValueError("El archivo esta vacio (0 bytes). Vuelve a copiar y pegar el JSON.")
    if contenido.lstrip().startswith("<"):
        raise ValueError("Este archivo .json en realidad contiene HTML (se guardo la pagina completa en vez de copiar la respuesta del Network tab).")
    data = json.loads(contenido)
    return _procesar_datos_fotmob(data)


def _procesar_datos_fotmob(data):
    """
    Logica compartida: recibe un dict que ya tiene 'general' y
    'content' como claves directas (sin importar si vino de un HTML
    o de un JSON crudo de la API) y devuelve las estadisticas.
    """
    general = data["general"]
    home_nombre = general["homeTeam"]["name"]
    away_nombre = general["awayTeam"]["name"]

    if not general.get("finished"):
        raise ValueError(
            f"Partido no jugado todavia ({home_nombre} vs {away_nombre}, "
            f"{general.get('matchTimeUTC')}) - sin estadisticas que extraer."
        )

    stats = data["content"]["stats"]
    if not stats:
        raise ValueError(f"FotMob no trae estadisticas para {home_nombre} vs {away_nombre}.")
    grupos = stats["Periods"]["All"]["stats"]

    def buscar(titulo_grupo, titulo_stat):
        for g in grupos:
            if g.get("title") == titulo_grupo:
                for s in g.get("stats", []):
                    if s.get("title") == titulo_stat:
                        valores = s.get("stats")
                        if valores and valores != [None, None]:
                            return valores
        return None

    def num(valor):
        if valor is None:
            return None
        if isinstance(valor, str):
            m2 = re.match(r"[\d.]+", valor)
            return float(m2.group()) if m2 else None
        return valor

    def desglosar_con_porcentaje(valor):
        """
        Convierte un texto tipo '1 (17%)' en (exitosos, total_estimado).
        Si no hay porcentaje o es 0%, devuelve (exitosos, None).
        """
        if valor is None:
            return None, None
        if not isinstance(valor, str):
            return num(valor), None
        m2 = re.match(r"([\d.]+)\s*\((\d+)%\)", valor)
        if not m2:
            return num(valor), None
        exitosos = float(m2.group(1))
        porcentaje = float(m2.group(2))
        if porcentaje == 0:
            return exitosos, None
        total = round(exitosos / (porcentaje / 100))
        return exitosos, total

    posesion = buscar("Top stats", "Ball possession")
    xg = buscar("Expected goals (xG)", "Expected goals (xG)")
    xgot = buscar("Expected goals (xG)", "xG on target (xGOT)")
    tiros = buscar("Shots", "Total shots")
    tiros_arco = buscar("Shots", "Shots on target")
    pases = buscar("Passes", "Passes")
    pases_propia = buscar("Passes", "Own half")
    pases_opuesta = buscar("Passes", "Opposition half")
    cruces = buscar("Passes", "Accurate crosses")
    corners = buscar("Top stats", "Corners")
    faltas = buscar("Discipline", "Fouls committed")
    big_chances = buscar("Top stats", "Big chances")
    big_chances_perdidas = buscar("Top stats", "Big chances missed")
    tiros_dentro_area = buscar("Shots", "Shots inside box")
    tiros_fuera_area = buscar("Shots", "Shots outside box")

    cruces_home_ok, cruces_home_total = desglosar_con_porcentaje(cruces[0]) if cruces else (None, None)
    cruces_away_ok, cruces_away_total = desglosar_con_porcentaje(cruces[1]) if cruces else (None, None)

    def xg_por_tiro(valor_xg, valor_tiros):
        if valor_xg is None or valor_tiros is None or valor_tiros == 0:
            return None
        return round(valor_xg / valor_tiros, 2)

    xg_home = num(xg[0]) if xg else None
    xg_away = num(xg[1]) if xg else None
    tiros_home = num(tiros[0]) if tiros else None
    tiros_away = num(tiros[1]) if tiros else None

    pases_opuesta_home = num(pases_opuesta[0]) if pases_opuesta else None
    pases_opuesta_away = num(pases_opuesta[1]) if pases_opuesta else None
    if pases_opuesta_home is not None and pases_opuesta_away is not None and (pases_opuesta_home + pases_opuesta_away) > 0:
        total_tilt = pases_opuesta_home + pases_opuesta_away
        field_tilt_home = round(100 * pases_opuesta_home / total_tilt, 1)
        field_tilt_away = round(100 - field_tilt_home, 1)
    else:
        field_tilt_home = None
        field_tilt_away = None

    return {
        "home_nombre": home_nombre,
        "away_nombre": away_nombre,
        "home": {
            "posesion": num(posesion[0]) if posesion else None,
            "xg": xg_home,
            "xgot": num(xgot[0]) if xgot else None,
            "xg_por_tiro": xg_por_tiro(xg_home, tiros_home),
            "tiros": tiros_home,
            "tiros_al_arco": num(tiros_arco[0]) if tiros_arco else None,
            "pases": num(pases[0]) if pases else None,
            "pases_mitad_propia": num(pases_propia[0]) if pases_propia else None,
            "pases_mitad_opuesta": num(pases_opuesta[0]) if pases_opuesta else None,
            "cruces_exitosos": cruces_home_ok,
            "cruces_totales": cruces_home_total,
            "corners": num(corners[0]) if corners else None,
            "faltas": num(faltas[0]) if faltas else None,
            "big_chances": num(big_chances[0]) if big_chances else None,
            "big_chances_perdidas": num(big_chances_perdidas[0]) if big_chances_perdidas else None,
            "tiros_dentro_area": num(tiros_dentro_area[0]) if tiros_dentro_area else None,
            "tiros_fuera_area": num(tiros_fuera_area[0]) if tiros_fuera_area else None,
        },
        "away": {
            "posesion": num(posesion[1]) if posesion else None,
            "xg": xg_away,
            "xgot": num(xgot[1]) if xgot else None,
            "xg_por_tiro": xg_por_tiro(xg_away, tiros_away),
            "tiros": tiros_away,
            "tiros_al_arco": num(tiros_arco[1]) if tiros_arco else None,
            "pases": num(pases[1]) if pases else None,
            "pases_mitad_propia": num(pases_propia[1]) if pases_propia else None,
            "pases_mitad_opuesta": num(pases_opuesta[1]) if pases_opuesta else None,
            "cruces_exitosos": cruces_away_ok,
            "cruces_totales": cruces_away_total,
            "corners": num(corners[1]) if corners else None,
            "faltas": num(faltas[1]) if faltas else None,
            "big_chances": num(big_chances[1]) if big_chances else None,
            "big_chances_perdidas": num(big_chances_perdidas[1]) if big_chances_perdidas else None,
            "tiros_dentro_area": num(tiros_dentro_area[1]) if tiros_dentro_area else None,
            "tiros_fuera_area": num(tiros_fuera_area[1]) if tiros_fuera_area else None,
        },
        "field_tilt_home": field_tilt_home,
        "field_tilt_away": field_tilt_away,
    }


import unicodedata

def normalizar(nombre):
    base = nombre.strip().lower()
    base = "".join(c for c in unicodedata.normalize("NFD", base) if unicodedata.category(c) != "Mn")
    base = base.replace("cape verde", "cabo verde")
    base = base.replace("south korea", "republic of korea")
    base = base.replace("atletico madrid", "atletico")
    base = base.replace("deportivo alaves", "alaves")
    # FotMob usa nombres oficiales completos para la Premier League;
    # los archivos de WhoScored usan las versiones cortas.
    base = base.replace("afc bournemouth", "bournemouth")
    base = base.replace("brighton & hove albion", "brighton")
    base = base.replace("brighton and hove albion", "brighton")
    base = base.replace("leeds united", "leeds")
    base = base.replace("manchester city", "man city")
    base = base.replace("manchester united", "man utd")
    base = base.replace("newcastle united", "newcastle")
    base = base.replace("tottenham hotspur", "tottenham")
    base = base.replace("west ham united", "west ham")
    # Igual, pero para la Bundesliga.
    base = base.replace("1. fc heidenheim 1846", "fc heidenheim")
    base = base.replace("1. fc koln", "fc koln")
    base = base.replace("1. fc union berlin", "union berlin")
    base = base.replace("1. fsv mainz 05", "mainz 05")
    base = base.replace("bayer 04 leverkusen", "bayer leverkusen")
    base = base.replace("borussia monchengladbach", "borussia m.gladbach")
    base = base.replace("fc augsburg", "augsburg")
    base = base.replace("fc bayern munchen", "bayern munich")
    base = base.replace("bayern munchen", "bayern munich")
    base = base.replace("fc st. pauli", "st. pauli")
    base = base.replace("sport-club freiburg", "freiburg")
    base = base.replace("sv werder bremen", "werder bremen")
    base = base.replace("tsg hoffenheim", "hoffenheim")
    base = base.replace("vfl wolfsburg", "wolfsburg")
    base = base.replace("wolverhampton wanderers", "wolves")
    return base


def encontrar_archivo_json(home_fotmob, away_fotmob, carpeta_data, nombre_html_stem=None):
    candidatos = list(carpeta_data.glob("*.json"))
    candidatos = [c for c in candidatos if c.name != "lista.json"]

    # Estrategia 1: coincidencia EXACTA quitando el sufijo _FotMob.
    if nombre_html_stem:
        stem_limpio = nombre_html_stem
        if stem_limpio.endswith("_FotMob"):
            stem_limpio = stem_limpio[: -len("_FotMob")]
        for c in candidatos:
            if c.stem == stem_limpio:
                return c

    # Estrategia 2 (segura): requiere AMBOS equipos, EN ORDEN
    # (local antes que visitante, como en "Athletic Club 2-1 Elche")
    # + el marcador exacto. Solo exigir que ambos nombres esten
    # presentes (sin importar el orden) causaba que partidos de ida
    # y vuelta con el mismo marcador (ej. "Fulham 1-0 Leeds" y
    # "Leeds 1-0 Fulham") se fusionaran los dos en el mismo archivo.
    if nombre_html_stem:
        m_score = re.search(r"(\d+)\s*-\s*(\d+)", nombre_html_stem)
        if m_score:
            g1, g2 = m_score.group(1), m_score.group(2)
            # Se generan variantes con y sin espacios alrededor del guion,
            # porque los archivos de Premier League usan "3 - 1" y los de
            # LaLiga usan "3-1".
            marcador_variantes = [
                f"{g1}-{g2}", f"{g2}-{g1}",
                f"{g1} - {g2}", f"{g2} - {g1}",
            ]
            h = normalizar(home_fotmob)
            a = normalizar(away_fotmob)
            for c in candidatos:
                nombre = normalizar(c.stem)
                pos_h = nombre.find(h)
                pos_a = nombre.find(a)
                if pos_h == -1 or pos_a == -1 or pos_h >= pos_a:
                    continue
                for variante in marcador_variantes:
                    # \b evita que "1-0" matchee dentro de "11-0"
                    patron = r"(?<!\d)" + re.escape(variante) + r"(?!\d)"
                    if re.search(patron, c.stem):
                        return c
    # Estrategia 3: solo equipos sin marcador. Esto SOLO es seguro
    # cuando el nombre del archivo no trae marcador (los FotMob del
    # Mundial en español, ej. "Argentina vs Brasil - marcador en
    # vivo..."). Si el archivo SI tenia marcador pero la Estrategia 2
    # no encontro nada, NO caemos aqui: eso significaria fusionar a
    # ciegas sin verificar el resultado, y en una liga con ida y
    # vuelta eso puede pegar el partido equivocado sin avisar.
    tiene_marcador = bool(nombre_html_stem and re.search(r"(\d+)\s*-\s*(\d+)", nombre_html_stem))
    if not tiene_marcador and home_fotmob and away_fotmob:
        h = normalizar(home_fotmob)
        a = normalizar(away_fotmob)
        for c in candidatos:
            nombre = normalizar(c.stem)
            if h in nombre and a in nombre:
                return c
    return None


def main():
    carpeta_fotmob = Path("partidos_fotmob")
    carpeta_data = Path("data")

    if not carpeta_fotmob.exists():
        print(f"No existe la carpeta '{carpeta_fotmob}'.")
        return

    archivos_html = sorted(carpeta_fotmob.glob("*.html"))
    archivos_json = sorted(carpeta_fotmob.glob("*.json"))
    archivos = archivos_html + archivos_json
    if not archivos:
        print(f"No hay archivos .html ni .json en '{carpeta_fotmob}'.")
        return

    actualizados = 0
    for archivo in archivos:
        try:
            if archivo.suffix == ".json":
                datos_fotmob = extraer_datos_fotmob_json(archivo)
            else:
                datos_fotmob = extraer_datos_fotmob(archivo)
        except Exception as e:
            print(f"  [ERROR] {archivo.name}: {e}")
            continue

        ruta_json = encontrar_archivo_json(
            datos_fotmob["home_nombre"], datos_fotmob["away_nombre"], carpeta_data, archivo.stem
        )
        if ruta_json is None:
            print(f"  [SIN MATCH] {archivo.name} ({datos_fotmob['home_nombre']} vs {datos_fotmob['away_nombre']}) - no se encontro JSON correspondiente")
            continue

        partido_json = json.loads(ruta_json.read_text(encoding="utf-8"))
        partido_json["home"]["fotmob"] = datos_fotmob["home"]
        partido_json["away"]["fotmob"] = datos_fotmob["away"]
        partido_json["home"]["fotmob"]["field_tilt"] = datos_fotmob["field_tilt_home"]
        partido_json["away"]["fotmob"]["field_tilt"] = datos_fotmob["field_tilt_away"]
        ruta_json.write_text(json.dumps(partido_json, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"  [OK] {archivo.name} -> {ruta_json.name}")
        actualizados += 1

    print(f"\nListo: {actualizados}/{len(archivos)} partidos actualizados con datos de FotMob.")


if __name__ == "__main__":
    main()

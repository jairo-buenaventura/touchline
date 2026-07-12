"""
descargar_fotmob_premier.py
----------------------------
Automatiza la descarga de datos de FotMob (la respuesta real de
matchDetails, la misma que veniamos copiando a mano del Network tab)
para todos los partidos de Premier League 2025/26 que aun no tengan
su archivo en partidos_fotmob/.

Es idempotente: si corres el script varias veces, salta los partidos
que ya estan descargados y solo intenta los que faltan. Si algo falla
a mitad de camino (tu internet, un timeout, etc.), simplemente vuelve
a correrlo y sigue donde se quedo.

Requisitos (ya deberian estar instalados si usaste Playwright antes):
    pip install playwright --break-system-packages
    playwright install chromium

Uso:
    python3 descargar_fotmob_premier.py
"""

import json
import re
import time
import unicodedata
from pathlib import Path

from playwright.sync_api import sync_playwright

LEAGUE_ID_FOTMOB = 47  # Premier League en FotMob
CARPETA_FOTMOB = Path("partidos_fotmob")
DEMORA_ENTRE_PARTIDOS = 2.5  # segundos, para no saturar el sitio

# Los 380 partidos oficiales de la Premier League 2025/26
# (ronda, fecha, local, visitante, marcador)
FIXTURES_RAW = Path(__file__).parent / "premier_league_fixtures.csv"


def normalizar(nombre):
    base = nombre.strip().lower()
    base = "".join(
        c for c in unicodedata.normalize("NFD", base) if unicodedata.category(c) != "Mn"
    )
    return base


def cargar_fixtures():
    """Lee el CSV de fixtures (ronda,fecha,local,visitante,marcador)."""
    fixtures = []
    with open(FIXTURES_RAW, encoding="utf-8") as f:
        for linea in f:
            partes = linea.strip().split(",")
            if len(partes) != 5:
                continue
            ronda, fecha, home, away, marcador = partes
            fixtures.append({"ronda": ronda, "fecha": fecha, "home": home, "away": away, "marcador": marcador})
    return fixtures


def nombre_archivo_esperado(home, away, marcador):
    return f"{home} {marcador} {away} - Premier League 2025-2026_FotMob.json"


def ya_descargado(home, away, marcador):
    """
    Revisa si ya existe un .json o .html en partidos_fotmob/ para este
    partido, comparando nombres normalizados (sin tildes, minusculas)
    en vez de exigir coincidencia exacta de archivo.
    """
    h = normalizar(home)
    a = normalizar(away)
    for archivo in CARPETA_FOTMOB.glob("*Premier League*"):
        nombre = normalizar(archivo.stem)
        if h in nombre and a in nombre:
            return True
    return False


NOMBRES_BUSQUEDA = {
    "Man Utd": "Manchester United",
    "Man City": "Manchester City",
    "Nott'm Forest": "Nottingham Forest",
    "Spurs": "Tottenham Hotspur",
}


def convertir_fecha(fecha_dd_mm_aaaa):
    """Convierte '15/08/2025' -> '2025-08-15' (formato ISO)."""
    dia, mes, anio = fecha_dd_mm_aaaa.split("/")
    return f"{anio}-{mes}-{dia}"


def cargar_calendario_fotmob(request_context):
    """
    Trae el calendario COMPLETO de la temporada en una sola llamada
    (en vez de buscar partido por partido, que se confunde con
    equipos grandes que tienen muchos cruces). Devuelve una lista de
    partidos con su matchId, nombres de equipo (tal como los escribe
    FotMob) y fecha.
    """
    url = "https://www.fotmob.com/api/data/leagues?id=47&season=2025/2026&ccode3=ENG"
    resp = request_context.get(url)
    if not resp.ok:
        raise RuntimeError(f"No se pudo traer el calendario de FotMob (status {resp.status})")
    data = resp.json()

    # La clave exacta puede variar segun la version de la API
    # (se ha visto 'matches' y 'fixtures' en distintos momentos).
    bloque = data.get("matches") or data.get("fixtures") or {}
    partidos = bloque.get("allMatches", [])
    if not partidos:
        raise RuntimeError(
            "El calendario llego vacio. Claves de nivel superior recibidas: "
            + ", ".join(data.keys())
        )

    calendario = []
    for p in partidos:
        calendario.append({
            "id": p.get("id"),
            "home": normalizar(p.get("home", {}).get("name", "")),
            "away": normalizar(p.get("away", {}).get("name", "")),
            "fecha": (p.get("status", {}).get("utcTime") or "")[:10],
        })
    return calendario


def buscar_match_id_en_calendario(calendario, home, away, fecha_esperada_dd_mm_aaaa):
    """
    Busca el matchId dentro del calendario ya descargado, comparando
    nombres normalizados (con contiene, no igualdad exacta, porque
    FotMob puede usar 'Manchester United' y nosotros 'Man Utd') y
    exigiendo que la fecha coincida exactamente.
    """
    fecha_esperada = convertir_fecha(fecha_esperada_dd_mm_aaaa)
    home_norm = normalizar(NOMBRES_BUSQUEDA.get(home, home))
    away_norm = normalizar(NOMBRES_BUSQUEDA.get(away, away))

    for p in calendario:
        if p["fecha"] != fecha_esperada:
            continue
        h_ok = home_norm in p["home"] or p["home"] in home_norm
        a_ok = away_norm in p["away"] or p["away"] in away_norm
        if h_ok and a_ok:
            return p["id"]
    return None


def descargar_match_details(page, match_id):
    """
    Navega a la pagina del partido y captura la respuesta real de
    matchDetails que carga la app (la misma que se copiaba a mano del
    Network tab). Devuelve el dict ya parseado, o None si no llego a
    tiempo.
    """
    resultado = {}

    def on_response(response):
        if "matchDetails" in response.url and str(match_id) in response.url:
            try:
                resultado["data"] = response.json()
            except Exception:
                pass

    page.on("response", on_response)
    try:
        page.goto(f"https://www.fotmob.com/match/{match_id}", wait_until="networkidle", timeout=20000)
    except Exception:
        pass

    # Dar un poco mas de tiempo si la respuesta no habia llegado aun
    for _ in range(10):
        if "data" in resultado:
            break
        page.wait_for_timeout(500)

    page.remove_listener("response", on_response)
    return resultado.get("data")


def fecha_coincide(datos, fecha_esperada_dd_mm_aaaa):
    """
    Verifica que la fecha real del partido descargado coincida con la
    esperada (con 1 dia de tolerancia por zona horaria). Esto evita
    guardar por error el cruce de otra temporada entre los mismos
    equipos (ej: capturar el partido de 2026/27 en vez del de esta
    temporada).
    """
    try:
        fecha_real = datos["general"]["matchTimeUTCDate"][:10]  # 'YYYY-MM-DD'
    except (KeyError, TypeError):
        return False
    fecha_esperada = convertir_fecha(fecha_esperada_dd_mm_aaaa)
    return fecha_real == fecha_esperada


def main():
    import sys

    limite = None
    if "--limite" in sys.argv:
        idx = sys.argv.index("--limite")
        limite = int(sys.argv[idx + 1])

    if not FIXTURES_RAW.exists():
        print(f"No encuentro '{FIXTURES_RAW}'. Debe estar en la misma carpeta que este script.")
        return

    CARPETA_FOTMOB.mkdir(exist_ok=True)
    fixtures = cargar_fixtures()

    pendientes = [f for f in fixtures if not ya_descargado(f["home"], f["away"], f["marcador"])]
    if limite:
        pendientes = pendientes[:limite]
        print(f"(Modo prueba: solo los primeros {limite} pendientes)\n")

    print(f"Total partidos: {len(fixtures)} | Ya descargados: {len(fixtures) - len(pendientes) if not limite else 'N/A (modo prueba)'} | Pendientes en esta corrida: {len(pendientes)}\n")

    if not pendientes:
        print("No hay nada pendiente. Todo ya esta descargado.")
        return

    exitosos = 0
    fallidos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("Descargando el calendario completo de la temporada...")
        calendario = cargar_calendario_fotmob(context.request)
        print(f"Calendario cargado: {len(calendario)} partidos.\n")

        for i, partido in enumerate(pendientes, 1):
            home, away, marcador, fecha = partido["home"], partido["away"], partido["marcador"], partido["fecha"]
            etiqueta = f"[{i}/{len(pendientes)}] {home} {marcador} {away}"

            match_id = buscar_match_id_en_calendario(calendario, home, away, fecha)
            if not match_id:
                print(f"{etiqueta} -> [SIN MATCH ID]")
                fallidos.append(partido)
                continue

            datos = descargar_match_details(page, match_id)
            if not datos:
                print(f"{etiqueta} -> [ERROR] no llego matchDetails a tiempo")
                fallidos.append(partido)
                continue

            if not fecha_coincide(datos, fecha):
                fecha_real = datos.get("general", {}).get("matchTimeUTC", "?")
                print(f"{etiqueta} -> [RECHAZADO] capturo el partido equivocado (fecha real: {fecha_real})")
                fallidos.append(partido)
                continue

            nombre_archivo = nombre_archivo_esperado(home, away, marcador)
            ruta = CARPETA_FOTMOB / nombre_archivo
            ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
            print(f"{etiqueta} -> [OK] guardado como {nombre_archivo}")
            exitosos += 1

            time.sleep(DEMORA_ENTRE_PARTIDOS)

        browser.close()

    print(f"\nListo: {exitosos}/{len(pendientes)} descargados en esta corrida.")
    if fallidos:
        print(f"{len(fallidos)} quedaron pendientes (vuelve a correr el script para reintentarlos):")
        for f in fallidos:
            print(f"  - {f['home']} {f['marcador']} {f['away']}")


if __name__ == "__main__":
    main()

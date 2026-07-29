"""
descargar_fotmob_mls.py
------------------------
Automatiza la descarga de datos de FotMob (la respuesta real de
matchDetails) para todos los partidos de la MLS 2025 que aun no
tengan su archivo en partidos_fotmob/.

Es idempotente: si corres el script varias veces, salta los partidos
que ya estan descargados y solo intenta los que faltan.

Uso:
    python3 descargar_fotmob_mls.py
"""

import json
import time
import unicodedata
from pathlib import Path

from playwright.sync_api import sync_playwright

LEAGUE_ID_FOTMOB = 130  # MLS en FotMob
TEMPORADA_FOTMOB = "2025"
CARPETA_FOTMOB = Path("partidos_fotmob")
DEMORA_ENTRE_PARTIDOS = 2.0
FIXTURES_JSON = Path(".playwright-mcp/mls_2025_lista.json")


def normalizar(nombre):
    base = nombre.strip().lower()
    base = "".join(
        c for c in unicodedata.normalize("NFD", base) if unicodedata.category(c) != "Mn"
    )
    return base


def cargar_fixtures():
    partidos = json.loads(FIXTURES_JSON.read_text(encoding="utf-8"))
    fixtures = []
    for p in partidos:
        fixtures.append({
            "home": p["home"],
            "away": p["away"],
            "marcador": f"{p['homeScore']}-{p['awayScore']}",
            "fecha": p["startTime"][:10],  # YYYY-MM-DD
        })
    return fixtures


def nombre_archivo_esperado(home, away, marcador):
    return f"{home} {marcador} {away} - MLS 2025_FotMob.json"


def ya_descargado(home, away, marcador):
    return (CARPETA_FOTMOB / nombre_archivo_esperado(home, away, marcador)).exists()


def cargar_calendario_fotmob(request_context):
    url = f"https://www.fotmob.com/api/data/leagues?id={LEAGUE_ID_FOTMOB}&season={TEMPORADA_FOTMOB}&ccode3=USA"
    resp = request_context.get(url)
    if not resp.ok:
        raise RuntimeError(f"No se pudo traer el calendario de FotMob (status {resp.status})")
    data = resp.json()

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


def buscar_match_id_en_calendario(calendario, home, away, fecha_esperada_iso):
    """
    Compara solo con tolerancia de +-1 dia: el 'startTime' de WhoScored
    y el 'utcTime' de FotMob a veces caen en fechas distintas para
    partidos cerca de medianoche UTC (distinta zona horaria de origen),
    aunque describan el mismo partido.
    """
    from datetime import date

    home_norm = normalizar(home)
    away_norm = normalizar(away)
    fecha_esperada = date.fromisoformat(fecha_esperada_iso)

    for p in calendario:
        if not p["fecha"]:
            continue
        try:
            fecha_p = date.fromisoformat(p["fecha"])
        except ValueError:
            continue
        if abs((fecha_p - fecha_esperada).days) > 1:
            continue
        h_ok = home_norm in p["home"] or p["home"] in home_norm
        a_ok = away_norm in p["away"] or p["away"] in away_norm
        if h_ok and a_ok:
            return p["id"]
    return None


def descargar_match_details(page, match_id):
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

    for _ in range(10):
        if "data" in resultado:
            break
        page.wait_for_timeout(500)

    page.remove_listener("response", on_response)
    return resultado.get("data")


def fecha_coincide(datos, fecha_esperada_iso):
    from datetime import date

    try:
        fecha_real = date.fromisoformat(datos["general"]["matchTimeUTCDate"][:10])
    except (KeyError, TypeError, ValueError):
        return False
    fecha_esperada = date.fromisoformat(fecha_esperada_iso)
    return abs((fecha_real - fecha_esperada).days) <= 1


def main():
    import sys

    limite = None
    if "--limite" in sys.argv:
        idx = sys.argv.index("--limite")
        limite = int(sys.argv[idx + 1])

    if not FIXTURES_JSON.exists():
        print(f"No encuentro '{FIXTURES_JSON}'.")
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

            try:
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
            finally:
                time.sleep(DEMORA_ENTRE_PARTIDOS)

        browser.close()

    print(f"\nListo: {exitosos}/{len(pendientes)} descargados en esta corrida.")
    if fallidos:
        print(f"{len(fallidos)} quedaron pendientes (vuelve a correr el script para reintentarlos):")
        for f in fallidos:
            print(f"  - {f['home']} {f['marcador']} {f['away']}")


if __name__ == "__main__":
    main()

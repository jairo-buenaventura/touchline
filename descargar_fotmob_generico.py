"""
descargar_fotmob_generico.py
------------------------------
Version generica (parametrizable por linea de comandos) de los scripts
descargar_fotmob_*.py existentes: descarga la respuesta real de
matchDetails de FotMob para todos los partidos de una liga/temporada
que aun no tengan su archivo en partidos_fotmob/, usando la lista
consolidada de partidos (id/home/away/scores/startTime) que ya se
genero en el Paso 2 del skill descargar-whoscored.

Es idempotente: si corres el script varias veces, salta los partidos
que ya estan descargados y solo intenta los que faltan.

Uso:
    python3 descargar_fotmob_generico.py \
        --league-id 87 --season "2023/2024" --ccode3 ESP \
        --fixtures .playwright-mcp/laliga_2324_lista.json \
        --liga-label "LaLiga" --temporada-label "2023-2024"

    (--liga-label + --temporada-label arman el sufijo del nombre de
    archivo: "{home} {marcador} {away} - {liga-label} {temporada-label}_FotMob.json",
    igual que el resto de los archivos ya existentes en partidos_fotmob/)
"""

import argparse
import json
import time
import unicodedata
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

CARPETA_FOTMOB = Path("partidos_fotmob")
DEMORA_ENTRE_PARTIDOS = 2.0


def normalizar(nombre):
    base = nombre.strip().lower()
    base = "".join(
        c for c in unicodedata.normalize("NFD", base) if unicodedata.category(c) != "Mn"
    )
    return base


def cargar_fixtures(ruta_json):
    partidos = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    fixtures = []
    for p in partidos:
        fixtures.append({
            "home": p["home"],
            "away": p["away"],
            "marcador": f"{p['homeScore']}-{p['awayScore']}",
            "fecha": p["startTime"][:10],
        })
    return fixtures


def cargar_alias(ruta_json):
    if not ruta_json:
        return {}
    return json.loads(Path(ruta_json).read_text(encoding="utf-8"))


def nombre_archivo_esperado(home, away, marcador, liga_label, temporada_label):
    return f"{home} {marcador} {away} - {liga_label} {temporada_label}_FotMob.json"


def ya_descargado(home, away, marcador, liga_label, temporada_label):
    return (CARPETA_FOTMOB / nombre_archivo_esperado(home, away, marcador, liga_label, temporada_label)).exists()


def cargar_calendario_fotmob(request_context, league_id, season, ccode3):
    url = f"https://www.fotmob.com/api/data/leagues?id={league_id}&season={season}&ccode3={ccode3}"
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


def buscar_match_id_en_calendario(calendario, home, away, fecha_esperada_iso, alias=None):
    alias = alias or {}
    home_norm = normalizar(alias.get(home, home))
    away_norm = normalizar(alias.get(away, away))
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
    try:
        fecha_real = date.fromisoformat(datos["general"]["matchTimeUTCDate"][:10])
    except (KeyError, TypeError, ValueError):
        return False
    fecha_esperada = date.fromisoformat(fecha_esperada_iso)
    return abs((fecha_real - fecha_esperada).days) <= 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league-id", type=int, required=True)
    ap.add_argument("--season", required=True)
    ap.add_argument("--ccode3", required=True)
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--liga-label", required=True)
    ap.add_argument("--temporada-label", required=True)
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--alias-json", default=None, help="JSON {nombre_whoscored: nombre_busqueda_fotmob} para equipos cuyo nombre no coincide por substring")
    args = ap.parse_args()

    CARPETA_FOTMOB.mkdir(exist_ok=True)
    fixtures = cargar_fixtures(args.fixtures)
    alias = cargar_alias(args.alias_json)

    pendientes = [
        f for f in fixtures
        if not ya_descargado(f["home"], f["away"], f["marcador"], args.liga_label, args.temporada_label)
    ]
    if args.limite:
        pendientes = pendientes[: args.limite]
        print(f"(Modo prueba: solo los primeros {args.limite} pendientes)\n")

    print(f"Total partidos: {len(fixtures)} | Ya descargados: {len(fixtures) - len(pendientes) if not args.limite else 'N/A (modo prueba)'} | Pendientes en esta corrida: {len(pendientes)}\n")

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
        calendario = cargar_calendario_fotmob(context.request, args.league_id, args.season, args.ccode3)
        print(f"Calendario cargado: {len(calendario)} partidos.\n")

        for i, partido in enumerate(pendientes, 1):
            home, away, marcador, fecha = partido["home"], partido["away"], partido["marcador"], partido["fecha"]
            etiqueta = f"[{i}/{len(pendientes)}] {home} {marcador} {away}"

            try:
                match_id = buscar_match_id_en_calendario(calendario, home, away, fecha, alias)
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

                nombre_archivo = nombre_archivo_esperado(home, away, marcador, args.liga_label, args.temporada_label)
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

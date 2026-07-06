"""
backfill_masivo.py
Procesa partidos en tandas desde partidos_faltantes.json,
usando el mismo flujo de procesar_partido.py (WhoScored + FotMob).

Uso:
    python3 backfill_masivo.py --inicio 0 --cantidad 20
"""

import re
import json
import time
import argparse
import subprocess
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright


def fetch_html(url, wait_ms=8000):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_timeout(wait_ms)
        html = page.content()
        browser.close()
    return html


def buscar_id_fotmob(home, away, fecha_iso):
    termino = f"{home} {away}"
    r = requests.get(
        "https://apigw.fotmob.com/searchapi/suggest",
        params={"term": termino, "lang": "en"},
        timeout=15,
    )
    data = r.json()
    for grupo in data.get("matchSuggest", []):
        for opcion in grupo.get("options", []):
            payload = opcion.get("payload", {})
            if payload.get("matchDate", "")[:10] == fecha_iso:
                return payload["id"]
    return None


def slug_nombre(nombre):
    """Convierte un nombre de equipo a slug simplificado para WhoScored URL."""
    return nombre.lower().replace(" ", "-")


def fecha_ddmmaa_a_iso(fecha_str):
    """Convierte DD-MM-AA a YYYY-MM-DD."""
    dd, mm, aa = fecha_str.split("-")
    return f"20{aa}-{mm}-{dd}"


def procesar_uno(partido, log_errores):
    home = partido["home"]
    away = partido["away"]
    match_id = partido["match_id"]
    fecha_iso = fecha_ddmmaa_a_iso(partido["fecha"])

    nombre_base = f"{home} {partido['marcador'].replace(' ', '')} {away} - LaLiga 2025-2026"
    nombre_base = nombre_base.replace(":", "-")

    whoscored_url = f"https://www.whoscored.com/matches/{match_id}/live/spain-laliga-2025-2026-{slug_nombre(home)}-{slug_nombre(away)}"

    try:
        print(f"  Descargando WhoScored: {home} vs {away}...")
        html_ws = fetch_html(whoscored_url)
        ruta_ws = Path("partidos_html") / f"{nombre_base}.html"
        ruta_ws.write_text(html_ws, encoding="utf-8")

        resultado = subprocess.run(
            ["python3", "parser.py", str(ruta_ws)],
            capture_output=True, text=True
        )
        if resultado.returncode != 0 or "FALLO" in resultado.stdout:
            raise RuntimeError(f"parser.py fallo: {resultado.stdout} {resultado.stderr}")

        fotmob_id = buscar_id_fotmob(home, away, fecha_iso)
        if fotmob_id:
            html_fm = fetch_html(f"https://www.fotmob.com/match/{fotmob_id}")
            ruta_fm = Path("partidos_fotmob") / f"{nombre_base}_FotMob.html"
            ruta_fm.write_text(html_fm, encoding="utf-8")

            resultado_fm = subprocess.run(
                ["python3", "fotmob_parser.py"],
                capture_output=True, text=True
            )

        archivo_json = f"{nombre_base}.json"
        with open("data/lista.json", "r", encoding="utf-8") as f:
            lista = json.load(f)

        if not any(item["archivo"] == archivo_json for item in lista):
            lista.append({
                "archivo": archivo_json,
                "home": home,
                "away": away,
                "marcador": partido["marcador"],
                "estadio": None,
                "fecha": fecha_iso,
                "jornada": None,
            })
            with open("data/lista.json", "w", encoding="utf-8") as f:
                json.dump(lista, f, ensure_ascii=False, indent=2)

        print(f"  OK: {home} vs {away}")
        return True

    except Exception as e:
        print(f"  ERROR: {home} vs {away} -> {e}")
        log_errores.append({"partido": f"{home} vs {away}", "error": str(e)})
        return False


def main():
    parser_args = argparse.ArgumentParser()
    parser_args.add_argument("--inicio", type=int, default=0)
    parser_args.add_argument("--cantidad", type=int, default=20)
    args = parser_args.parse_args()

    with open("partidos_faltantes.json", "r", encoding="utf-8") as f:
        faltantes = json.load(f)

    tanda = faltantes[args.inicio:args.inicio + args.cantidad]
    print(f"Procesando tanda: partidos {args.inicio} a {args.inicio + len(tanda)} de {len(faltantes)}")

    log_errores = []
    exitosos = 0

    for i, partido in enumerate(tanda, start=1):
        print(f"\n[{i}/{len(tanda)}] {partido['home']} vs {partido['away']} ({partido['fecha']})")
        if procesar_uno(partido, log_errores):
            exitosos += 1
        time.sleep(6)

    print(f"\n=== Resumen de la tanda ===")
    print(f"Exitosos: {exitosos}/{len(tanda)}")
    print(f"Errores: {len(log_errores)}")

    if log_errores:
        with open("log_errores_backfill.json", "w", encoding="utf-8") as f:
            json.dump(log_errores, f, ensure_ascii=False, indent=2)
        print("Log de errores guardado en log_errores_backfill.json")


if __name__ == "__main__":
    main()

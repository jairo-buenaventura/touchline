"""Busca partidos de LaLiga sin datos de FotMob y los completa."""

import json
import time
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
import requests


def fetch_html(url, wait_ms=8000):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
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


def main():
    archivos = [a for a in Path("data").glob("*LaLiga*.json")]
    faltantes = []
    for archivo in archivos:
        data = json.load(open(archivo))
        if "fotmob" not in data.get("home", {}):
            faltantes.append((archivo, data))

    print(f"Partidos a completar: {len(faltantes)}")

    for i, (archivo, data) in enumerate(faltantes, start=1):
        home = data["home"]["equipo"]
        away = data["away"]["equipo"]
        print(f"\n[{i}/{len(faltantes)}] {home} vs {away}")

        calendario = json.load(open("calendario_completo_laliga.json"))
        entrada_cal = next((p for p in calendario if p["home"] == home and p["away"] == away), None)
        if entrada_cal:
            dd, mm, aa = entrada_cal["fecha"].split("-")
            fecha_iso = f"20{aa}-{mm}-{dd}"
        else:
            fecha_iso = None

        if not fecha_iso:
            print("  Sin fecha en lista.json, se omite")
            continue

        fotmob_id = buscar_id_fotmob(home, away, fecha_iso)
        if not fotmob_id:
            print("  No se encontro en FotMob")
            continue

        html_fm = fetch_html(f"https://www.fotmob.com/match/{fotmob_id}")
        ruta_fm = Path("partidos_fotmob") / f"{archivo.stem}_FotMob.html"
        ruta_fm.write_text(html_fm, encoding="utf-8")
        print(f"  Descargado ({len(html_fm)} caracteres)")

        time.sleep(5)

    print("\nEjecutando fotmob_parser.py final...")
    resultado = subprocess.run(["python3", "fotmob_parser.py"], capture_output=True, text=True)
    print(resultado.stdout[-500:])


if __name__ == "__main__":
    main()

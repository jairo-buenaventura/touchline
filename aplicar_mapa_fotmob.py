"""Usa mapa_fotmob_ids.json para descargar y aplicar FotMob a los partidos pendientes."""

import json
import time
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright


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


def main():
    mapa = json.load(open("mapa_fotmob_ids.json"))
    archivos = [a for a in Path("data").glob("*LaLiga*.json")]

    pendientes = []
    for archivo in archivos:
        data = json.load(open(archivo))
        if "fotmob" not in data.get("home", {}):
            home = data["home"]["equipo"]
            away = data["away"]["equipo"]
            clave = f"{home}|||{away}"
            if clave in mapa:
                pendientes.append((archivo.stem, mapa[clave]))

    print(f"Partidos a resolver con el mapa: {len(pendientes)}")

    for i, (nombre_base, fotmob_id) in enumerate(pendientes, start=1):
        print(f"[{i}/{len(pendientes)}] {nombre_base} (FotMob ID: {fotmob_id})")
        html_fm = fetch_html(f"https://www.fotmob.com/match/{fotmob_id}")
        ruta_fm = Path("partidos_fotmob") / f"{nombre_base}_FotMob.html"
        ruta_fm.write_text(html_fm, encoding="utf-8")
        time.sleep(4)

    print("\nEjecutando fotmob_parser.py...")
    resultado = subprocess.run(["python3", "fotmob_parser.py"], capture_output=True, text=True)
    print(resultado.stdout[-500:])


if __name__ == "__main__":
    main()

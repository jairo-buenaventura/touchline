"""Descarga los ultimos 4 partidos pendientes de FotMob usando el mapa de IDs."""

import time
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright


PENDIENTES = [
    ("Barcelona 3-1 Atletico Madrid - LaLiga 2025-2026", "4837401"),
    ("Valencia 2-0 Athletic Club - LaLiga 2025-2026", "4837450"),
    ("Atletico Madrid 5-2 Real Madrid - LaLiga 2025-2026", "4837397"),
    ("Real Sociedad 1-1 Atletico Madrid - LaLiga 2025-2026", "4837371"),
]


def fetch_html(url, wait_ms=15000):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(wait_ms)
        html = page.content()
        browser.close()
    return html


def main():
    for i, (nombre_base, fotmob_id) in enumerate(PENDIENTES, start=1):
        print(f"[{i}/4] {nombre_base} (ID: {fotmob_id})")
        html_fm = fetch_html(f"https://www.fotmob.com/match/{fotmob_id}")
        ruta_fm = Path("partidos_fotmob") / f"{nombre_base}_FotMob.html"
        ruta_fm.write_text(html_fm, encoding="utf-8")
        print(f"  Guardado ({len(html_fm)} caracteres)")
        time.sleep(4)

    print("\nEjecutando fotmob_parser.py...")
    resultado = subprocess.run(["python3", "fotmob_parser.py"], capture_output=True, text=True)
    print(resultado.stdout[-300:])


if __name__ == "__main__":
    main()

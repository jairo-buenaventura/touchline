import json
import time
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright


def fetch_html(url, wait_ms=8000):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
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


def slug_nombre(nombre):
    return nombre.lower().replace(" ", "-")


PENDIENTES = [
    {"match_id": "1914109", "home": "Athletic Club", "away": "Elche", "marcador": "2 : 1"},
    {"match_id": "1914134", "home": "Real Sociedad", "away": "Real Oviedo", "marcador": "3 : 3"},
]

for p in PENDIENTES:
    home, away, match_id = p["home"], p["away"], p["match_id"]
    marcador_guion = p["marcador"].replace(" ", "").replace(":", "-")
    nombre_base = f"{home} {marcador_guion} {away} - LaLiga 2025-2026"

    print(f"Procesando: {home} vs {away}")
    url = f"https://www.whoscored.com/matches/{match_id}/live/spain-laliga-2025-2026-{slug_nombre(home)}-{slug_nombre(away)}"
    html = fetch_html(url)
    ruta_html = Path("partidos_html") / f"{nombre_base}.html"
    ruta_html.write_text(html, encoding="utf-8")

    resultado = subprocess.run(["python3", "parser.py", str(ruta_html)], capture_output=True, text=True)
    print(resultado.stdout)
    if resultado.returncode != 0:
        print("ERROR:", resultado.stderr)

    time.sleep(10)

print("Listo")

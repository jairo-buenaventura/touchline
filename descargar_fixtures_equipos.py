"""Descarga la pagina de fixtures de cada equipo de La Liga."""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright

EQUIPOS = {
    "60": "deportivo-alaves",
    "53": "athletic-club",
    "63": "atletico-madrid",
    "65": "barcelona",
    "62": "celta-vigo",
    "833": "elche",
    "70": "espanyol",
    "819": "getafe",
    "2783": "girona",
    "832": "levante",
    "51": "mallorca",
    "131": "osasuna",
    "64": "rayo-vallecano",
    "54": "real-betis",
    "52": "real-madrid",
    "61": "real-oviedo",
    "68": "real-sociedad",
    "67": "sevilla",
    "55": "valencia",
    "839": "villarreal",
}

PAUSA_SEG = 8


def fetch_html(url, wait_ms=8000):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_timeout(wait_ms)
        html = page.content()
        browser.close()
    return html


def main():
    Path("fixtures_equipos").mkdir(exist_ok=True)

    for i, (team_id, slug) in enumerate(EQUIPOS.items(), start=1):
        ruta_salida = Path("fixtures_equipos") / f"{team_id}_{slug}.html"
        if ruta_salida.exists():
            print(f"[{i}/{len(EQUIPOS)}] {slug} ya existe, se omite")
            continue

        print(f"[{i}/{len(EQUIPOS)}] Descargando {slug}...")
        url = f"https://www.whoscored.com/teams/{team_id}/fixtures/spain-{slug}"
        html = fetch_html(url)
        ruta_salida.write_text(html, encoding="utf-8")
        print(f"   Guardado ({len(html)} caracteres)")

        if i < len(EQUIPOS):
            time.sleep(PAUSA_SEG)

    print("\nListo. Todos los fixtures descargados.")


if __name__ == "__main__":
    main()

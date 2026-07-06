"""Descarga el HTML de un partido de FotMob usando Playwright."""

import sys
from pathlib import Path
from playwright.sync_api import sync_playwright


def fetch_fotmob_html(url, timeout_ms=60000, wait_ms=5000):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, timeout=timeout_ms)
        page.wait_for_timeout(wait_ms)
        html = page.content()
        browser.close()
    return html


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 fetch_fotmob.py <url> <nombre_archivo_salida.html>")
        sys.exit(1)

    url = sys.argv[1]
    nombre_salida = sys.argv[2]

    Path("partidos_fotmob").mkdir(exist_ok=True)
    ruta_salida = Path("partidos_fotmob") / nombre_salida

    print(f"Descargando: {url}")
    html = fetch_fotmob_html(url)
    ruta_salida.write_text(html, encoding="utf-8")
    print(f"Guardado en: {ruta_salida} ({len(html)} caracteres)")

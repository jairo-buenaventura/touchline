"""Identifica y descarga los partidos de WhoScored que faltan para los SIN MATCH de FotMob."""

import json
import re
import time
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
    calendario = json.load(open("calendario_completo_laliga.json"))
    archivos_fotmob = sorted(Path("partidos_fotmob").glob("*LaLiga*_FotMob.html"))

    # Reconstruimos, para cada html de fotmob, el par de equipos y marcador
    faltantes_reales = []
    for archivo in archivos_fotmob:
        nombre = archivo.stem.replace("_FotMob", "")
        m = re.match(r"^(.+?) (\d+)-(\d+) (.+?) - LaLiga", nombre)
        if not m:
            continue
        home, gh, ga, away = m.group(1), m.group(2), m.group(3), m.group(4)

        # Buscamos este partido exacto en el calendario oficial (por marcador)
        for p in calendario:
            if p["home"] == home and p["away"] == away and p["marcador"].replace(" ", "").replace(":", "-") == f"{gh}-{ga}":
                # Verificamos si ya existe el JSON con este mismo marcador
                candidato = Path("data") / f"{home} {gh}-{ga} {away} - LaLiga 2025-2026.json"
                if not candidato.exists():
                    faltantes_reales.append(p)
                break

    print(f"Partidos de WhoScored realmente faltantes: {len(faltantes_reales)}")
    for f in faltantes_reales:
        print(" -", f)

    with open("faltantes_reales_confirmados.json", "w", encoding="utf-8") as file:
        json.dump(faltantes_reales, file, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

"""
Resuelve los partidos de LaLiga que quedaron sin datos de FotMob,
usando las paginas de calendario completo de FotMob (por pagina/jornada).
"""

import json
import re
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


def extraer_ids_de_pagina(html):
    """Devuelve lista de (id, equipo1, equipo2) de una pagina de calendario FotMob."""
    resultados = []
    for m in re.finditer(r'(\d{7})" class="css-[a-z0-9]+-MatchWrapper', html):
        match_id = m.group(1)
        idx = m.start()
        fragmento = html[idx:idx+1500]
        equipos = re.findall(r'TeamName[^"]*">([^<]+)<', fragmento)
        if len(equipos) >= 2:
            resultados.append((match_id, equipos[0], equipos[1]))
    return resultados


def main():
    archivos = [a for a in Path("data").glob("*LaLiga*.json")]
    faltantes = []
    for archivo in archivos:
        data = json.load(open(archivo))
        if "fotmob" not in data.get("home", {}):
            faltantes.append((archivo.stem, data["home"]["equipo"], data["away"]["equipo"]))

    print(f"Partidos pendientes: {len(faltantes)}")

    # Descargamos varias paginas del calendario completo de FotMob (temporada 25/26)
    mapa_ids = {}
    for pagina in range(1, 39):  # hasta 38 jornadas aprox
        url = f"https://www.fotmob.com/leagues/87/fixtures/laliga?group=by-date&season=2025-2026&page={pagina}"
        print(f"Descargando pagina {pagina}...")
        html = fetch_html(url)
        pares = extraer_ids_de_pagina(html)
        for match_id, eq1, eq2 in pares:
            mapa_ids[(eq1, eq2)] = match_id
            mapa_ids[(eq2, eq1)] = match_id
        time.sleep(4)

    print(f"\nTotal de pares equipo1-equipo2 mapeados: {len(mapa_ids)}")

    with open("mapa_fotmob_ids.json", "w", encoding="utf-8") as f:
        json.dump({f"{k[0]}|||{k[1]}": v for k, v in mapa_ids.items()}, f, ensure_ascii=False, indent=2)
    print("Guardado en mapa_fotmob_ids.json")


if __name__ == "__main__":
    main()

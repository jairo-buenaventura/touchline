"""Backfill de varios partidos de La Liga Jornada 35 en un solo lote."""

import time
import subprocess
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

# Lista de partidos a procesar
PARTIDOS = [
    {
        "url": "https://www.whoscored.com/matches/1914201/live/spain-laliga-2025-2026-levante-osasuna",
        "archivo_html": "Levante_3-2_Osasuna_LaLiga_2025-2026.html",
        "home": "Levante",
        "away": "Osasuna",
        "marcador": "3 : 2",
        "estadio": "Ciutat de Valencia",
        "fecha": "2026-05-08",
        "jornada": 35,
    },
    {
        "url": "https://www.whoscored.com/matches/1914215/live/spain-laliga-2025-2026-rayo-vallecano-girona",
        "archivo_html": "Rayo_Vallecano_1-1_Girona_LaLiga_2025-2026.html",
        "home": "Rayo Vallecano",
        "away": "Girona",
        "marcador": "1 : 1",
        "estadio": "Estadio de Vallecas",
        "fecha": "2026-05-11",
        "jornada": 35,
    },
]

PAUSA_ENTRE_PARTIDOS_SEG = 15  # pausa de cortesía para no saturar WhoScored


def fetch_match_html(url, timeout_ms=60000, wait_ms=5000):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, timeout=timeout_ms)
        page.wait_for_timeout(wait_ms)
        html = page.content()
        browser.close()
    return html


def main():
    Path("partidos_html").mkdir(exist_ok=True)
    nuevas_entradas_lista = []

    for i, partido in enumerate(PARTIDOS, start=1):
        print(f"\n[{i}/{len(PARTIDOS)}] Procesando: {partido['home']} vs {partido['away']}")

        # 1. Fetch
        print("  Descargando HTML...")
        html = fetch_match_html(partido["url"])
        ruta_html = Path("partidos_html") / partido["archivo_html"]
        ruta_html.write_text(html, encoding="utf-8")
        print(f"  HTML guardado ({len(html)} caracteres)")

        # 2. Parse (reutilizando parser.py tal cual)
        print("  Ejecutando parser.py...")
        resultado = subprocess.run(
            ["python3", "parser.py", str(ruta_html)],
            capture_output=True, text=True
        )
        print(" ", resultado.stdout.strip())
        if resultado.returncode != 0:
            print("  ERROR:", resultado.stderr.strip())
            continue

        # 3. Preparar entrada para lista.json
        archivo_json = ruta_html.stem + ".json"
        nuevas_entradas_lista.append({
            "archivo": archivo_json,
            "home": partido["home"],
            "away": partido["away"],
            "marcador": partido["marcador"],
            "estadio": partido["estadio"],
            "fecha": partido["fecha"],
            "jornada": partido["jornada"],
        })

        # 4. Pausa de cortesía (excepto en el último)
        if i < len(PARTIDOS):
            print(f"  Esperando {PAUSA_ENTRE_PARTIDOS_SEG}s antes del siguiente...")
            time.sleep(PAUSA_ENTRE_PARTIDOS_SEG)

    # 5. Actualizar lista.json una sola vez al final
    with open("data/lista.json", "r", encoding="utf-8") as f:
        lista = json.load(f)

    lista.extend(nuevas_entradas_lista)

    with open("data/lista.json", "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)

    print(f"\nListo. {len(nuevas_entradas_lista)} partidos agregados al índice.")
    print(f"Total de partidos en lista.json ahora: {len(lista)}")


if __name__ == "__main__":
    main()

"""
procesar_partido.py
Automatiza el flujo completo para un partido nuevo:
WhoScored (fetch) -> parser.py -> busqueda FotMob -> FotMob (fetch) -> fotmob_parser.py -> lista.json

Uso:
    python3 procesar_partido.py
(edita la seccion PARTIDO mas abajo antes de correrlo)
"""

import json
import subprocess
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright


# ==================== EDITA ESTO PARA CADA PARTIDO ====================
PARTIDO = {
    "whoscored_url": "https://www.whoscored.com/matches/1914080/live/spain-laliga-2025-2026-sevilla-athletic-club",
    "home": "Sevilla",
    "away": "Athletic Club",
    "marcador": "2 : 1",
    "estadio": "Ramon Sanchez Pizjuan",
    "fecha": "2026-01-24",
    "jornada": 20,
    "nombre_archivo_base": "Sevilla 2-1 Athletic Club - LaLiga 2025-2026",
}
# ========================================================================


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


def main():
    p = PARTIDO
    if not p["whoscored_url"]:
        print("ERROR: Completa la seccion PARTIDO antes de correr este script.")
        return

    Path("partidos_html").mkdir(exist_ok=True)
    Path("partidos_fotmob").mkdir(exist_ok=True)

    # 1. Fetch WhoScored
    print(f"[1/5] Descargando WhoScored: {p['home']} vs {p['away']}...")
    html_ws = fetch_html(p["whoscored_url"])
    ruta_ws = Path("partidos_html") / f"{p['nombre_archivo_base']}.html"
    ruta_ws.write_text(html_ws, encoding="utf-8")
    print(f"      Guardado ({len(html_ws)} caracteres)")

    # 2. Parser WhoScored
    print("[2/5] Ejecutando parser.py...")
    resultado = subprocess.run(["python3", "parser.py", str(ruta_ws)], capture_output=True, text=True)
    print("     ", resultado.stdout.strip())
    if resultado.returncode != 0:
        print("ERROR:", resultado.stderr.strip())
        return

    # 3. Buscar ID de FotMob
    print("[3/5] Buscando partido en FotMob...")
    fotmob_id = buscar_id_fotmob(p["home"], p["away"], p["fecha"])
    if fotmob_id is None:
        print("      No se encontro el partido en FotMob. Se omite el paso de FotMob.")
    else:
        print(f"      Encontrado, ID: {fotmob_id}")

        # 4. Fetch FotMob
        print("[4/5] Descargando FotMob...")
        html_fm = fetch_html(f"https://www.fotmob.com/match/{fotmob_id}")
        ruta_fm = Path("partidos_fotmob") / f"{p['nombre_archivo_base']}_FotMob.html"
        ruta_fm.write_text(html_fm, encoding="utf-8")
        print(f"      Guardado ({len(html_fm)} caracteres)")

        # 5. Parser FotMob (procesa toda la carpeta)
        print("[5/5] Ejecutando fotmob_parser.py...")
        resultado = subprocess.run(["python3", "fotmob_parser.py"], capture_output=True, text=True)
        print("     ", resultado.stdout.strip()[-300:])

    # Actualizar lista.json
    archivo_json = f"{p['nombre_archivo_base']}.json"
    with open("data/lista.json", "r", encoding="utf-8") as f:
        lista = json.load(f)

    ya_existe = any(item["archivo"] == archivo_json for item in lista)
    if not ya_existe:
        lista.append({
            "archivo": archivo_json,
            "home": p["home"],
            "away": p["away"],
            "marcador": p["marcador"],
            "estadio": p["estadio"],
            "fecha": p["fecha"],
            "jornada": p["jornada"],
        })
        with open("data/lista.json", "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=2)
        print("\nAgregado a lista.json")
    else:
        print("\nYa estaba en lista.json, no se duplico")

    print("Listo.")


if __name__ == "__main__":
    main()

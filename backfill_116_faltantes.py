"""Procesa los 50 partidos de WhoScored que faltan (ya tenemos su FotMob)."""

import time
import subprocess
import json
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


def main():
    import argparse
    parser_args = argparse.ArgumentParser()
    parser_args.add_argument("--inicio", type=int, default=0)
    parser_args.add_argument("--cantidad", type=int, default=30)
    args = parser_args.parse_args()

    todos = json.load(open("faltantes_116.json"))
    faltantes = todos[args.inicio:args.inicio + args.cantidad]
    print(f"Procesando tanda: {args.inicio} a {args.inicio + len(faltantes)} de {len(todos)}")

    exitosos = 0
    errores = []

    for i, p in enumerate(faltantes, start=1):
        home, away, match_id = p["home"], p["away"], p["match_id"]
        marcador_guion = p["marcador"].replace(" ", "").replace(":", "-")
        nombre_base = f"{home} {marcador_guion} {away} - LaLiga 2025-2026"

        print(f"\n[{i}/{len(faltantes)}] {home} vs {away}")
        try:
            url = f"https://www.whoscored.com/matches/{match_id}/live/spain-laliga-2025-2026-{slug_nombre(home)}-{slug_nombre(away)}"
            html = fetch_html(url)
            ruta_html = Path("partidos_html") / f"{nombre_base}.html"
            ruta_html.write_text(html, encoding="utf-8")

            resultado = subprocess.run(
                ["python3", "parser.py", str(ruta_html)],
                capture_output=True, text=True
            )
            if resultado.returncode != 0 or "[OK]" not in resultado.stdout:
                raise RuntimeError(f"parser.py fallo: {resultado.stdout} {resultado.stderr}")

            print(f"  OK: {home} vs {away}")
            exitosos += 1
        except Exception as e:
            print(f"  ERROR: {home} vs {away} -> {e}")
            errores.append({"partido": f"{home} vs {away}", "error": str(e)})

        time.sleep(10)

    print(f"\n=== Resumen ===")
    print(f"Exitosos: {exitosos}/{len(faltantes)}")
    print(f"Errores: {len(errores)}")

    if errores:
        with open("log_errores_50.json", "w", encoding="utf-8") as f:
            json.dump(errores, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

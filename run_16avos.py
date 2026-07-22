# -*- coding: utf-8 -*-
"""
run_16avos.py

Corre mundial_dashboard.generar_reporte para los 7 partidos de 16avos del
Mundial 2026 a los que les falta el CSV de eventos y el dashboard de 4
imágenes. Captura errores por partido sin detener el batch completo.

Uso:
    /Users/jairobuenaventura/Desktop/touchline/.venv_mundial/bin/python3 run_16avos.py
"""

import json
import traceback

from mundial_dashboard import generar_reporte

BASE = "/Users/jairobuenaventura/Documents/Mundial/16avos /"

PARTIDOS = [
    {
        "carpeta": "73. Sudafrica vs Canada 1-2",
        "whoscored": "South Africa 0-1 Canada - FIFA World Cup 2026.html",
        "fotmob": "Sudáfrica vs Canadá - marcador en vivo, alineaciones previstas y estadísticas H2H.html",
    },
    {
        "carpeta": "74. Brasil vs Japon 2-1",
        "whoscored": "Brazil 2-1 Japan - FIFA World Cup 2026.html",
        "fotmob": "Brasil vs Japón - marcador en vivo, alineaciones previstas y estadísticas H2H.html",
    },
    {
        "carpeta": "75. Alemania vs Paraguay 1-1*",
        "whoscored": "Germany 1-1 Paraguay - FIFA World Cup 2026.html",
        "fotmob": "Alemania vs Paraguay - marcador en vivo, alineaciones previstas y estadísticas H2H.html",
    },
    {
        "carpeta": "76. Paises Bajos vs Marruecos 1-1*",
        "whoscored": "Netherlands 1-1 Morocco - FIFA World Cup 2026.html",
        "fotmob": "Países Bajos vs Marruecos - marcador en vivo, alineaciones previstas y estadísticas H2H.html",
    },
    {
        "carpeta": "79. Mexico vs Ecuador 2-0",
        "whoscored": "Mexico 2-0 Ecuador - FIFA World Cup 2026.html",
        "fotmob": "México vs Ecuador - marcador en vivo, alineaciones previstas y estadísticas H2H.html",
    },
    {
        "carpeta": "81. Belgica vs Senegal 3-2",
        "whoscored": "Belgium 3-2 Senegal - FIFA World Cup 2026.html",
        "fotmob": "Bélgica vs Senegal - marcador en vivo, alineaciones previstas y estadísticas H2H.html",
    },
    {
        "carpeta": "88. Colombia vs Ghana 1-0",
        "whoscored": "Colombia 1-0 Ghana - FIFA World Cup 2026.html",
        "fotmob": "Colombia vs Ghana - marcador en vivo, alineaciones previstas y estadísticas H2H.html",
    },
]

GW_LABEL = "Dieciseisavos"


def main(generar_imagenes=True):
    resultados = []
    for p in PARTIDOS:
        carpeta = BASE + p["carpeta"] + "/"
        whoscored_html = carpeta + p["whoscored"]
        fotmob_html = carpeta + p["fotmob"]
        print("\n" + "=" * 90)
        print(f"▶ {p['carpeta']}")
        print("=" * 90)
        try:
            resumen = generar_reporte(
                whoscored_html=whoscored_html,
                fotmob_html=fotmob_html,
                gw_label=GW_LABEL,
                output_dir=carpeta,
                generar_imagenes=generar_imagenes,
            )
            resumen["carpeta"] = p["carpeta"]
            resumen["error"] = None
            resultados.append(resumen)
            print(f"✅ OK: {resumen['hteamName']} {resumen['hgoal_count']}-{resumen['agoal_count']} {resumen['ateamName']}")
        except Exception as e:
            print(f"❌ ERROR en {p['carpeta']}: {e}")
            traceback.print_exc()
            resultados.append({"carpeta": p["carpeta"], "error": str(e)})

    print("\n\n" + "#" * 90)
    print("# RESUMEN FINAL")
    print("#" * 90)
    for r in resultados:
        print(json.dumps(r, ensure_ascii=False, indent=2))

    with open(BASE + "_batch_resumen.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys
    solo_csv = "--solo-csv" in sys.argv
    main(generar_imagenes=not solo_csv)

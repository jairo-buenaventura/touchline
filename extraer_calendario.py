"""
extraer_calendario.py
Extrae todos los partidos de La Liga de un HTML de fixtures de un equipo (WhoScored).

Uso:
    python3 extraer_calendario.py archivo.html
"""

import re
import sys
import json


def extraer_partidos(ruta_html):
    with open(ruta_html, "r", encoding="utf-8") as f:
        contenido = f.read()

    # Cada fila de partido empieza con data-id="..." y termina antes del siguiente data-id
    filas = re.split(r'(?=data-id="\d+")', contenido)

    partidos = []
    for fila in filas:
        m_id = re.match(r'data-id="(\d+)"', fila)
        if not m_id:
            continue

        match_id = m_id.group(1)

        m_torneo = re.search(r'title="([^"]+)" class="tournament-link"', fila)
        torneo = m_torneo.group(1) if m_torneo else None

        # Solo nos interesa LaLiga
        if torneo != "LaLiga":
            continue

        m_fecha = re.search(r'date fourth-col-date[^>]*>([^<]+)<', fila)
        fecha = m_fecha.group(1) if m_fecha else None

        equipos = re.findall(r'team-link[^>]*href="/teams/(\d+)/show/[^"]*">([^<]+)<', fila)
        if len(equipos) < 2:
            continue
        home_id, home_name = equipos[0]
        away_id, away_name = equipos[1]

        m_marcador = re.search(r'result-\d"[^>]*>(\d+ : \d+)<', fila)
        marcador = m_marcador.group(1) if m_marcador else None

        partidos.append({
            "match_id": match_id,
            "fecha": fecha,
            "home": home_name,
            "away": away_name,
            "marcador": marcador,
        })

    return partidos


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 extraer_calendario.py archivo.html")
        sys.exit(1)

    partidos = extraer_partidos(sys.argv[1])
    print(f"Partidos de LaLiga encontrados: {len(partidos)}")
    for p in partidos[:5]:
        print(p)

    with open("calendario_extraido.json", "w", encoding="utf-8") as f:
        json.dump(partidos, f, ensure_ascii=False, indent=2)
    print("Guardado en calendario_extraido.json")

#!/usr/bin/env python3
"""
agregar_ranking_jugador.py
---------------------------
Recorre todos los partidos en data/ y usa el campo "stats_avanzadas" (por
jugador, agregado con id de WhoScored) para construir, por cada
competicion+temporada, un ranking de jugadores con:

  - Totales de temporada (goles, asistencias, tiros, chances creadas, etc.)
  - Tasas por 90 minutos (solo para jugadores que superan un minimo de
    minutos jugados, para que la tasa no se infle con muestras chicas)
  - El percentil de cada jugador en cada categoria, respecto a los demas
    jugadores de esa misma competicion+temporada (totales sin umbral,
    tasas por 90 solo entre los que califican)

Solo lee data/*.json -- no modifica ningun archivo existente. Genera un
JSON por competicion+temporada en data/leaders/.

Uso:
    python3 agregar_ranking_jugador.py
"""
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path("data")
SALIDA_DIR = DATA_DIR / "leaders"
UMBRAL_MINUTOS_POR90 = 450  # ~5 partidos completos, estandar tipo FBref

CATEGORIAS = [
    "goles", "asistencias", "tiros", "tiros_al_arco", "regates_exitosos",
    "chances_creadas", "big_chances_creadas", "chances_open_play",
    "cruces_exitosos", "through_balls_exitosos", "layoffs_exitosos",
    "corners_sacados", "toques_area_rival",
]


def cargar_partidos():
    for f in DATA_DIR.glob("*.json"):
        if f.name in ("lista.json", "jugadores.json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or "home" not in data or "away" not in data:
            continue
        yield data


def acumular():
    """
    clave: (competicion, temporada, jugador_id) -> dict acumulador
    """
    acumulado = {}
    equipos_por_jugador = defaultdict(lambda: defaultdict(int))  # (comp,temp,id) -> {equipo: apariciones}

    for match in cargar_partidos():
        competicion = match.get("competicion")
        temporada = match.get("temporada")
        if not competicion or not temporada:
            continue
        for lado in ("home", "away"):
            equipo_data = match.get(lado) or {}
            equipo_nombre = equipo_data.get("equipo")
            for j in equipo_data.get("stats_avanzadas", []):
                clave = (competicion, temporada, j["id"])
                if clave not in acumulado:
                    acumulado[clave] = {
                        "id": j["id"],
                        "nombre": j["nombre"],
                        "competicion": competicion,
                        "temporada": temporada,
                        "partidos_jugados": 0,
                        "minutos_jugados": 0,
                        "motm": 0,
                        "ratings": [],
                    }
                    for cat in CATEGORIAS:
                        acumulado[clave][cat] = 0

                acc = acumulado[clave]
                # Un jugador que quedo en la banca sin entrar no deberia
                # contar como "partido jugado" (minutos_jugados=0 y sin
                # ninguna accion registrada).
                jugo = j["minutos_jugados"] > 0 or any(j[c] > 0 for c in CATEGORIAS)
                if jugo:
                    acc["partidos_jugados"] += 1
                acc["minutos_jugados"] += j["minutos_jugados"]
                acc["motm"] += 1 if j["motm"] else 0
                if j["rating"] is not None:
                    acc["ratings"].append(j["rating"])
                for cat in CATEGORIAS:
                    acc[cat] += j[cat]

                if equipo_nombre:
                    equipos_por_jugador[clave][equipo_nombre] += 1

    for clave, acc in acumulado.items():
        equipos = equipos_por_jugador[clave]
        acc["equipo"] = max(equipos, key=equipos.get) if equipos else None
        acc["rating_promedio"] = round(sum(acc["ratings"]) / len(acc["ratings"]), 2) if acc["ratings"] else None
        del acc["ratings"]

    return acumulado


def calcular_percentil(valores_ordenados, valor):
    """
    % de jugadores con un valor MENOR O IGUAL al de este jugador, dentro
    del grupo. 100 = el mejor (o empatado con el mejor) de su categoria.
    """
    n = len(valores_ordenados)
    if n <= 1:
        return 100.0
    menores_o_igual = sum(1 for v in valores_ordenados if v <= valor)
    return round(100 * (menores_o_igual - 1) / (n - 1), 1)


# El percentil de cada categoria se calcula solo entre los jugadores que
# registraron algo > 0 en ESA categoria, no contra toda la liga. Motivo:
# en una categoria como goles, la mayoria de la liga (arqueros, centrales)
# tiene 0 -- compararse contra ellos comprime a todos los goleadores
# reales en un rango de percentil casi identico (98-100), haciendo que un
# jugador con 6 goles y otro con 25 aparezcan casi con el mismo "Top X%".
# Filtrando a solo quienes compiten de verdad en esa categoria, la
# distribucion se estira y el percentil vuelve a ser representativo.
# Confirmado con datos reales de LaLiga 25/26 (ver conversacion): Nico
# Williams (6 goles) pasa de "Top 6%" (contra los 747 de la liga) a un
# "Top 16%" mas honesto (contra los 296 que si marcaron).


def construir_rankings(acumulado):
    por_grupo = defaultdict(list)
    for clave, acc in acumulado.items():
        competicion, temporada, _ = clave
        por_grupo[(competicion, temporada)].append(acc)

    SALIDA_DIR.mkdir(exist_ok=True)
    resumen = []

    for (competicion, temporada), jugadores in por_grupo.items():
        calificados_90 = [j for j in jugadores if j["minutos_jugados"] >= UMBRAL_MINUTOS_POR90]

        for cat in CATEGORIAS:
            valores_totales = [j[cat] for j in jugadores]
            valores_totales_participantes = [v for v in valores_totales if v > 0]
            valores_90_calificados = [
                (j[cat] / j["minutos_jugados"]) * 90 for j in calificados_90
            ]
            valores_90_participantes = [v for v in valores_90_calificados if v > 0]

            for j in jugadores:
                if j[cat] > 0:
                    j[f"{cat}_percentil"] = calcular_percentil(valores_totales_participantes, j[cat])

            for j in calificados_90:
                tasa = (j[cat] / j["minutos_jugados"]) * 90
                j[f"{cat}_por90"] = round(tasa, 2)
                if tasa > 0:
                    j[f"{cat}_por90_percentil"] = calcular_percentil(valores_90_participantes, tasa)

        jugadores.sort(key=lambda j: j["goles"], reverse=True)

        nombre_archivo = f"{competicion}_{temporada.replace('/', '-')}.json"
        ruta = SALIDA_DIR / nombre_archivo
        ruta.write_text(json.dumps(jugadores, ensure_ascii=False, indent=2), encoding="utf-8")

        resumen.append({
            "competicion": competicion,
            "temporada": temporada,
            "archivo": nombre_archivo,
            "jugadores": len(jugadores),
            "calificados_por90": len(calificados_90),
        })

    return resumen


def main():
    print("Acumulando stats_avanzadas de todos los partidos en data/...")
    acumulado = acumular()
    print(f"Jugador x competicion x temporada acumulados: {len(acumulado)}")

    resumen = construir_rankings(acumulado)

    ruta_indice = SALIDA_DIR / "indice.json"
    ruta_indice.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nGenerados {len(resumen)} archivos de ranking en '{SALIDA_DIR}/':")
    for r in sorted(resumen, key=lambda r: (r["competicion"], r["temporada"])):
        print(f"  {r['competicion']} {r['temporada']}: {r['jugadores']} jugadores ({r['calificados_por90']} califican para por-90)")


if __name__ == "__main__":
    main()

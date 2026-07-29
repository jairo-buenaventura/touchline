#!/usr/bin/env python3
"""
agregar_temporada_jugador.py
-----------------------------
Recorre todos los partidos en data/ y construye una tabla plana por
jugador-competicion-temporada con métricas agregadas: participación,
acciones por tipo (total/exitosas), pases dados, tiros/goles, recepciones
en zonas de peligro, y posición/equipo más frecuentes.

Solo lee data/ — no modifica ningún archivo de data/ ni ningún script
existente. Genera tabla_jugadores_temporada.csv (y, de paso,
tabla_jugador_partido.csv con el detalle sin agregar, por si se necesita
para depurar).

Limitación honesta: el dataset no trae minutos jugados ni sustituciones,
así que las métricas son totales/promedios por partido con participación
registrada, no normalizadas por 90 minutos. Antes de usar esta tabla para
negociar algo, hay que tenerlo presente (ver PLAN_MEJORAS_CALIDAD_DATOS.md).

Uso:
    python3 agregar_temporada_jugador.py
"""
import json
import os
from collections import defaultdict

import pandas as pd

DATA_DIR = "data"


def procesar_lado(match, lado, filas):
    equipo_data = match.get(lado)
    if not equipo_data:
        return

    equipo = equipo_data.get("equipo")
    otro_lado = "away" if lado == "home" else "home"
    rival = (match.get(otro_lado) or {}).get("equipo")
    competicion = match.get("competicion")
    temporada = match.get("temporada")

    alineacion = equipo_data.get("alineacion") or {}
    formacion = alineacion.get("formacion")
    posiciones = {}
    for j in (alineacion.get("titulares") or []) + (alineacion.get("banca") or []):
        posiciones[j["id"]] = j.get("posicion")

    toques_por_id = {j["id"]: j for j in equipo_data.get("jugadores", [])}

    pases_dados = defaultdict(int)
    for p in equipo_data.get("pases", []):
        pases_dados[p["de"]] += p.get("veces", 0)

    tiros_por_nombre = defaultdict(lambda: {"tiros": 0, "goles": 0, "tiros_al_arco": 0})
    for t in equipo_data.get("tiros", []):
        nombre = t.get("jugador")
        info = tiros_por_nombre[nombre]
        info["tiros"] += 1
        resultado = t.get("resultado")
        if resultado == "Goal":
            info["goles"] += 1
            info["tiros_al_arco"] += 1
        elif resultado == "SavedShot":
            info["tiros_al_arco"] += 1

    recepciones_por_id = {r["id"]: r for r in equipo_data.get("recepcion_pases", [])}

    acciones_por_id = {}
    for a in equipo_data.get("acciones", []):
        conteo = defaultdict(lambda: [0, 0])
        for acc in a.get("acciones", []):
            tipo = acc.get("tipo")
            conteo[tipo][0] += 1
            if acc.get("exitoso"):
                conteo[tipo][1] += 1
        acciones_por_id[a["id"]] = conteo

    todos_ids = set(toques_por_id) | set(recepciones_por_id) | set(acciones_por_id) | set(pases_dados)

    for pid in todos_ids:
        info_toques = toques_por_id.get(pid, {})
        recep = recepciones_por_id.get(pid, {})
        nombre = info_toques.get("nombre") or recep.get("nombre")
        conteo_acc = acciones_por_id.get(pid, {})
        tiros_info = tiros_por_nombre.get(nombre, {"tiros": 0, "goles": 0, "tiros_al_arco": 0})

        fila = {
            "jugador_id": pid,
            "nombre": nombre,
            "equipo": equipo,
            "rival": rival,
            "competicion": competicion,
            "temporada": temporada,
            "posicion": posiciones.get(pid),
            "formacion_equipo": formacion,
            "toques": info_toques.get("toques", 0),
            "x_prom": info_toques.get("x"),
            "y_prom": info_toques.get("y"),
            "pases_dados": pases_dados.get(pid, 0),
            "tiros": tiros_info["tiros"],
            "goles": tiros_info["goles"],
            "tiros_al_arco": tiros_info["tiros_al_arco"],
            "recepciones": len(recep.get("recepciones", [])),
            "pases_clave_recibidos": len(recep.get("pases_clave_recibidos", [])),
            "asistencias_recibidas": len(recep.get("asistencias_recibidas", [])),
            "en_tercio_final": recep.get("en_tercio_final", 0),
            "en_area_rival": recep.get("en_area_rival", 0),
            "cruces_recibidos": recep.get("cruces_recibidos", 0),
        }
        for tipo, (total, exitosas) in conteo_acc.items():
            fila[f"acc_{tipo}_total"] = total
            fila[f"acc_{tipo}_exitosas"] = exitosas
        filas.append(fila)


def construir_tabla():
    filas = []
    archivos = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")]
    errores = 0
    for i, fn in enumerate(archivos):
        try:
            match = json.load(open(os.path.join(DATA_DIR, fn), encoding="utf-8"))
        except Exception:
            errores += 1
            continue
        if not isinstance(match, dict) or "home" not in match or "away" not in match:
            # data/ tiene un par de archivos de metadata (jugadores.json,
            # lista.json) que no son partidos individuales — se ignoran.
            continue
        for lado in ("home", "away"):
            procesar_lado(match, lado, filas)
        if (i + 1) % 1000 == 0:
            print(f"  procesados {i + 1}/{len(archivos)} archivos...")

    print(f"Archivos totales: {len(archivos)}, con error de lectura: {errores}")
    return pd.DataFrame(filas)


def moda(serie):
    m = serie.mode()
    return m.iat[0] if not m.empty else None


def agregar_por_temporada(df):
    cols_suma = [
        c
        for c in df.columns
        if c.startswith("acc_")
        or c
        in (
            "toques",
            "pases_dados",
            "tiros",
            "goles",
            "tiros_al_arco",
            "recepciones",
            "pases_clave_recibidos",
            "asistencias_recibidas",
            "en_tercio_final",
            "en_area_rival",
            "cruces_recibidos",
        )
    ]
    df["acc_total_todas"] = df[[c for c in cols_suma if c.endswith("_total")]].sum(axis=1)
    df["acc_exitosas_todas"] = df[[c for c in cols_suma if c.endswith("_exitosas")]].sum(axis=1)
    cols_suma += ["acc_total_todas", "acc_exitosas_todas"]

    agg = {c: "sum" for c in cols_suma}
    agg.update(
        {
            "equipo": moda,
            "posicion": moda,
            "x_prom": "mean",
            "y_prom": "mean",
            "rival": "count",
        }
    )

    tabla = (
        df.groupby(["jugador_id", "nombre", "competicion", "temporada"])
        .agg(agg)
        .rename(columns={"rival": "partidos_con_participacion"})
        .reset_index()
    )
    tabla["x_prom"] = tabla["x_prom"].round(1)
    tabla["y_prom"] = tabla["y_prom"].round(1)
    return tabla.sort_values(
        ["competicion", "temporada", "toques"], ascending=[True, True, False]
    )


def main():
    df = construir_tabla()
    print(f"Filas jugador-partido construidas: {len(df)}")
    df.to_csv("tabla_jugador_partido.csv", index=False)

    tabla = agregar_por_temporada(df)
    tabla.to_csv("tabla_jugadores_temporada.csv", index=False)
    print(
        f"Guardado tabla_jugadores_temporada.csv con {len(tabla)} filas "
        f"(jugador x competicion x temporada)."
    )


if __name__ == "__main__":
    main()

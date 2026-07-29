#!/usr/bin/env python3
"""
revisar_pendientes_transfermarkt.py
--------------------------------------
Segunda pasada sobre los jugadores que quedaron en confianza_match ==
"necesita_revision_manual" en jugadores_transfermarkt_completo.jsonl.

Esos son casos donde SI encontramos al jugador en Transfermarkt (el nombre
aparece), pero no pudimos verificarlo por equipo -- casi siempre porque se
transfirio, se retiro, quedo sin equipo, o nuestra aparicion es con la
seleccion nacional (Transfermarkt siempre muestra club, nunca selingo)
[ver conversacion]. En la mayoria de esos casos el jugador SI es el
correcto, solo que la verificacion por equipo es demasiado estricta.

Heuristica nueva (mas permisiva pero sin adivinar): si el nombre
normalizado del jugador coincide EXACTO con el nombre normalizado de un
candidato de Transfermarkt, y ese candidato es el UNICO con ese nombre
exacto entre los resultados de la busqueda (sin ambiguedad de "cual de
los tres Aaron Cresswell es"), lo aceptamos como confiable aunque el
equipo no calce.

No modifica jugadores_transfermarkt_completo.jsonl -- escribe un archivo
aparte, jugadores_transfermarkt_revision.jsonl, para que el archivo
principal siga siendo la fuente de verdad de la corrida original.

Uso:
    python3 revisar_pendientes_transfermarkt.py            # todos los pendientes
    python3 revisar_pendientes_transfermarkt.py --limite 100  # muestra chica
"""
import argparse
import json
import time
import unicodedata
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from enriquecer_transfermarkt import BASE, HEADERS, extraer_perfil, extraer_lesiones, PAUSA_ENTRE_REQUESTS
from enriquecer_transfermarkt_completo import normalizar_equipo  # noqa: F401 (reuso futuro)

ENTRADA_PRINCIPAL = Path("jugadores_transfermarkt_completo.jsonl")
SALIDA = Path("jugadores_transfermarkt_revision.jsonl")


def normalizar_nombre(nombre):
    if not nombre:
        return ""
    base = nombre.strip().lower()
    base = "".join(c for c in unicodedata.normalize("NFD", base) if unicodedata.category(c) != "Mn")
    return " ".join(base.split())


def buscar_candidatos(nombre):
    url = f"{BASE}/schnellsuche/ergebnis/schnellsuche?query={urllib.parse.quote(nombre)}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    tabla = soup.select_one("table.items")
    if not tabla:
        return []
    candidatos = []
    for tr in tabla.select("tbody tr"):
        a = tr.select_one("td.hauptlink a[href*='/profil/spieler/']")
        if not a:
            continue
        img = tr.select_one("td img.tiny_wappen")
        equipo = img.get("alt") if img else None
        candidatos.append((a.get("href"), a.get_text(strip=True), equipo))
    return candidatos


def cargar_pendientes():
    pendientes = []
    with ENTRADA_PRINCIPAL.open(encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            d = json.loads(linea)
            if d.get("confianza_match") == "necesita_revision_manual":
                pendientes.append(d)
    return pendientes


def cargar_ids_ya_revisados():
    if not SALIDA.exists():
        return set()
    ids = set()
    with SALIDA.open(encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                ids.add(json.loads(linea)["jugador_id"])
            except Exception:
                continue
    return ids


def procesar(pendiente):
    fila = {"jugador_id": pendiente["jugador_id"], "nombre": pendiente["nombre"], "equipo": pendiente.get("equipo")}
    nombre_norm = normalizar_nombre(pendiente["nombre"])
    try:
        candidatos = buscar_candidatos(pendiente["nombre"])
        exactos_por_href = {}
        for c in candidatos:
            if normalizar_nombre(c[1]) == nombre_norm:
                # Transfermarkt a veces repite la misma fila (mismo href) dos
                # veces en los resultados -- una con escudo de equipo y otra
                # sin el. Deduplicar por href antes de juzgar ambiguedad.
                exactos_por_href.setdefault(c[0], c)
        exactos = list(exactos_por_href.values())

        if len(exactos) != 1:
            fila["confianza_match"] = "necesita_revision_manual"
            fila["motivo_no_resuelto"] = "sin_candidatos_exactos" if not exactos else "nombre_ambiguo"
            fila["candidatos_exactos_encontrados"] = len(exactos)
            return fila

        href, nom_tm, equipo_tm = exactos[0]
        fila["confianza_match"] = "alta"
        fila["metodo_match"] = "nombre_exacto_sin_ambiguedad"
        fila["equipo_transfermarkt"] = equipo_tm

        time.sleep(PAUSA_ENTRE_REQUESTS)
        fila.update(extraer_perfil(href))
        fila["transfermarkt_url"] = BASE + href

        time.sleep(PAUSA_ENTRE_REQUESTS)
        resumen_lesiones, detalle_lesiones = extraer_lesiones(href)
        fila.update(resumen_lesiones)
        fila["lesiones_detalle"] = detalle_lesiones
    except Exception as e:
        fila["confianza_match"] = "error"
        fila["error"] = str(e)
    return fila


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=None, help="cortar antes, para pruebas")
    args = ap.parse_args()

    pendientes = cargar_pendientes()
    ya_revisados = cargar_ids_ya_revisados()
    faltan = [p for p in pendientes if p["jugador_id"] not in ya_revisados]
    if args.limite:
        faltan = faltan[: args.limite]

    print(f"Pendientes totales (necesita_revision_manual): {len(pendientes)}")
    print(f"Ya revisados en corridas previas: {len(ya_revisados)}")
    print(f"A procesar ahora: {len(faltan)}")

    resueltos = 0
    sin_resolver = 0
    with SALIDA.open("a", encoding="utf-8") as out:
        for i, p in enumerate(faltan, 1):
            fila = procesar(p)
            out.write(json.dumps(fila, ensure_ascii=False) + "\n")
            out.flush()

            if fila["confianza_match"] == "alta":
                resueltos += 1
            else:
                sin_resolver += 1

            if i % 25 == 0 or i == len(faltan):
                print(f"[{i}/{len(faltan)}] resueltos={resueltos} sin_resolver={sin_resolver}")

            time.sleep(PAUSA_ENTRE_REQUESTS)

    print(f"\nListo esta corrida: {resueltos} resueltos por nombre exacto, {sin_resolver} siguen sin verificar.")
    print(f"Guardado incremental en '{SALIDA}'.")


if __name__ == "__main__":
    main()

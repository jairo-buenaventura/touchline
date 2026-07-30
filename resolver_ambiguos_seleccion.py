#!/usr/bin/env python3
"""
resolver_ambiguos_seleccion.py
---------------------------------
Tercera pasada sobre los pendientes de Transfermarkt: solo ataca el
subgrupo de "necesita_revision_manual" / "nombre_ambiguo" cuyo UNICO
equipo conocido en nuestros datos es una seleccion nacional (ej. el
jugador solo aparecio para nosotros en un partido de "Wales" o
"Senegal", nunca con un club). Para esos, la comparacion de club de las
pasadas anteriores es inutil (Transfermarkt nunca muestra la seleccion
en los resultados de busqueda, solo el club) -- pero el PERFIL real de
cada candidato con nombre exacto SI lista la nacionalidad (Citizenship),
asi que cruzamos eso.

Sigue sin adivinar: solo se acepta si, entre los candidatos de nombre
exacto, HAY UNO Y SOLO UNO cuya nacionalidad coincide con la seleccion
que tenemos registrada. Si dos candidatos distintos comparten nombre Y
nacionalidad (dos jugadores reales homonimos del mismo pais), se deja
sin resolver -- no hay forma segura de diferenciarlos con los datos que
tenemos (sin fecha de nacimiento ni foto).

Escribe en jugadores_transfermarkt_revision.jsonl (mismo archivo que la
segunda pasada), agregando filas nuevas para los que se logren resolver
-- agregar_perfiles_jugador.py ya prioriza la ultima ocurrencia por id.

Uso:
    python3 resolver_ambiguos_seleccion.py
"""
import json
import time
import unicodedata
from pathlib import Path

from enriquecer_transfermarkt import PAUSA_ENTRE_REQUESTS, extraer_perfil, extraer_lesiones, BASE
from enriquecer_transfermarkt_completo import _buscar_candidatos_transfermarkt, cargar_universo_jugadores

ENTRADA = Path("jugadores_transfermarkt_revision.jsonl")
SALIDA = ENTRADA  # se agrega al mismo archivo

PAISES = {
    "wales", "senegal", "uzbekistan", "iran", "england", "ireland", "scotland",
    "france", "spain", "germany", "italy", "portugal", "argentina", "brazil",
    "mexico", "usa", "nigeria", "ghana", "morocco", "algeria", "tunisia",
    "egypt", "cameroon", "ivory coast", "netherlands", "belgium", "croatia",
    "serbia", "poland", "ukraine", "denmark", "sweden", "norway", "finland",
    "iceland", "switzerland", "austria", "turkey", "greece", "japan",
    "south korea", "australia", "canada", "colombia", "chile", "peru",
    "uruguay", "paraguay", "ecuador", "venezuela", "costa rica", "panama",
    "jamaica", "qatar", "saudi arabia", "uae", "jordan", "iraq",
}


def normalizar_nombre(nombre):
    base = nombre.strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", base) if unicodedata.category(c) != "Mn")


def cargar_pendientes_seleccion():
    pendientes = []
    with ENTRADA.open(encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            d = json.loads(linea)
            if (
                d.get("confianza_match") == "necesita_revision_manual"
                and d.get("motivo_no_resuelto") == "nombre_ambiguo"
                and (d.get("equipo") or "").strip().lower() in PAISES
            ):
                pendientes.append(d)
    return pendientes


def resolver(pendiente):
    nombre = pendiente["nombre"]
    pais_esperado = pendiente["equipo"].strip().lower()
    candidatos = _buscar_candidatos_transfermarkt(nombre)
    nombre_norm = normalizar_nombre(nombre)

    exactos = {}
    for href, nom_tm, _equipo in candidatos:
        if normalizar_nombre(nom_tm) == nombre_norm:
            exactos.setdefault(href, nom_tm)

    matches = []
    for href in exactos:
        time.sleep(PAUSA_ENTRE_REQUESTS)
        perfil = extraer_perfil(href)
        nacionalidad = (perfil.get("nacionalidad") or "").lower()
        if pais_esperado in nacionalidad:
            matches.append((href, perfil))

    fila = {"jugador_id": pendiente["jugador_id"], "nombre": nombre, "equipo": pendiente.get("equipo")}
    if len(matches) != 1:
        fila["confianza_match"] = "necesita_revision_manual"
        fila["motivo_no_resuelto"] = "nombre_ambiguo"
        fila["candidatos_nacionalidad_coincidente"] = len(matches)
        return fila, False

    href, perfil = matches[0]
    fila["confianza_match"] = "alta"
    fila["metodo_match"] = "nombre_exacto_y_nacionalidad"
    fila.update(perfil)
    fila["transfermarkt_url"] = BASE + href

    time.sleep(PAUSA_ENTRE_REQUESTS)
    resumen_lesiones, detalle_lesiones = extraer_lesiones(href)
    fila.update(resumen_lesiones)
    fila["lesiones_detalle"] = detalle_lesiones
    return fila, True


def main():
    pendientes = cargar_pendientes_seleccion()
    print(f"Pendientes con seleccion nacional como unico equipo: {len(pendientes)}")

    resueltos = 0
    with SALIDA.open("a", encoding="utf-8") as out:
        for i, p in enumerate(pendientes, 1):
            try:
                fila, ok = resolver(p)
            except Exception as e:
                fila = {"jugador_id": p["jugador_id"], "nombre": p["nombre"], "confianza_match": "error", "error": str(e)}
                ok = False
            out.write(json.dumps(fila, ensure_ascii=False) + "\n")
            out.flush()
            if ok:
                resueltos += 1
            if i % 10 == 0 or i == len(pendientes):
                print(f"[{i}/{len(pendientes)}] resueltos={resueltos}")
            time.sleep(PAUSA_ENTRE_REQUESTS)

    print(f"\nListo: {resueltos} de {len(pendientes)} resueltos por nombre exacto + nacionalidad.")


if __name__ == "__main__":
    main()

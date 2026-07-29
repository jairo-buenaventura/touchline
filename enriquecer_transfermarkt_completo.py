#!/usr/bin/env python3
"""
enriquecer_transfermarkt_completo.py
--------------------------------------
Version a escala completa de enriquecer_transfermarkt.py (que sigue
intacto como prueba de concepto validada con una muestra de 8 jugadores
-- este script reutiliza sus funciones, no las duplica).

Recorre TODOS los jugadores unicos de data/jugadores.json (no solo una
muestra) y resuelve su perfil de Transfermarkt (edad, valor de mercado,
fin de contrato, agente) + historial de lesiones.

Disenado para correr muchas horas sin supervision:

  - REANUDABLE: escribe cada jugador en cuanto lo procesa (JSONL, una
    linea por jugador), no acumula nada en memoria hasta el final. Si se
    corta a mitad de camino, correrlo de nuevo salta automaticamente los
    ids que ya aparecen en la salida.
  - CONFIANZA DEL MATCH marcada explicitamente en cada fila
    (alta/necesita_revision_manual/sin_match/error). Los datos de perfil
    (edad, valor de mercado, lesiones) SOLO se completan cuando el match
    quedo verificado por equipo (confianza "alta") -- si no se pudo
    verificar, la fila queda con los campos de perfil vacios y solo un
    candidato sugerido para revision humana, para que nunca se mezcle un
    dato adivinado con uno confirmado.

Uso:
    python3 enriquecer_transfermarkt_completo.py
    python3 enriquecer_transfermarkt_completo.py --limite 500   # cortar antes, para pruebas
"""
import argparse
import json
import re
import time
import unicodedata
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from enriquecer_transfermarkt import BASE, HEADERS, extraer_perfil, extraer_lesiones, PAUSA_ENTRE_REQUESTS

SALIDA = Path("jugadores_transfermarkt_completo.jsonl")

SUFIJOS_CLUB = {"fc", "cf", "afc", "sc", "ac", "cd", "ud", "rc", "ca", "sad", "1", "1846", "1899", "1900", "1904", "1905", "1909", "1913"}


REEMPLAZOS_BUSQUEDA = {"ø": "o", "Ø": "O", "æ": "ae", "Æ": "Ae", "ð": "d", "Ð": "D", "þ": "th", "Þ": "Th"}


def quitar_diacriticos_busqueda(nombre):
    """
    Solo para ampliar la CONSULTA de busqueda -- el buscador de
    Transfermarkt indexa "Gytkjaer", no "Gytkjær", asi que un nombre con
    letras nordicas (ø/æ/ð/þ) devuelve "sin_resultados" aunque el jugador
    si tenga perfil. No afecta la verificacion posterior por equipo/nombre
    exacto, que sigue igual de estricta.
    """
    base = nombre
    for original, reemplazo in REEMPLAZOS_BUSQUEDA.items():
        base = base.replace(original, reemplazo)
    base = "".join(c for c in unicodedata.normalize("NFD", base) if unicodedata.category(c) != "Mn")
    return base


def normalizar_equipo(nombre):
    """
    Normaliza un nombre de club para comparar WhoScored vs Transfermarkt
    (que a veces difieren en sufijos tipo "FC"/"CF", numeros de fundacion,
    o acentos): quita acentos, minusculas, y descarta palabras sueltas que
    son solo sufijos genericos de club.
    """
    if not nombre:
        return ""
    base = nombre.strip().lower()
    base = "".join(c for c in unicodedata.normalize("NFD", base) if unicodedata.category(c) != "Mn")
    palabras = [p for p in re.split(r"[^a-z0-9]+", base) if p and p not in SUFIJOS_CLUB]
    return " ".join(palabras)


def _buscar_candidatos_transfermarkt(nombre):
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


def buscar_jugador_verificado(nombre, equipos_esperados=None):
    """
    Igual que buscar_jugador() de enriquecer_transfermarkt.py, pero con
    comparacion de equipo normalizada (mas tolerante a diferencias de
    formato) y SIN el fallback de "primer resultado sin verificar" -- si
    no se puede confirmar por equipo, se devuelve None explicitamente en
    vez de adivinar, porque estos datos tienen que ser verificables.

    equipos_esperados: coleccion de TODOS los equipos con los que jugo
    ese jugador en nuestros datos (no solo el mas reciente) -- un
    jugador puede tener su ultima aparicion con la seleccion nacional
    (ej. un Mundial) mientras Transfermarkt muestra su club, o puede
    haber estado a prestamo en un club distinto al que muestra
    Transfermarkt como "actual". Probar contra todo el historial reduce
    falsos negativos sin bajar el estandar de verificacion.
    """
    candidatos = _buscar_candidatos_transfermarkt(nombre)
    if not candidatos:
        # Transfermarkt indexa "Gytkjaer", no "Gytkjær" -- si el nombre
        # tiene letras nordicas (o cualquier acento) y la busqueda exacta
        # no devolvio nada, reintentamos solo con la consulta ampliada.
        # La verificacion posterior (equipo/nombre exacto) sigue igual.
        nombre_normalizado = quitar_diacriticos_busqueda(nombre)
        if nombre_normalizado != nombre:
            candidatos = _buscar_candidatos_transfermarkt(nombre_normalizado)
        if not candidatos:
            return None, "sin_resultados", None

    equipos_norm_esperados = {normalizar_equipo(e) for e in (equipos_esperados or [])}
    equipos_norm_esperados.discard("")
    if equipos_norm_esperados:
        for href, nom_tm, equipo in candidatos:
            equipo_norm_tm = normalizar_equipo(equipo)
            if not equipo_norm_tm:
                continue
            for equipo_norm_esperado in equipos_norm_esperados:
                if equipo_norm_esperado in equipo_norm_tm or equipo_norm_tm in equipo_norm_esperado:
                    return href, "match_por_equipo", nom_tm

    # No hay match verificado por equipo: no adivinamos. Se guarda el
    # primer candidato solo como referencia para revision manual, no
    # como dato confirmado.
    return None, "sin_verificar", candidatos[0]


def cargar_universo_jugadores():
    """
    Un jugador por id, con TODOS los equipos con los que aparece en
    nuestros datos (no solo el mas reciente) para maximizar las chances
    de verificar el match contra Transfermarkt sin bajar el estandar de
    verificacion (ver comentario en buscar_jugador_verificado). El
    "equipo" (singular) mas reciente se guarda aparte solo para mostrar
    en el output, no para el matching.
    """
    jugadores = json.loads(Path("data/jugadores.json").read_text(encoding="utf-8"))
    universo = []
    for j in jugadores:
        apariciones = j.get("apariciones") or []
        equipos_todos = sorted({a["equipo"] for a in apariciones if a.get("equipo")})
        equipo_reciente = None
        if apariciones:
            con_fecha = [a for a in apariciones if a.get("fecha")]
            if con_fecha:
                equipo_reciente = max(con_fecha, key=lambda a: a["fecha"]).get("equipo")
            else:
                equipo_reciente = apariciones[-1].get("equipo")
        universo.append({
            "id": j["id"],
            "nombre": j["nombre"],
            "equipo": equipo_reciente,
            "equipos_todos": equipos_todos,
        })
    return universo


def cargar_ids_ya_procesados():
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


def procesar_jugador(j):
    fila = {"jugador_id": j["id"], "nombre": j["nombre"], "equipo": j["equipo"]}
    try:
        href, metodo_match, candidato_sin_verificar = buscar_jugador_verificado(j["nombre"], equipos_esperados=j.get("equipos_todos"))

        if not href:
            # Sin verificacion por equipo: NO se completan campos de
            # perfil/lesiones con un dato adivinado. Se deja constancia
            # del mejor candidato encontrado para revision manual, sin
            # tratarlo como confirmado.
            fila["confianza_match"] = "sin_match" if metodo_match == "sin_resultados" else "necesita_revision_manual"
            if candidato_sin_verificar:
                href_cand, nom_cand, equipo_cand = candidato_sin_verificar
                fila["candidato_sugerido_nombre"] = nom_cand
                fila["candidato_sugerido_equipo"] = equipo_cand
                fila["candidato_sugerido_url"] = "https://www.transfermarkt.com" + href_cand
            return fila

        fila["confianza_match"] = "alta"
        fila["metodo_match"] = metodo_match

        time.sleep(PAUSA_ENTRE_REQUESTS)
        fila.update(extraer_perfil(href))
        fila["transfermarkt_url"] = "https://www.transfermarkt.com" + href

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
    ap.add_argument("--limite", type=int, default=None, help="procesar como maximo N jugadores nuevos en esta corrida")
    args = ap.parse_args()

    universo = cargar_universo_jugadores()
    ya_procesados = cargar_ids_ya_procesados()
    pendientes = [j for j in universo if j["id"] not in ya_procesados]

    print(f"Universo total: {len(universo)} jugadores | Ya procesados: {len(ya_procesados)} | Pendientes: {len(pendientes)}")

    if args.limite:
        pendientes = pendientes[: args.limite]
        print(f"(Corte de esta corrida: {len(pendientes)} jugadores)")

    exitosos = 0
    alta_confianza = 0
    necesita_revision = 0
    sin_match = 0
    errores = 0

    with SALIDA.open("a", encoding="utf-8") as f_out:
        for i, j in enumerate(pendientes, 1):
            fila = procesar_jugador(j)
            f_out.write(json.dumps(fila, ensure_ascii=False) + "\n")
            f_out.flush()

            conf = fila.get("confianza_match")
            if conf == "alta":
                alta_confianza += 1
            elif conf == "necesita_revision_manual":
                necesita_revision += 1
            elif conf == "sin_match":
                sin_match += 1
            elif conf == "error":
                errores += 1
            exitosos += 1

            if i % 25 == 0 or i == len(pendientes):
                print(f"[{i}/{len(pendientes)}] alta={alta_confianza} necesita_revision={necesita_revision} sin_match={sin_match} error={errores}")

            time.sleep(PAUSA_ENTRE_REQUESTS)

    print(f"\nListo esta corrida: {exitosos} jugadores procesados.")
    print(f"  Confianza alta (match por equipo, datos completos y confiables): {alta_confianza}")
    print(f"  Necesita revision manual (encontramos un candidato pero SIN verificar equipo -- sin datos de perfil llenados): {necesita_revision}")
    print(f"  Sin match en Transfermarkt: {sin_match}")
    print(f"  Errores: {errores}")
    print(f"Guardado incremental en '{SALIDA}'.")


if __name__ == "__main__":
    main()

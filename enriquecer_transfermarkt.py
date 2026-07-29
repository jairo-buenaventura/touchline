#!/usr/bin/env python3
"""
enriquecer_transfermarkt.py
-----------------------------
Prueba de concepto del punto 6 del plan de mejoras: para una MUESTRA de
jugadores de tabla_jugadores_temporada.csv, resuelve su perfil en
Transfermarkt (edad, nacionalidad, valor de mercado, fin de contrato,
agente) y su historial de lesiones reciente.

Por qué es solo una muestra y no todo el dataset:
- tabla_jugadores_temporada.csv tiene ~13,000 filas jugador-competicion-
  temporada (varios miles de jugadores únicos). Cruzar todo eso contra
  Transfermarkt de una sola pasada sería scraping masivo, lento y poco
  respetuoso con el sitio (aquí sí hay pausa entre requests a propósito).
- Este script demuestra que el mapeo de identidad (nombre -> perfil real de
  Transfermarkt) funciona con datos reales, para decidir si vale la pena
  escalarlo y a qué ritmo.

Transfermarkt no bloquea peticiones simples (a diferencia de WhoScored, que
sí necesita Playwright) — con un User-Agent normal responde 200 directo.

No modifica data/ ni tabla_jugadores_temporada.csv — solo lee y genera
jugadores_transfermarkt_muestra.csv.

Uso:
    python3 enriquecer_transfermarkt.py           # ~20 jugadores (top por competición)
    python3 enriquecer_transfermarkt.py --n 8     # muestra más chica
"""
import argparse
import re
import time
import urllib.parse

import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
BASE = "https://www.transfermarkt.com"
PAUSA_ENTRE_REQUESTS = 1.5  # segundos — trato de no golpear el sitio


def buscar_jugador(nombre, equipo_esperado=None):
    url = f"{BASE}/schnellsuche/ergebnis/schnellsuche?query={urllib.parse.quote(nombre)}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    tabla = soup.select_one("table.items")
    if not tabla:
        return None, "sin_resultados"

    candidatos = []
    for tr in tabla.select("tbody tr"):
        a = tr.select_one("td.hauptlink a[href*='/profil/spieler/']")
        if not a:
            continue
        img = tr.select_one("td img.tiny_wappen")
        equipo = img.get("alt") if img else None
        candidatos.append((a.get("href"), a.get_text(strip=True), equipo))

    if not candidatos:
        return None, "sin_resultados"

    if equipo_esperado:
        for href, _nom, equipo in candidatos:
            if equipo and equipo_esperado.lower() in equipo.lower():
                return href, "match_por_equipo"

    return candidatos[0][0], "primer_resultado_sin_verificar_equipo"


def extraer_perfil(href):
    r = requests.get(BASE + href, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    datos = {}
    # Ojo: Transfermarkt no usa siempre la misma etiqueta HTML para este bloque
    # (a veces es <li class="data-header__label">, a veces <span> con la misma
    # clase) — se selecciona por clase CSS, no por tag, para no perder datos.
    for elem in soup.select(".data-header__label"):
        span = elem.select_one(".data-header__content")
        texto = span.get_text(" ", strip=True) if span else None
        etiqueta = elem.get_text(" ", strip=True)
        if etiqueta.startswith("Date of birth"):
            m = re.search(r"\((\d+)\)", texto or "")
            datos["edad"] = int(m.group(1)) if m else None
            datos["fecha_nacimiento"] = (texto or "").split(" (")[0]
        elif etiqueta.startswith("Citizenship"):
            datos["nacionalidad"] = texto
        elif etiqueta.startswith("Height"):
            datos["altura"] = texto
        elif etiqueta.startswith("Agent"):
            datos["agente"] = texto
        elif etiqueta.startswith("Contract expires"):
            datos["fin_contrato"] = texto
        elif etiqueta.startswith("Joined"):
            datos["fecha_llegada_club_actual"] = texto

    mv = soup.select_one(".data-header__market-value-wrapper")
    if mv:
        datos["valor_mercado_texto"] = mv.get_text(" ", strip=True).split("Last update")[0].strip()

    return datos


def extraer_lesiones(href, filas_max=18):
    """Devuelve el resumen (conteo, dias totales) Y el detalle fila por fila
    (temporada, tipo de lesion, desde/hasta, dias de baja, partidos perdidos)
    tal cual lo publica Transfermarkt en /verletzungen/."""
    href_lesiones = href.replace("/profil/spieler/", "/verletzungen/spieler/")
    r = requests.get(BASE + href_lesiones, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    tabla = soup.select_one("table.items")
    if not tabla:
        return {"lesiones_registradas": 0, "dias_baja_totales": 0}, []

    dias_total = 0
    detalle = []
    for tr in tabla.select("tbody tr")[:filas_max]:
        celdas = [td.get_text(" ", strip=True) for td in tr.select("td")]
        if len(celdas) < 6:
            continue
        temporada, tipo, desde, hasta, dias_texto, partidos_perdidos = celdas[:6]
        m = re.search(r"(\d+)", dias_texto)
        dias_num = int(m.group(1)) if m else 0
        dias_total += dias_num
        detalle.append(
            {
                "temporada_lesion": temporada,
                "tipo_lesion": tipo,
                "desde": desde,
                "hasta": hasta,
                "dias_baja": dias_num,
                "partidos_perdidos": partidos_perdidos,
            }
        )

    resumen = {"lesiones_registradas": len(detalle), "dias_baja_totales": dias_total}
    return resumen, detalle


def seleccionar_muestra(n):
    df = pd.read_csv("tabla_jugadores_temporada.csv")
    ultima_por_comp = df.groupby("competicion")["temporada"].max()
    partes = []
    for comp, temp in ultima_por_comp.items():
        sub = df[(df["competicion"] == comp) & (df["temporada"] == temp)]
        partes.append(sub.sort_values("toques", ascending=False).head(3))
    muestra = pd.concat(partes).drop_duplicates(subset=["jugador_id"])
    return muestra.head(n) if n else muestra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20, help="cuántos jugadores enriquecer (prueba de concepto)")
    args = ap.parse_args()

    muestra = seleccionar_muestra(args.n)
    print(f"Enriqueciendo {len(muestra)} jugadores (muestra, no el dataset completo)...")

    filas = []
    filas_lesiones = []
    for _, row in muestra.iterrows():
        nombre, equipo = row["nombre"], row["equipo"]
        print(f"  {nombre} ({equipo})...")
        fila = {"jugador_id": row["jugador_id"], "nombre": nombre, "equipo": equipo}
        try:
            href, metodo_match = buscar_jugador(nombre, equipo_esperado=equipo)
            fila["match"] = metodo_match
            if href:
                time.sleep(PAUSA_ENTRE_REQUESTS)
                fila.update(extraer_perfil(href))
                fila["transfermarkt_url"] = BASE + href
                time.sleep(PAUSA_ENTRE_REQUESTS)
                resumen_lesiones, detalle_lesiones = extraer_lesiones(href)
                fila.update(resumen_lesiones)
                for d in detalle_lesiones:
                    filas_lesiones.append({"jugador_id": row["jugador_id"], "nombre": nombre, **d})
        except Exception as e:
            fila["match"] = f"error: {e}"
        filas.append(fila)
        time.sleep(PAUSA_ENTRE_REQUESTS)

    out = pd.DataFrame(filas)
    out.to_csv("jugadores_transfermarkt_muestra.csv", index=False)
    print(f"\nGuardado jugadores_transfermarkt_muestra.csv con {len(out)} filas.")

    out_lesiones = pd.DataFrame(filas_lesiones)
    out_lesiones.to_csv("lesiones_detalle_muestra.csv", index=False)
    print(f"Guardado lesiones_detalle_muestra.csv con {len(out_lesiones)} filas (una por lesion).")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
agregar_perfiles_jugador.py
------------------------------
Convierte jugadores_transfermarkt_completo.jsonl (+ jugadores_transfermarkt_revision.jsonl
si existe) en data/perfiles_jugadores.json: un diccionario jugador_id -> perfil,
listo para que index.html lo sirva sin exponer nada del pipeline de scraping.

Solo incluye jugadores con confianza_match == "alta" -- nunca se muestra un
perfil sin verificar por equipo (o por nombre exacto sin ambiguedad, para los
resueltos en la segunda pasada). Si un jugador aparece en ambos archivos, gana
la version de jugadores_transfermarkt_completo.jsonl (la corrida principal).

No modifica ninguno de los dos archivos de entrada.

Uso:
    python3 agregar_perfiles_jugador.py
"""
import json
from pathlib import Path

from traduccion_lesiones import traducir_lesion

ENTRADAS = [
    Path("jugadores_transfermarkt_completo.jsonl"),
    Path("jugadores_transfermarkt_revision.jsonl"),
]
SALIDA = Path("data/perfiles_jugadores.json")

CAMPOS_PERFIL = [
    "edad", "fecha_nacimiento", "nacionalidad", "altura", "agente",
    "fecha_llegada_club_actual", "fin_contrato", "valor_mercado_texto",
    "transfermarkt_url", "lesiones_registradas", "dias_baja_totales",
    "lesiones_detalle",
]


def cargar_perfiles():
    perfiles = {}
    for ruta in ENTRADAS:
        if not ruta.exists():
            continue
        with ruta.open(encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                d = json.loads(linea)
                if d.get("confianza_match") != "alta":
                    continue
                jid = str(d["jugador_id"])
                if jid in perfiles and ruta.name == "jugadores_transfermarkt_revision.jsonl":
                    continue  # la corrida principal ya tiene prioridad
                perfil = {campo: d.get(campo) for campo in CAMPOS_PERFIL if d.get(campo) is not None}
                for lesion in perfil.get("lesiones_detalle") or []:
                    lesion["tipo_lesion_es"] = traducir_lesion(lesion.get("tipo_lesion"))
                perfiles[jid] = perfil
    return perfiles


def main():
    perfiles = cargar_perfiles()
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text(json.dumps(perfiles, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generados {len(perfiles)} perfiles verificados en '{SALIDA}'.")


if __name__ == "__main__":
    main()

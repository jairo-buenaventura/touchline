#!/usr/bin/env python3
"""
actualizar_todo.py
-------------------
Punto de entrada UNICO para "procesar todo lo nuevo en data/" de punta a
punta: parser.py (que ya reescribe cada JSON SIN el bloque "fotmob") ->
reinyeccion de FotMob -> verificacion de que no quedo ningun partido sin
FotMob -> corners/leaders.

Por que existe: parser.py reescribe cada JSON de partido desde cero en
cada corrida y depende de un paso SEPARADO (fotmob_parser.actualizar_fotmob)
para reponer el bloque "fotmob". Si algo corta el proceso entre esos dos
pasos (la sesion se reinicia, se mata el proceso, se corre uno sin el
otro a mano), TODO data/ queda sin FotMob en silencio -- paso real,
detectado el 2026-10-11, que dejo 8706/9870 partidos sin FotMob porque
una corrida de parser.py se corto antes de llegar a actualizar_fotmob().

Esto nunca debe volver a pasar en silencio: este script corre los pasos
en el orden correcto, SIEMPRE termina con una verificacion dura (si queda
un solo partido sin FotMob que debería tenerlo, termina con exit code 1
y lo dice explicito) y recien despues corre corners/leaders. No hace
commit ni push -- eso es responsabilidad de quien invoca este script
(la skill descargar-whoscored o la tarea automatizada).

Uso:
    python3 actualizar_todo.py
"""
import subprocess
import sys
import json
from pathlib import Path

import fotmob_parser


def correr(cmd, descripcion):
    print(f"\n{'='*70}\n{descripcion}\n{'='*70}")
    resultado = subprocess.run(cmd, cwd=Path(__file__).parent)
    if resultado.returncode != 0:
        print(f"\n[ABORTADO] '{descripcion}' termino con codigo {resultado.returncode}.")
        sys.exit(resultado.returncode)


def verificar_fotmob_completo():
    """
    Devuelve (ok, total, con_fotmob, faltantes). "ok" es False si algun
    partido con al menos un archivo de FotMob real descargado en
    partidos_fotmob/ quedo sin su bloque "fotmob" inyectado.
    """
    total = 0
    con_fotmob = 0
    faltantes = []
    for f in fotmob_parser.listar_jsons_de_partidos(Path("data")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        total += 1
        if d.get("home", {}).get("fotmob") or d.get("away", {}).get("fotmob"):
            con_fotmob += 1
        else:
            faltantes.append(str(f))
    return total == con_fotmob, total, con_fotmob, faltantes


def main():
    correr([sys.executable, "parser.py"], "Paso 1/4 -- parser.py (procesa HTML, arma lista.json/jugadores.json)")

    print(f"\n{'='*70}\nPaso 2/4 -- Reinyectando FotMob en todo data/\n{'='*70}")
    actualizados, total_fotmob = fotmob_parser.actualizar_fotmob(silencioso=True)
    print(f"FotMob reinyectado: {actualizados}/{total_fotmob} archivos de partidos_fotmob/.")

    print(f"\n{'='*70}\nPaso 3/4 -- Verificando que ningun partido quedo sin FotMob\n{'='*70}")
    ok, total, con_fotmob, faltantes = verificar_fotmob_completo()
    print(f"Partidos totales: {total} | con FotMob: {con_fotmob} | sin FotMob: {total - con_fotmob}")
    if not ok:
        print("\n[ERROR] Hay partidos sin FotMob que deberian tenerlo. Lista completa:")
        for f in faltantes:
            print(f"  {f}")
        print(
            "\n[ABORTADO] No se corre corners/leaders con datos incompletos. "
            "Revisar manualmente (puede ser un gap real nunca descargado de FotMob, "
            "no necesariamente un bug) antes de confiar en el resto del pipeline."
        )
        sys.exit(1)

    correr([sys.executable, "agregar_corners_equipo.py"], "Paso 4/4a -- agregar_corners_equipo.py")
    correr([sys.executable, "agregar_ranking_jugador.py"], "Paso 4/4b -- agregar_ranking_jugador.py")

    print(f"\n{'='*70}\nListo. data/ quedo consistente: {total} partidos, todos con FotMob.\n{'='*70}")


if __name__ == "__main__":
    main()

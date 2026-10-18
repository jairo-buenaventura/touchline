#!/usr/bin/env python3
"""
generar_dashboards_nuevos.py
-----------------------------
Genera los 4 PNG del PostMatch (Dashboard, Player_Dashboard, KPI_Summary y
Tactical_Insights) para cada partido NUEVO de data/ que todavia no tenga
dashboard. Pensado para correr solo, al final de la tarea diaria
(automatizacion/descarga_diaria.sh) y SIN bloquearla: si algo falla, deja el
detalle en el registro y en dashboards/ULTIMA_CORRIDA.md y termina con codigo 0.

Que hace, en orden:
  1. Recorre data/<Liga>/<Temporada>/*.html (WhoScored) y se queda con los que
     no estan en dashboards/_registro.json.
  2. Empareja cada uno con su FotMob en partidos_fotmob/ (por una clave
     normalizada local-marcador-visitante-liga-temporada, porque el formato del
     nombre de archivo cambia entre ligas). Si todavia no hay FotMob, el partido
     queda pendiente para la proxima corrida.
  3. Calcula la jornada (cuantos partidos lleva el local en esa temporada, con
     las fechas de data/lista.json).
  4. Corrige colores: un color casi blanco (invisible sobre el fondo blanco) o
     dos colores que se confunden entre si se cambian por el color alterno del
     equipo. Avisa de los equipos que no estan en TEAM_COLORS.
  5. Llama a mundial_dashboard.generar_reporte() en un proceso aparte por partido
     (asi la memoria de matplotlib se libera siempre) y lo registra.
  6. Si FotMob no trajo xG, NO publica el dashboard (saldria con xG=0): lo marca
     como error y lo reintenta en la proxima corrida (hasta 3 intentos).

Salida: dashboards/<Liga>/<Temporada>/<partido>/*.png   (ignorado por git/vercel)

Uso:
    python3 generar_dashboards_nuevos.py                       # corrida normal
    python3 generar_dashboards_nuevos.py --dry-run             # solo lista pendientes
    python3 generar_dashboards_nuevos.py --solo "Torino 2-1"   # un partido concreto
    python3 generar_dashboards_nuevos.py --marcar-existentes --excepto-ultimos-dias 1
        # instalacion inicial: registra todo lo que ya existe como "baseline" para
        # no generar miles de dashboards viejos; deja pendientes los de los ultimos N dias.
"""
import argparse
import bisect
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent
DATA = REPO / "data"
FOTMOB = REPO / "partidos_fotmob"
SALIDA_DEFECTO = REPO / "dashboards"
COLORES_EXTRA = REPO / "colores_equipos.json"   # opcional: {"Equipo": {"home": "#...", "away": "#..."}}
LIGAS = ["Premier League", "LaLiga", "Bundesliga", "Ligue 1", "Serie A", "MLS", "Champions League"]

# Ligas donde el dashboard se organiza en una subcarpeta "Jornada N/".
# jornada_de() cuenta, para el equipo LOCAL de cada partido, cuantas
# fechas jugo antes (como local O visitante) en esa competicion+temporada
# -- esto funciona igual de bien para Champions League (fase de liga
# unica, sin ida/vuelta clasico) que para una liga domestica: verificado
# con Barcelona de local en la jornada 1 (vs Feyenoord) y de visitante en
# la jornada 2 (vs Galatasaray) -- da 1 y 2 correctamente, porque no
# depende de que el partido sea ida/vuelta, solo de cuantas fechas jugo
# cada equipo hasta ese momento.
LIGAS_CON_JORNADA = list(LIGAS)
MAX_INTENTOS = 3
TIMEOUT_PARTIDO = 900  # segundos por partido
PNGS = ["Dashboard", "Player_Dashboard", "KPI_Summary", "Tactical_Insights"]

PAT = re.compile(
    r'^(?P<h>.+?) (?P<gh>\d+)\s*-\s*(?P<ga>\d+) (?P<a>.+?) - (?P<liga>.+?) '
    r'(?P<t>\d{4}(?:[-_]\d{4})?)(?:_FotMob)?$'
)


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def clave(stem):
    m = PAT.match(stem)
    if not m:
        return None
    return (norm(m["h"]), int(m["gh"]), int(m["ga"]), norm(m["a"]), norm(m["liga"]),
            m["t"].replace("_", "-"))


# ───────────────────────── registro ─────────────────────────
def cargar_registro(salida):
    p = salida / "_registro.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def guardar_registro(salida, reg):
    salida.mkdir(parents=True, exist_ok=True)
    tmp = salida / "_registro.json.tmp"
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, salida / "_registro.json")


# ───────────────────────── descubrimiento ─────────────────────────
def listar_partidos():
    out = []
    for liga in LIGAS:
        base = DATA / liga
        if not base.is_dir():
            continue
        for temp in sorted(os.listdir(base)):
            carpeta = base / temp
            if not carpeta.is_dir():
                continue
            for f in os.listdir(carpeta):
                if f.endswith(".html"):
                    p = carpeta / f
                    out.append({"rel": f"{liga}/{temp}/{f}", "liga": liga, "temp": temp,
                                "stem": f[:-5], "ws": p, "mtime": p.stat().st_mtime})
    out.sort(key=lambda x: x["mtime"])
    return out


def indexar_fotmob():
    idx = {}
    if FOTMOB.is_dir():
        for f in os.listdir(FOTMOB):
            if f.endswith("_FotMob.json"):
                k = clave(f[:-5])
                if k:
                    idx[k] = FOTMOB / f
    return idx


def cargar_jornadas():
    """(por_archivo, fechas_por_equipo) a partir de data/lista.json; vacios si no existe."""
    por_archivo, fechas = {}, defaultdict(list)
    p = DATA / "lista.json"
    if not p.exists():
        return por_archivo, fechas
    try:
        lista = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return por_archivo, fechas
    for e in lista:
        arch = e.get("archivo")
        if arch:
            por_archivo[norm(re.sub(r"\.json$", "", arch))] = e
        if e.get("fecha"):
            for lado in ("home", "away"):
                if e.get(lado):
                    fechas[(e.get("competicion"), e.get("temporada"), norm(e[lado]))].append(e["fecha"])
    for k in fechas:
        fechas[k].sort()
    return por_archivo, fechas


def jornada_de(partido, por_archivo, fechas):
    e = por_archivo.get(norm(re.sub(r"\.html$", "", partido["rel"])))
    if not e or not e.get("fecha") or not e.get("home"):
        return "—"
    lst = fechas.get((e.get("competicion"), e.get("temporada"), norm(e["home"])), [])
    n = bisect.bisect_right(lst, e["fecha"])
    return str(n) if n else "—"


# ───────────────────────── FotMob JSON -> HTML minimo ─────────────────────────
def fotmob_json_a_html(ruta_json, destino):
    """generar_reporte() solo sabe leer el HTML de FotMob (bloque __NEXT_DATA__);
    en partidos_fotmob/ el dato esta como JSON crudo (general/content en la raiz).
    Se envuelve en un HTML minimo equivalente."""
    d = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    if "props" not in d:
        d = {"props": {"pageProps": d}}
    texto = json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
    Path(destino).write_text(
        f'<html><body><script id="__NEXT_DATA__" type="application/json">{texto}</script></body></html>',
        encoding="utf-8")


# ───────────────────────── colores (usado por el worker) ─────────────────────────
def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(h):
    def c(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)


def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b))) ** 0.5


CLARO = 0.78    # luminancia a partir de la cual un color casi no se ve sobre fondo blanco
CHOQUE = 90     # por debajo de esta distancia RGB local y visitante se confunden
SEPARACION = 140  # distancia minima que debe tener el color de reemplazo


def resolver_colores(tc, home, away):
    th, ta = tc.get(home, {}), tc.get(away, {})
    D_H, D_A = "#F50900", "#0115F5"
    hc, ac = th.get("home", D_H), ta.get("away", D_A)
    alt_h, alt_a = th.get("away"), ta.get("home")
    notas = []
    for nombre, c, alt, lado in ((home, hc, alt_h, "local"), (away, ac, alt_a, "visitante")):
        if _lum(c) > CLARO:
            nuevo = alt if (alt and _lum(alt) <= CLARO) else "#444444"
            notas.append(f"{nombre} ({lado}): {c} casi blanco -> {nuevo}")
            if lado == "local":
                hc = nuevo
            else:
                ac = nuevo
    if _dist(hc, ac) < CHOQUE:
        # prioridad: color alterno propio del visitante, luego azul/rojo/negro genericos;
        # se acepta el primero que se distinga CLARAMENTE del local (distancia >= SEPARACION)
        for cand in (alt_a, D_A, D_H, "#000000"):
            if cand and _lum(cand) <= CLARO and _dist(hc, cand) >= SEPARACION:
                notas.append(f"{away}: choca con {home} ({ac} vs {hc}) -> {cand}")
                ac = cand
                break
    sin_color = [n for n, t in ((home, th), (away, ta)) if not t]
    return hc, ac, notas, sin_color


# ───────────────────────── worker (un partido, proceso aparte) ─────────────────────────
def _nombres_whoscored(ws_html):
    txt = Path(ws_html).read_text(encoding="utf-8", errors="ignore")
    data_txt = re.findall(r'(?<=require\.config\.params\["args"\].=.)[\s\S]*?;', txt)[0]
    for key in ["matchId", "matchCentreData", "matchCentreEventTypeJson", "formationIdNameMappings"]:
        data_txt = data_txt.replace(key, f'"{key}"')
    data = json.loads(data_txt.replace("};", "}"))
    mc = data["matchCentreData"]
    return mc["home"]["name"], mc["away"]["name"]


def worker(args):
    os.environ.setdefault("MPLBACKEND", "Agg")
    sys.path.insert(0, str(REPO))
    import pandas as pd

    # La cuadricula xT se descarga de GitHub en cada partido: se guarda en cache local.
    cache = Path(args.salida) / "_cache" / "xT_Grid.csv"
    _orig = pd.read_csv

    def _read_csv(path, *a, **k):
        if isinstance(path, str) and path.startswith("http") and path.endswith("xT_Grid.csv"):
            if cache.exists():
                return _orig(cache, *a, **k)
            df = _orig(path, *a, **k)
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(cache, header=False, index=False)
            except Exception:
                pass
            return df
        return _orig(path, *a, **k)

    pd.read_csv = _read_csv

    import mundial_dashboard as md
    if COLORES_EXTRA.exists():
        try:
            md.TEAM_COLORS.update(json.loads(COLORES_EXTRA.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"⚠️  colores_equipos.json ilegible: {e}")

    try:
        home, away = _nombres_whoscored(args.ws)
    except Exception:
        home, away = args.home, args.away
    hc, ac, notas, sin_color = resolver_colores(md.TEAM_COLORS, home, away)
    md.TEAM_COLORS[home] = {**md.TEAM_COLORS.get(home, {}), "home": hc}
    md.TEAM_COLORS[away] = {**md.TEAM_COLORS.get(away, {}), "away": ac}

    resumen = md.generar_reporte(args.ws, args.fm, args.gw, args.outdir, generar_imagenes=True,
                                  jugador_home=args.jugador_home, jugador_away=args.jugador_away)
    resumen["colores"] = {"home": hc, "away": ac}
    resumen["notas_color"] = notas
    resumen["equipos_sin_color"] = sin_color
    (Path(args.outdir) / ".resumen.json").write_text(
        json.dumps(resumen, ensure_ascii=False, default=str), encoding="utf-8")


# ───────────────────────── proceso principal ─────────────────────────
def _borrar(ruta):
    """Limpieza tolerante: si no se puede borrar (permisos, carpeta no vacia) no es un error."""
    try:
        if ruta.is_dir():
            ruta.rmdir()
        else:
            ruta.unlink()
    except OSError:
        pass


def procesar(p, fm_json, gw, salida, jugador_home=None, jugador_away=None):
    if p["liga"] in LIGAS_CON_JORNADA and gw not in (None, "—"):
        outdir = salida / p["liga"] / p["temp"] / f"Jornada {gw}" / p["stem"]
    else:
        outdir = salida / p["liga"] / p["temp"] / p["stem"]
    outdir.mkdir(parents=True, exist_ok=True)
    m = PAT.match(p["stem"])
    with tempfile.TemporaryDirectory() as tmp:
        fm_html = Path(tmp) / "fotmob.html"
        fotmob_json_a_html(fm_json, fm_html)
        cmd = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--ws", str(p["ws"]), "--fm", str(fm_html), "--gw", gw, "--outdir", str(outdir),
               "--home", m["h"], "--away", m["a"], "--salida", str(salida)]
        if jugador_home:
            cmd += ["--jugador-home", jugador_home]
        if jugador_away:
            cmd += ["--jugador-away", jugador_away]
        t0 = time.time()
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_PARTIDO, cwd=str(REPO))
        except subprocess.TimeoutExpired:
            return False, f"timeout de {TIMEOUT_PARTIDO}s", None
    rs_path = outdir / ".resumen.json"
    resumen = json.loads(rs_path.read_text(encoding="utf-8")) if rs_path.exists() else None
    if r.returncode != 0 or resumen is None:
        cola = (r.stderr or r.stdout or "").strip().splitlines()[-6:]
        return False, "worker fallo: " + " | ".join(cola)[-600:], None
    if not resumen.get("fotmob_used"):
        for f in list(outdir.iterdir()):
            _borrar(f)
        _borrar(outdir)
        return False, "FotMob sin xG utilizable (no se publica con xG=0)", resumen
    faltan = [n for n in PNGS if not (outdir / f"{resumen['file_header']}_{n}.png").exists()]
    if faltan:
        return False, f"faltan PNG: {faltan}", resumen
    for f in outdir.glob("*.csv"):
        _borrar(f)   # el CSV de eventos ya vive en data/*.json; solo se conservan los PNG
    resumen["segundos"] = round(time.time() - t0)
    resumen["carpeta"] = str(outdir.relative_to(salida))
    return True, "ok", resumen


def notificar(texto):
    if sys.platform == "darwin":
        try:
            subprocess.run(["osascript", "-e",
                            f'display notification "{texto}" with title "Touchline"'],
                           timeout=10, capture_output=True)
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", default=str(SALIDA_DEFECTO))
    ap.add_argument("--limite", type=int, default=30, help="maximo de partidos por corrida")
    ap.add_argument("--solo", help="procesar solo partidos cuyo nombre contenga este texto")
    ap.add_argument("--forzar", action="store_true", help="regenerar aunque ya este registrado")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sin-notificar", action="store_true")
    ap.add_argument("--marcar-existentes", action="store_true")
    ap.add_argument("--excepto-ultimos-dias", type=float, default=0)
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--jugador-home", dest="jugador_home", help="forzar este jugador (en vez del de mejor rating) en el Player_Dashboard del lado local; usar junto con --solo")
    ap.add_argument("--jugador-away", dest="jugador_away", help="forzar este jugador (en vez del de mejor rating) en el Player_Dashboard del lado visitante; usar junto con --solo")
    for a in ("ws", "fm", "gw", "outdir", "home", "away"):
        ap.add_argument(f"--{a}")
    args = ap.parse_args()

    if args.worker:
        worker(args)
        return 0

    salida = Path(args.salida)
    reg = cargar_registro(salida)
    partidos = listar_partidos()

    if args.marcar_existentes:
        corte = time.time() - args.excepto_ultimos_dias * 86400
        marcados = pendientes = 0
        for p in partidos:
            if p["rel"] in reg:
                continue
            if args.excepto_ultimos_dias and p["mtime"] >= corte:
                pendientes += 1
                continue
            reg[p["rel"]] = {"estado": "baseline", "fecha": datetime.now().isoformat(timespec="seconds")}
            marcados += 1
        guardar_registro(salida, reg)
        print(f"Baseline: {marcados} partidos registrados como existentes; "
              f"{pendientes} quedan pendientes (ultimos {args.excepto_ultimos_dias} dias).")
        return 0

    idx = indexar_fotmob()
    por_archivo, fechas = cargar_jornadas()

    pend, sin_fm = [], []
    for p in partidos:
        r = reg.get(p["rel"])
        if args.solo and args.solo.lower() not in p["stem"].lower():
            continue
        if not args.forzar and r and (r["estado"] in ("ok", "baseline") or r.get("intentos", 0) >= MAX_INTENTOS):
            continue
        k = clave(p["stem"])
        fm = idx.get(k) if k else None
        if fm is None:
            sin_fm.append(p["stem"])
            continue
        pend.append((p, fm))

    print(f"Pendientes con FotMob: {len(pend)} | esperando FotMob: {len(sin_fm)}")
    if args.dry_run:
        for p, _ in pend[:args.limite]:
            print("  •", p["rel"])
        return 0

    nuevos, errores, sin_color_todos = [], [], set()
    for p, fm in pend[:args.limite]:
        gw = jornada_de(p, por_archivo, fechas)
        print(f"→ {p['stem']} (jornada {gw})", flush=True)
        ok, msg, res = procesar(p, fm, gw, salida, jugador_home=args.jugador_home, jugador_away=args.jugador_away)
        prev = reg.get(p["rel"], {})
        if ok:
            reg[p["rel"]] = {"estado": "ok", "fecha": datetime.now().isoformat(timespec="seconds"),
                             "carpeta": res["carpeta"], "segundos": res.get("segundos")}
            nuevos.append((p, res))
            sin_color_todos.update(res.get("equipos_sin_color", []))
            print(f"   ✅ {res['hteamName']} {res['hgoal_count']}-{res['agoal_count']} {res['ateamName']} "
                  f"({res.get('segundos')}s)")
            for n in res.get("notas_color", []):
                print("   🎨", n)
        else:
            reg[p["rel"]] = {"estado": "error", "fecha": datetime.now().isoformat(timespec="seconds"),
                             "detalle": msg, "intentos": prev.get("intentos", 0) + 1}
            errores.append((p, msg))
            print(f"   ❌ {msg}")
        guardar_registro(salida, reg)

    # resumen legible
    lineas = [f"# Ultima corrida de dashboards — {datetime.now():%Y-%m-%d %H:%M}", ""]
    lineas.append(f"- Generados: **{len(nuevos)}** | con error: **{len(errores)}** | esperando FotMob: **{len(sin_fm)}**")
    if len(pend) > args.limite:
        lineas.append(f"- Quedan {len(pend) - args.limite} pendientes para la proxima corrida (limite {args.limite}).")
    if nuevos:
        lineas += ["", "## Nuevos", ""]
        for p, r in nuevos:
            lineas.append(f"- {r['hteamName']} {r['hgoal_count']}-{r['agoal_count']} {r['ateamName']} "
                          f"({p['liga']} {p['temp']}) — xG {r['hxg']}-{r['axg']} — "
                          f"`{r['carpeta']}`")
    if errores:
        lineas += ["", "## Errores", ""]
        lineas += [f"- {p['stem']}: {msg}" for p, msg in errores]
    if sin_color_todos:
        lineas += ["", "## Equipos sin color propio (usaron rojo/azul por defecto)", ""]
        lineas += [f"- {n}" for n in sorted(sin_color_todos)]
        lineas += ["", "Agregalos en `colores_equipos.json` como "
                       '`{"Equipo": {"home": "#RRGGBB", "away": "#RRGGBB"}}`.']
    if sin_fm:
        lineas += ["", f"## Esperando FotMob ({len(sin_fm)})", ""] + [f"- {s}" for s in sin_fm[:20]]
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "ULTIMA_CORRIDA.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")

    print("\n".join(lineas))
    if nuevos and not args.sin_notificar:
        notificar(f"{len(nuevos)} dashboards nuevos listos en la carpeta dashboards")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:      # nunca debe tumbar la tarea diaria
        print(f"[ERROR] generar_dashboards_nuevos.py: {type(e).__name__}: {e}")
        sys.exit(0)

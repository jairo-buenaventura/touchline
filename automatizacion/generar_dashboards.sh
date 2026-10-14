#!/bin/bash
# Genera los dashboards (4 PNG) de los partidos NUEVOS de data/ que aun no los tienen.
# Lo invoca descarga_diaria.sh al final de cada corrida (6am, 5pm y 11pm), pero tambien
# se puede correr a mano:   bash automatizacion/generar_dashboards.sh [--dry-run] [--solo "texto"]
#
# NUNCA bloquea la tarea diaria: termina siempre con codigo 0 y deja el detalle en el log.
# Resultado: dashboards/<Liga>/<Temporada>/<partido>/*.png y dashboards/ULTIMA_CORRIDA.md

export PATH="/opt/homebrew/bin:$PATH"   # launchd arranca con un PATH minimo
REPO="${TOUCHLINE_REPO:-/Users/jairobuenaventura/Desktop/touchline}"
cd "$REPO" || exit 0

LIBS="import mplsoccer, highlight_text, sklearn, scipy, seaborn, pandas, matplotlib"
sirve() { "$1" -c "$LIBS" >/dev/null 2>&1; }

PY=""
for c in "${DASH_PYTHON:-}" "$REPO/.venv_mundial/bin/python3" /opt/homebrew/bin/python3 /opt/anaconda3/bin/python3 \
         "$HOME/anaconda3/bin/python3" /opt/miniconda3/bin/python3 /usr/bin/python3; do
  if [ -n "$c" ] && [ -x "$c" ] && sirve "$c"; then PY="$c"; break; fi
done

if [ -z "$PY" ]; then
  echo "[dashboards] Ningun Python tiene las librerias; creando .venv_mundial (solo esta vez)..."
  BASE="$(command -v /opt/homebrew/bin/python3 || command -v python3)"
  if [ -n "$BASE" ] && "$BASE" -m venv "$REPO/.venv_mundial" \
     && "$REPO/.venv_mundial/bin/pip" install -q mplsoccer highlight_text scikit-learn scipy seaborn pandas numpy matplotlib pillow; then
    PY="$REPO/.venv_mundial/bin/python3"
  fi
fi

if [ -z "$PY" ]; then
  echo "[dashboards] No se pudo preparar un Python con las librerias; se omite este paso (la descarga no se ve afectada)."
  exit 0
fi

echo "[dashboards] Python: $PY"
"$PY" "$REPO/generar_dashboards_nuevos.py" "$@"
exit 0

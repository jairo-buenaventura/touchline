#!/bin/bash
# Corrido por launchd (ver com.touchline.descargadiaria.plist) todos los dias a las
# 6am, 5pm y 11pm hora Bogota.
# Invoca Claude Code en modo no interactivo, sin pedir permisos (no hay nadie para
# aprobarlos a esta hora), para que baje/procese/commitee/pushee/despliegue solo.

set -uo pipefail

REPO="/Users/jairobuenaventura/Desktop/touchline"
LOGDIR="$REPO/automatizacion/logs"
mkdir -p "$LOGDIR"
LOGFILE="$LOGDIR/$(date +%Y-%m-%d_%H-%M-%S).log"

cd "$REPO" || exit 1

PROMPT="$(cat "$REPO/automatizacion/prompt_descarga_diaria.md")"

# --mcp-config con --isolated: usa un perfil de navegador propio para esta corrida,
# para no chocar con el "Browser is already in use" si hay otra sesion de Claude Code
# (ej. VSCode) con el Playwright MCP del proyecto abierto al mismo tiempo.
/opt/homebrew/bin/claude -p "$PROMPT" \
  --permission-mode bypassPermissions \
  --dangerously-skip-permissions \
  --mcp-config "$REPO/automatizacion/mcp_config_automatizacion.json" \
  --strict-mcp-config \
  > "$LOGFILE" 2>&1

echo "---" >> "$LOGFILE"
echo "Terminado: $(date)" >> "$LOGFILE"

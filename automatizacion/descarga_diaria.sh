#!/bin/bash
# Corrido por launchd (ver com.touchline.descargadiaria.plist) todos los dias a las
# 6am, 5pm y 11pm hora Bogota.
# Invoca Claude Code en modo no interactivo, sin pedir permisos (no hay nadie para
# aprobarlos a esta hora), para que baje/procese/commitee/pushee/despliegue solo.

set -uo pipefail

# launchd arranca con un PATH minimo, asi que "python3"/"node"/"vercel" resuelven
# al binario del sistema (sin playwright instalado) en vez del de Homebrew. Pasó
# de verdad el 2026-10-11: actualizar_todo.py fallo con codigo 1 porque
# sofascore_parser.py no encontraba "playwright" al importar, y despues "vercel"
# tampoco estaba en el PATH para el deploy. El agente lo resolvio a mano esa vez
# agregando /opt/homebrew/bin al PATH -- esto lo deja fijo para que no dependa de
# que lo descubra cada corrida.
export PATH="/opt/homebrew/bin:$PATH"

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

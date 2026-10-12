# Tarea diaria automática: descargar la última fecha jugada (WhoScored + FotMob)

Esto corre SIN supervisión humana (tarea programada de macOS, 6am/5pm/11pm hora Bogotá), así que
tenés que completar todo el flujo de punta a punta y dejar un log claro, sin pedirle nada
a nadie.

## Qué hacer

Para cada una de estas 6 ligas, en su temporada en curso, descargar los partidos que ya
terminaron (`status == 6` / `elapsed == "FT"` en el endpoint de datos de WhoScored — ver
`.claude/skills/descargar-whoscored/SKILL.md`, que ya documenta el SOP completo, la regla
obligatoria de WhoScored+FotMob juntos, y por qué nunca hay que confiar solo en que
`homeScore`/`awayScore` no sean null) que todavía no estén en `data/`:

| Liga | WhoScored stageId | FotMob league-id | ccode3 |
|---|---|---|---|
| Premier League | 25544 | 47 | ENG |
| LaLiga | 25662 | 87 | ESP |
| Bundesliga | 25666 | 54 | GER |
| Ligue 1 | 25554 | 53 | FRA |
| Serie A | 25518 | 55 | ITA |
| MLS | 24960 | 130 | USA |

(URLs de fixtures / temporada completa: ver el skill, Paso 1 — si alguna de estas ligas ya
pasó a la temporada 2027/2028 o MLS a 2027, hay que re-detectar el `stageId`/season nuevo
siguiendo el Paso 1 del skill en vez de asumir que estos siguen vigentes.)

Seguí el SOP del skill `descargar-whoscored` al pie de la letra: Paso 1-3 para WhoScored
(con el filtro de `status == 6`), Paso 3.1 para FotMob (con la tabla de `--league-id`/
`--ccode3` de arriba y los alias de equipo ya documentados ahí — `Deportivo de A Coruna`,
`Bayern Munich`, `Borussia M.Gladbach`), Paso 5 para verificar. El HTML de partidos nuevos
va directo a `data/<Liga>/<Temporada>/`, no a `partidos_html/`.

Si algún partido quedó con `status == 5` (`Abd`/abandonado) o cualquier estado raro que no
sea 3 (en vivo, ignorar) ni 6 (FT, descargar), anotalo en el log como caso especial en vez
de tratarlo como un partido normal.

## Después de descargar

1. `python3 actualizar_todo.py` (NO corras `parser.py` suelto — este script encadena
   parser.py + reinyección de FotMob + verificación dura de que ningún partido quedó sin
   FotMob + corners/leaders, todo en un solo paso atómico). Si la sesión se corta entre
   `parser.py` y la reinyección de FotMob corriéndolos por separado, TODO `data/` queda sin
   FotMob en silencio (pasó de verdad el 2026-10-11) — por eso este script existe y por eso
   es obligatorio usarlo en vez de los pasos sueltos.
2. Confirmar que `actualizar_todo.py` terminó con exit code 0. Si terminó con código
   distinto de 0 (ya sea por `[ERROR]` de parser.py o por la verificación de FotMob
   fallida), NO sigas al commit — dejá todo tal cual está y escribí el error completo al
   final del log para que se revise a mano.
3. Si no hubo NINGÚN partido nuevo en ninguna liga, no hagas commit vacío — solo dejá
   constancia en el log de que se revisó y no había nada nuevo, y terminá ahí.
4. Si hubo partidos nuevos y todo salió limpio: `git add` solo lo relevante (nunca
   `git add -A` — `data/`, `partidos_fotmob/`, y cualquier script que hayas tenido que tocar),
   commit con mensaje descriptivo (qué ligas, cuántos partidos, terminando con
   `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`), `git push origin main`.
5. `vercel --prod --yes` desde la raíz del repo para desplegar.
6. Verificar en vivo con un `curl` a `https://touchline-woad.vercel.app/data/lista.json` que
   el total de partidos subió respecto a antes de la corrida.

## Log

Escribí un resumen al final (partidos nuevos por liga, errores si los hubo, si se hizo
commit/push/deploy o no, y por qué) — esto se redirige a un archivo de log por quien llama
este prompt, no hace falta que lo guardes vos en otro lado.

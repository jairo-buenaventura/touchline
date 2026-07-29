# touchline

Proyecto de análisis táctico y de scouting de fútbol: descarga partidos de
WhoScored (eventos, posiciones, red de pases) y FotMob (xG/xGOT, field tilt,
big chances), los combina en `data/*.json` por partido, y a partir de ahí
se calculan métricas tácticas (xT, PPDA, redes de pase) y — desde esta
sesión de trabajo — también métricas agregadas por jugador y datos de
negocio (edad, contrato, valor de mercado, lesiones).

## Estructura de datos

### `data/*.json` — un archivo por partido

Nombre de archivo: `"{home} {golesHome} - {golesAway} {away} - {liga} {temporada}.json"`
(el separador del marcador y el formato de temporada varían un poco entre
ligas — ver `validar_cobertura.py` para el detalle de esas variantes).

Cada archivo trae, en el nivel raíz: `marcador`, `estadio`, `capacidad_estadio`,
`asistencia`, **`competicion`** (slug, ej. `"premier_league"`) y **`temporada`**
(formato corto, ej. `"23/24"`) — estos dos últimos son más confiables que
parsear el nombre del archivo, y son los que usa `agregar_temporada_jugador.py`.

Por cada lado (`home`/`away`):

| campo              | contenido                                                                 |
|--------------------|----------------------------------------------------------------------------|
| `equipo`           | nombre del equipo                                                          |
| `jugadores`        | `id`, `nombre`, `dorsal`, `x`/`y` (posición promedio), `toques`             |
| `pases`            | red de pases: `de`, `a`, `veces` (conteo de pases entre ese par)            |
| `estadisticas`     | tiros, posesión, precisión de pase, goles (con minuto), `ppda`              |
| `tiros`            | por tiro: minuto, jugador, `resultado` (Goal/SavedShot/MissedShots/...), x/y, coords de arco |
| `acciones`         | por jugador: lista de acciones (`tipo`, x/y, `exitoso`) — Aerial, TakeOn, BallRecovery, Interception, Foul, Dispossessed, BlockedPass, Tackle, Clearance, Challenge |
| `recepcion_pases`  | por jugador: `recepciones` (x/y), `pases_clave_recibidos`, `asistencias_recibidas`, `en_tercio_final`, `en_area_rival`, `cruces_recibidos` |
| `alineacion`       | `formacion`, `entrenador`, `titulares`/`banca` (con `posicion` nominal)     |
| `fotmob`           | xg, xgot, posesión, field_tilt, big_chances, corners, faltas, cruces        |
| `stats_avanzadas`  | por jugador: `minutos_jugados`, goles, asistencias, tiros, regates, chances creadas, corners sacados, toques en área rival, rating, motm — excluye eventos de `PenaltyShootout` |
| `corners`          | por corner: `minuto`, `jugador`, `x`/`y` (origen), `endX`/`endY` (destino), `endYNorm` (mirror para comparar ambos lados), `zona` (`primer_palo`/`centro`/`segundo_palo`/`corto`/`sin_peligro`) |

**Ojo:** `data/jugadores.json` y `data/lista.json` viven en la misma carpeta
`data/` pero NO son partidos — son índices/metadata que arma `parser.py`.
Cualquier script que recorra `data/*.json` como si todos fueran partidos
debe filtrarlos explícitamente (ver `agregar_temporada_jugador.py`).

**Ya no es limitación:** `stats_avanzadas` trae `minutos_jugados` por jugador
(calculado desde `isFirstEleven` + eventos `SubstitutionOn`/`Off`, excluyendo
minutos de tanda de penales), así que las métricas por-90 en `data/leaders/`
sí son reales, no un promedio por partido. El resto del diagnóstico de
`PLAN_MEJORAS_CALIDAD_DATOS.md` sigue vigente salvo este punto.

**Inconsistencia conocida:** el mismo equipo puede aparecer con nombres
distintos entre archivos (ej. "Man City" y "Manchester City" para el mismo
Manchester City) — no son duplicados, es naming inconsistente entre scrapes.
Cualquier cruce por nombre de equipo necesita una tabla de alias (ver `ALIAS`
en `validar_cobertura.py`).

## Flujo de descarga (WhoScored + FotMob)

Ver `.claude/skills/descargar-whoscored/SKILL.md` para el SOP completo.
En resumen: `parser.py` procesa el HTML de WhoScored en `partidos_html/` y
escribe a `data/`; `fotmob_parser.py` hace lo mismo con el HTML de FotMob en
`partidos_fotmob/`. `descargar_fotmob_generico.py` es la versión
parametrizable (por `--league-id`/`--season`/etc.) que reemplaza en la
práctica a los scripts específicos por liga (`descargar_fotmob_premier.py`,
`_bundesliga.py`, `_ligue1.py`, `_mls.py`) — esos siguen en el repo mas no
se tocaron en esta sesión; son candidatos a archivar una vez confirmado que
el genérico cubre todos los casos.

`backfill_masivo.py` reprocesa partidos listados en `partidos_faltantes.json`
(hoy con lógica específica de LaLiga 2025-2026) y loggea fallos en
`log_errores_backfill.json`. **Ambos archivos son snapshots de una corrida
puntual, no se regeneran solos** — antes de confiar en ellos, correr
`validar_cobertura.py` / `revisar_errores_backfill.py` para ver el estado real.

## Scripts añadidos en esta sesión (todos de solo lectura sobre data/)

- **`validar_cobertura.py`** — cruza `data/` contra los fixtures reales
  (CSV/JSON) de Premier League, Bundesliga, Ligue 1 y LaLiga. Genera
  `reporte_cobertura.json`. Solo cubre esas 4 ligas porque son las únicas
  con fuente de fixtures en el repo.
- **`revisar_errores_backfill.py`** — cruza `log_errores_backfill.json`
  contra `data/` para saber qué errores ya se resolvieron en un run
  posterior. Genera `reporte_errores_backfill.json`.
- **`agregar_temporada_jugador.py`** — recorre todo `data/` y arma
  `tabla_jugadores_temporada.csv` (una fila por jugador × competición ×
  temporada) y `tabla_jugador_partido.csv` (detalle sin agregar).
- **`enriquecer_transfermarkt.py`** — prueba de concepto: toma una MUESTRA
  de jugadores de `tabla_jugadores_temporada.csv` y resuelve su perfil real
  en Transfermarkt (edad, nacionalidad, valor de mercado, fin de contrato,
  agente, historial de lesiones). Genera `jugadores_transfermarkt_muestra.csv`.
  Transfermarkt no bloquea peticiones simples (a diferencia de WhoScored,
  que sí necesita Playwright).
- **`enriquecer_transfermarkt_completo.py`** — versión a escala completa del
  anterior: recorre los ~6,776 jugadores únicos de `data/jugadores.json` y
  escribe incremental a `jugadores_transfermarkt_completo.jsonl` (resumible
  entre corridas, vía `cargar_ids_ya_procesados()`). **Regla dura: nunca
  adivina.** Cada fila trae `confianza_match`:
  - `"alta"` — el club/selección de Transfermarkt coincidió con alguno de
    los equipos reales del jugador en nuestros datos (`match_por_equipo`).
    Solo estas filas tienen datos de perfil/lesiones llenados.
  - `"necesita_revision_manual"` — se encontró un candidato con ese nombre
    pero el equipo no coincidió (casi siempre porque se transfirió, se
    retiró, o la aparición nuestra es con la selección y Transfermarkt solo
    muestra club). Sin datos de perfil llenados, solo un candidato sugerido.
  - `"sin_match"` — no hay ningún resultado en Transfermarkt para ese nombre.
- **`revisar_pendientes_transfermarkt.py`** — segunda pasada, solo sobre los
  `"necesita_revision_manual"` del script anterior: si el nombre normalizado
  coincide EXACTO con un único candidato en los resultados de búsqueda (sin
  ambigüedad de "cuál de los tres Aaron Cresswell es"), lo acepta igual
  aunque el equipo no calce — sigue sin adivinar, solo relaja el criterio de
  verificación de equipo a uno de nombre-sin-ambigüedad. Resuelve ~75% de
  los pendientes en la muestra probada. Escribe aparte, en
  `jugadores_transfermarkt_revision.jsonl` (no toca el archivo principal).
- **`agregar_perfiles_jugador.py`** — junta los dos jsonl de arriba
  (prioridad al principal), filtra a `confianza_match == "alta"` únicamente,
  traduce el `tipo_lesion` de cada lesión con `traduccion_lesiones.py` (deja
  el inglés original si no hay traducción confiable) y genera
  `data/perfiles_jugadores.json` — el único archivo que lee `index.html`
  para el drawer de perfil en Leaders (nunca lee los jsonl directo).
- **`agregar_ranking_jugador.py`** — agrega `stats_avanzadas` de todo
  `data/` en rankings por competición+temporada (`data/leaders/*.json`):
  totales de temporada (sin umbral de minutos, autocorrectivo) y tasas
  por-90 (solo jugadores con 450+ minutos). El percentil de cada categoría
  se calcula **solo entre los jugadores con valor > 0 en esa categoría**,
  no contra toda la liga — comparar a un goleador contra arqueros/centrales
  que nunca anotan comprime a todos los delanteros en el mismo percentil
  (ver commit/conversación del 2026-07-28: Nico Williams con 6 goles pasaba
  de un inflado "Top 6%" a un real "Top 16%" al corregirlo).
- **`agregar_corners_equipo.py`** — agrega el campo `corners` de `data/` en
  `data/corners/*.json`: conteo/porcentaje por zona y por equipo, más el
  detalle punto-por-punto (`endX`/`endYNorm`/`zona`) para el scatter de la
  pestaña Corners en Pitch view.

Ver `PLAN_MEJORAS_CALIDAD_DATOS.md` para el diagnóstico completo y el
`.claude/agents/representante-mal-genio.md` para el agente que audita el
proyecto con esa misma vara.

## Tests

`tests/` trae validaciones de solo lectura sobre `data/` (esquema, filtrado
correcto de `jugadores.json`/`lista.json`) y tests unitarios de las
funciones puras de los scripts nuevos. **No incluye tests de `parser.py`**
a propósito: `parser.py` escribe directo a `data/` y `data/lista.json`, así
que correrlo dentro de un test tendría efectos secundarios sobre datos
reales — si se quiere testear, habría que aislarlo primero con un
directorio de salida configurable.

Correr con:
```
python3 -m pytest tests/ -v
```

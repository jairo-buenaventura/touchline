## Estado de implementación (esta sesión)

Todo lo de abajo se implementó como **archivos nuevos**, sin tocar ningún
script existente que ya funcionara con fotmob/whoscored:

| Punto | Estado | Archivo | Resultado real |
|---|---|---|---|
| 1. Cobertura | ✅ hecho | `validar_cobertura.py` | 100% de cobertura en Premier League, Bundesliga, Ligue 1 y LaLiga 2025/26. `partidos_faltantes.json` estaba obsoleto (los 332 "faltantes" ya existen en `data/`). |
| 2. Errores de backfill | ✅ hecho | `revisar_errores_backfill.py` | El único error loggeado (Elche vs Osasuna) ya estaba resuelto — `log_errores_backfill.json` también estaba obsoleto. |
| 3. Tabla agregada jugador/temporada | ✅ hecho | `agregar_temporada_jugador.py` | 216,749 filas jugador-partido → 13,227 filas jugador×competición×temporada en `tabla_jugadores_temporada.csv`. Validado contra Haaland (27 goles PL 23/24, dato real). |
| 4. Scripts de descarga duplicados | ✅ ya estaba resuelto | `descargar_fotmob_generico.py` | Ya existe una versión parametrizable que reemplaza a los 4 scripts por liga — solo falta archivar los viejos (no se borraron, por precaución). |
| 5. Docs + tests | ✅ hecho | `CLAUDE.md`, `tests/` | 9 tests con pytest, todos verdes. Deliberadamente sin test de `parser.py` (escribe a `data/` real, tendría efectos secundarios). |
| 6. Enriquecimiento Transfermarkt | ✅ prueba de concepto | `enriquecer_transfermarkt.py` | 8 jugadores reales enriquecidos con edad, valor de mercado, fin de contrato, agente y lesiones — datos verificables en Transfermarkt.com. Transfermarkt no bloquea requests simples (a diferencia de WhoScored). |
| Extra: gitignore | ✅ hecho | `.gitignore` | Se agregó `__pycache__/`, `.DS_Store`, `.pytest_cache/`, el `.tsv` de scratch y `.venv_mundial/`. |

**Limitaciones honestas que quedan abiertas:**
- El script de cobertura no cubre Serie A, Eredivisie, Champions League, MLS ni el Mundial — no hay fuente de fixtures para esas ligas en el repo todavía.
- La tabla de jugadores no tiene minutos jugados (no existe en el dataset), así que no hay métricas por-90 reales.
- El enriquecimiento de Transfermarkt es una muestra de 8 jugadores, no las ~13,000 filas — escalarlo a todo el dataset requiere decidir un ritmo de requests respetuoso con el sitio.
- Los 4 scripts `descargar_fotmob_<liga>.py` siguen en el repo aunque ya son redundantes frente al genérico — no se borraron para no arriesgar nada sin confirmación explícita.

---

# Plan de mejoras — respuesta a la crítica del Representante Mal Genio

Basado en la revisión real del repo (conteos y archivos verificados: `partidos_faltantes.json` con 332 registros, `log_errores_backfill.json`, ausencia de `README`/tests, 5 scripts `descargar_fotmob_*.py` casi idénticos).

## 1. Cobertura de datos incompleta (332 partidos faltantes)

**Solución:**
- Crear `validar_cobertura.py`: cruza cada fixture de `*_fixtures.csv` / `calendario_completo_*.json` contra los archivos en `data/`. Cualquier partido jugado sin JSON correspondiente se marca como faltante automáticamente (reemplaza el mantenimiento manual de `partidos_faltantes.json`).
- Correr este script como paso final de cada backfill, no como algo aparte.
- Definir un umbral de cobertura mínima (ej. 99%) por liga/temporada — si no se cumple, el pipeline "falla" explícitamente en vez de quedar en silencio.

## 2. Errores de scraping sin resolver ni monitoreo

**Solución:**
- En `backfill_masivo.py`, envolver cada descarga en reintento con backoff exponencial (2–3 intentos) antes de loggear como error definitivo.
- `log_errores_backfill.json` deja de ser un archivo que se revisa manualmente: al final del backfill, imprimir/mostrar un resumen (`N errores de M intentos`) y, si hay errores, listar los partidos afectados para reintento explícito la próxima corrida.
- Opcional: si se corre en automático (cron), notificar (Slack/email) solo cuando haya errores — no monitoreo pasivo de un archivo que nadie abre.

## 3. Sin capa de agregación por jugador/temporada

**Solución:**
- Construir `agregar_temporada_jugador.py` que recorra todos los JSON de `data/` de una liga/temporada y produzca **una tabla plana** (CSV/Parquet/SQLite) con una fila por jugador-temporada:
  - Minutos jugados, xT total y por 90, xG y goles, % éxito por tipo de acción (Aerial, TakeOn, etc.), centralidad en red de pases, PPDA cuando aplique, posición nominal vs heatmap real.
- Esta tabla es el verdadero entregable de negocio — los JSON crudos son materia prima, la tabla agregada es lo que se lleva a una reunión.
- Reutilizar `calcular_xt_timeline.py` como módulo importado, no como script aislado.

## 4. Scripts ad-hoc duplicados por liga

**Solución:**
- Reemplazar `descargar_fotmob_bundesliga.py`, `_ligue1.py`, `_mls.py`, `_premier.py` por un único `descargar_fotmob.py --liga <nombre>` (ya existe `descargar_fotmob_generico.py` como base — consolidar todo ahí y borrar los específicos).
- Extraer a un archivo de configuración (`ligas.json` o similar) los IDs/slugs propios de cada liga en fotmob, en vez de tenerlos hardcodeados en scripts separados.
- Esto reduce el mantenimiento de "5 archivos casi iguales" a "1 archivo + 1 config".

## 5. Cero documentación, cero tests

**Solución:**
- Crear un `CLAUDE.md` en la raíz del proyecto: qué es touchline, estructura de `data/`, cómo correr un backfill, esquema de cada campo (`pases`, `tiros`, `acciones`, `fotmob`, etc.).
- Tests mínimos con `pytest`:
  - Validación de esquema (todo archivo en `data/` tiene las keys esperadas: `home`, `away`, `marcador`, etc.).
  - Test de `parser.py`/`fotmob_parser.py` contra un fixture HTML/JSON de muestra guardado en el repo, para detectar cuando la fuente cambia su estructura y el parser rompe en silencio.
- Esto es lo que permite que alguien más que no sea el autor original pueda operar y confiar en el sistema.

## 6. Cero capa de negocio (edad, contrato, valor de mercado, lesiones)

**Solución:**
- Construir `enriquecer_transfermarkt.py`: por cada jugador único en `data/` (usando el `id` de fotmob), resolver su perfil en Transfermarkt (fecha de nacimiento, valor de mercado, fin de contrato, historial de lesiones).
- El punto difícil es el **mapeo de identidad** (nombre en fotmob ≠ nombre en Transfermarkt por acentos/apodos): construir una tabla de mapeo `id_fotmob → id_transfermarkt` verificada manualmente para los jugadores prioritarios, y matching fuzzy (nombre + equipo + fecha aprox.) para el resto, marcando confianza del match.
- Guardar esto como una tabla maestra `jugadores_maestro.csv` separada de los datos de partido, para no mezclar dato de negocio (que cambia poco) con dato de evento (que crece cada semana).

## Extras que agregaría yo (no pedidos, pero relevantes)

- **Migrar de JSON sueltos a una base de datos consultable** (SQLite o DuckDB). Con 7,042 archivos y creciendo, cualquier pregunta agregada ("dame el xT promedio de todos los extremos de la Premier en 2024/25") hoy requiere leer todos los archivos uno por uno. Con una base local, es una query SQL.
- **Validación de esquema entre ligas.** No hay garantía verificada de que todas las ligas/temporadas tengan exactamente las mismas keys (`fotmob`, `alineacion`, etc.) — un chequeo de esquema por liga evitaría sorpresas al agregar.
- **Versionar el dataset.** Cuando se corrija cobertura o se re-scrapee algo, tener claro qué versión del dataset se usó para un análisis específico (importante si alguna vez se usa un número en una negociación real y luego el dato cambia).
- **Limpieza de higiene del repo.** Archivos como `.claude_scratch_matchlist.tsv`, `.DS_Store`, `__pycache__` no deberían vivir en el repo — un `.gitignore` más estricto evita ruido.

---
name: descargar-whoscored
description: Descarga el HTML completo (match center) de todos los partidos de una liga/temporada en WhoScored usando el navegador de Playwright MCP, y los guarda en partidos_html/. Usar cuando el usuario pida "descargar partidos de whoscored", "bajar el html de [liga] de whoscored" o similar para cualquier competición/temporada.
---

SOP para descargar en bloque el HTML de partidos de WhoScored (match center "live") para una liga y temporada dadas, evitando el bloqueo de Cloudflare y sin agotar el contexto de la conversación.

## Por qué este método

WhoScored está protegido por Cloudflare: peticiones simples con `urllib`/`requests` devuelven la pantalla de bloqueo (ver `revisar_bloqueo_whoscored.py`). Una sesión de navegador real controlada por Playwright (vía el MCP `mcp__playwright__*`) sí pasa el check de Cloudflare sin necesidad de ninguna técnica de evasión: basta con navegar normalmente. Una vez la sesión está "autorizada", incluso peticiones `fetch()` hechas *desde dentro* de esa página (mismo origen, con las cookies ya puestas) devuelven el HTML completo sin bloqueo.

## Paso 1 — Identificar la competición y temporada en WhoScored

1. Navegar (`mcp__playwright__browser_navigate`) a la página de la competición, p.ej. `https://www.whoscored.com/regions/{regionId}/tournaments/{tournamentId}/{slug}`. Si no se conoce la URL exacta, buscar en Google `whoscored <liga>` o navegar desde whoscored.com y usar el buscador.
2. En el snapshot de la página, localizar el link "Fixtures": tiene la forma
   `/regions/{regionId}/tournaments/{tournamentId}/seasons/{seasonId}/stages/{stageId}/fixtures/{slug}`
   — el `{stageId}` es la pieza clave que se necesita para el paso 2.
3. Confirmar con el selector de temporada (combobox en la página) que `{seasonId}`/`{stageId}` corresponden a la temporada pedida (p.ej. "2025/2026").

## Paso 2 — Obtener la lista completa de partidos (IDs) vía el endpoint JSON de datos

WhoScored expone un endpoint interno que devuelve todos los partidos de un mes para un `stageId`:

```
GET /tournaments/{stageId}/data/?d=YYYYMM&isAggregate=false
```

No hace falta pasearse por la calendarización de la UI (mes a mes con clicks) — se puede pedir este endpoint directamente para cada mes de la temporada usando `fetch()` desde dentro de la página ya navegada (mismo origen, cookies incluidas), vía `mcp__playwright__browser_evaluate`:

```js
async () => {
  const months = ['202508','202509','202510','202511','202512','202601','202602','202603','202604','202605']; // ajustar al rango real de la temporada
  const all = {};
  for (const m of months) {
    const res = await fetch(`/tournaments/{stageId}/data/?d=${m}&isAggregate=false`, {headers: {'X-Requested-With':'XMLHttpRequest'}});
    all[m] = await res.json();
  }
  return JSON.stringify(all);
}
```

Guardar el resultado con el parámetro `filename` del evaluate (NUNCA dejar que se devuelva inline — el JSON de una temporada completa pesa cientos de KB y satura el límite de tokens de la respuesta de la tool).

Luego, con un script Python (Bash tool), parsear ese JSON: cada mes tiene `tournaments[0].matches[]`, con `id`, `homeTeamName`, `awayTeamName`, `homeScore`, `awayScore`, `startTime`. Deduplicar por `id` (los meses solapan) y ordenar por `startTime`. Verificar que el total de partidos únicos coincide con lo esperado (p.ej. 306 para una liga de 18 equipos a doble vuelta, 380 para 20 equipos). Guardar esta lista consolidada en un JSON en el scratchpad — este archivo es el que consume el paso 3.

Nota: si por algún motivo el endpoint de datos no existe para esa competición, hay un plan B más lento: en la página de "Fixtures" existe un botón `#dayChangeBtn-prev` que retrocede un mes en la vista; se puede hacer click con `document.getElementById('dayChangeBtn-prev').click()` (vía evaluate, para evitar que un pop-up de notificaciones intercepte el click real) y extraer los links de partido visibles con `document.querySelectorAll('a[href*="/matches/"][href*="/live/"]')`, repitiendo hasta cubrir toda la temporada.

## Paso 3 — Descargar el HTML de cada partido

Para cada partido de la lista consolidada, comprobar primero el formato de nombre de archivo ya usado en `partidos_html/` para esa liga (o una liga similar ya descargada, p.ej. Premier League) con:

```bash
ls partidos_html | grep "<Liga>" | head -5
```

El patrón habitual es:

```
{Local} {golesLocal} - {golesVisitante} {Visitante} - {Liga} {temporada con guion bajo}.html
```

p.ej. `Bayern Munich 6 - 0 RB Leipzig - Bundesliga 2025_2026.html`.

Para cada partido, un único `browser_evaluate`:

```js
async () => {
  const res = await fetch('https://www.whoscored.com/matches/<ID>/live');
  return await res.text();
}
```

con `filename` = `partidos_html/<nombre exacto>.html`. Esto escribe el HTML directo a disco sin devolverlo inline (cada página pesa ~1-1.5MB; devolverlo inline rompe el límite de tokens de la tool).

No usar `browser_navigate` para esto — el `fetch()` desde la página ya cargada es más rápido (no carga imágenes/anuncios/scripts) y ya se ha confirmado que devuelve el HTML completo con el bloque `matchCentreData` embebido (los mismos datos que tendría la página renderizada).

### ⚠️ Bug conocido del MCP: el `filename` de `browser_evaluate` a veces guarda el resultado como JSON-string en vez de texto plano

Detectado el 2026-07-14 (Bundesliga/Ligue 1/Serie A/Eredivisie): en vez de escribir el HTML devuelto por el `fetch()` tal cual, el paquete `@playwright/mcp` (instalado vía `npx -y @playwright/mcp@latest`, o sea sin versión fija — el comportamiento puede cambiar de una sesión a otra sin aviso) guardó el archivo como si hubiera hecho `JSON.stringify(html)`: el archivo entero queda envuelto en comillas, con `\r\n` y `\"` escapados en vez de saltos de línea y comillas reales. `parser.py` truena con `Expecting property name enclosed in double quotes` porque el bloque `matchCentreData` que busca también queda doble-escapado.

Es recuperable sin volver a descargar (el HTML original vive intacto dentro del string JSON) — después de CADA tanda de descargas, antes de pasar a `parser.py`, correr esto:

```python
import glob, json

reparados = 0
for f in glob.glob("partidos_html/*<Liga> <temporada>.html"):
    with open(f, "rb") as fh:
        primero = fh.read(1)
    if primero != b'"':
        continue  # archivo sano, HTML crudo normal
    with open(f, encoding="utf-8") as fh:
        contenido = fh.read()
    html = json.loads(contenido)  # des-escapa
    assert isinstance(html, str) and "matchCentreData" in html
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(html)
    reparados += 1

print(f"Reparados: {reparados}")
```

Si `reparados` da 0, no hubo bug esta vez. Si da más de 0, quedó arreglado in-place; no hace falta re-descargar nada.

## Paso 4 — Delegar el volumen a un agente en background

Descargar una temporada completa son 300+ llamadas de tool, una por partido. Para no saturar el contexto de la conversación principal, lanzar un `Agent` (`subagent_type: general-purpose`, `run_in_background: true`) que:

- Reciba en el prompt la ruta al JSON consolidado del paso 2, la convención de nombre exacta, y el snippet de fetch+filename del paso 3.
- Aclarar explícitamente que NO debe usar `browser_navigate` ni devolver el HTML inline, y que debe saltarse archivos que ya existan (para poder resumir si se corta a medias).
- Pida que verifique periódicamente (`matchCentreData` presente, tamaño >500KB) y que reintente una vez si un fetch falla o vuelve corto (posible bloqueo de Cloudflare reaparecido), y que se detenga y reporte si el bloqueo persiste en vez de insistir.
- El agente en background reutiliza la MISMA sesión del navegador Playwright MCP (mismo proceso), así que no hace falta re-autenticar ni volver a pasar Cloudflare.

## Paso 5 — Verificar de forma independiente

Al terminar el agente, NO fiarse solo de su reporte — verificar con bash:

```bash
ls partidos_html | grep -c "<Liga> <temporada>"
find partidos_html -name "*<Liga> <temporada>.html" -size -500k | wc -l   # debe dar 0
grep -L "matchCentreData" partidos_html/*"<Liga> <temporada>.html" | wc -l  # debe dar 0
```

Comparar el conteo final contra el número esperado de partidos de la temporada.

**Esto solo confirma que el string `matchCentreData` está presente — NO que el JSON sea válido ni que el contenido corresponda al partido correcto.** Para una verificación real del contenido, parsear el JSON embebido y confirmar que coincide con lo esperado. El bloque va como `matchCentreData: {...}` pero con las comillas internas escapadas (`\"`), así que hay que des-escapar antes de parsear:

```python
import json, glob

def extract_match_centre_json(content):
    key = 'matchCentreData: {'
    idx = content.find(key)
    if idx == -1:
        return None
    brace_start = idx + len(key) - 1
    depth = 0
    i = brace_start
    while i < len(content):
        c = content[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return content[brace_start:i+1].replace('\\"', '"')
        i += 1
    return None

for f in glob.glob('partidos_html/*<Liga> <temporada>.html'):
    content = open(f, encoding='utf-8', errors='ignore').read()
    raw = extract_match_centre_json(content)
    data = json.loads(raw)  # debe parsear sin error
    assert data.get('home', {}).get('name') and data.get('away', {}).get('name')
    assert len(data.get('events', []) or []) > 50  # partido real trae cientos/miles de eventos
```

Correr esto sobre TODOS los archivos de la liga (no solo una muestra) antes de dar la descarga por completa — es barato (segundos) y es la única forma de confirmar que el contenido es real y utilizable, no solo que el archivo "parece" tener el tamaño correcto.

## Cuidado con competiciones que tienen varios "stages" en la misma temporada

Algunas ligas (p.ej. Eredivisie) dividen la temporada en varios `stageId` distintos dentro del mismo `seasonId`: la liga regular y, además, un stage de playoffs (p.ej. "Eredivisie ECL Playoff"). El link "Show"/"Summary" al que redirige el selector de temporada puede apuntar por defecto al stage de playoffs en vez de al de liga regular.

Antes de asumir el `stageId`, revisar si existe un combobox adicional de "stages" en la página (además de tournaments/seasons) y comprobar sus opciones vía evaluate:

```js
() => Array.from(document.querySelectorAll('select')).map((sel,i)=>({i, id:sel.id, options: Array.from(sel.options).map(o=>({value:o.value,text:o.text,selected:o.selected}))}))
```

Elegir el `stageId` cuyo texto sea el nombre de la liga regular (no "Playoff", "Relegation", "Championship Round", etc.), y verificar con el endpoint de datos que el conteo de partidos coincide con lo esperado (equipos × (equipos-1)) antes de seguir.

## Aprendizajes de la primera ejecución (Bundesliga 25/26)

- El popup de suscripción a notificaciones push (`.webpush-swal2-container`) intercepta clicks reales del mouse; si se necesita clickear algo en la UI, hacerlo vía `element.click()` en JS (evaluate) en vez de `browser_click`, o eliminar el overlay primero con `document.querySelector('.webpush-swal2-container')?.remove()`.
- Los IDs de partido de WhoScored NO son contiguos por competición/temporada de forma fiable en toda la temporada (hay bloques contiguos localmente por reprogramaciones, pero no se puede asumir un rango numérico completo sin gaps para toda la temporada) — por eso el paso 2 (endpoint de datos) es más fiable que adivinar rangos de ID.
- `mcp__playwright__browser_click` requiere el parámetro `target` (no `ref`) con la referencia exacta del snapshot.

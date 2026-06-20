with open('index.html') as f:
    contenido = f.read()

# Fix 1: radio de nodos basado en pases, no en toques genericos
viejo1 = """      const maxToques = Math.max(...equipo.jugadores.map(j => j.toques));
      const minToques = Math.min(...equipo.jugadores.map(j => j.toques));
      const rangoToques = (maxToques - minToques) || 1;
      const radioMinimo = 15;
      const radioMaximo = 30;
      const posicionesPorId = {};
      equipo.jugadores.forEach(j => {
        const [cx, cy] = aCancha(j.x, 100 - j.y);
        const radio = radioMinimo + ((j.toques - minToques) / rangoToques) * (radioMaximo - radioMinimo);
        posicionesPorId[j.id] = { jugador: j, cx, cy, radio };
      });"""

nuevo1 = """      const pasesPorJugador = {};
      equipo.jugadores.forEach(j => { pasesPorJugador[j.id] = 0; });
      (equipo.pases || []).forEach(p => {
        pasesPorJugador[p.de] = (pasesPorJugador[p.de] || 0) + p.veces;
        pasesPorJugador[p.a] = (pasesPorJugador[p.a] || 0) + p.veces;
      });
      const valoresPases = equipo.jugadores.map(j => pasesPorJugador[j.id] || 0);
      const maxPases = Math.max(...valoresPases);
      const minPases = Math.min(...valoresPases);
      const rangoPases = (maxPases - minPases) || 1;
      const radioMinimo = 12;
      const radioMaximo = 32;
      const posicionesPorId = {};
      equipo.jugadores.forEach(j => {
        const [cx, cy] = aCancha(j.x, 100 - j.y);
        const valor = pasesPorJugador[j.id] || 0;
        const radio = radioMinimo + ((valor - minPases) / rangoPases) * (radioMaximo - radioMinimo);
        posicionesPorId[j.id] = { jugador: j, cx, cy, radio };
      });"""

if viejo1 not in contenido:
    print("FALLO fix 1: bloque no encontrado")
else:
    contenido = contenido.replace(viejo1, nuevo1)
    print("OK fix 1")

# Fix 3: refrescar selector de jugador al cambiar de partido
viejo3 = """    function actualizarTodo(datos, lado) {
      actualizarMarcador(datos);
      actualizarEstadisticas(datos);
      actualizarGoles(datos);
      dibujarVistaActual(datos, lado);
    }"""

nuevo3 = """    function actualizarTodo(datos, lado) {
      actualizarMarcador(datos);
      actualizarEstadisticas(datos);
      actualizarGoles(datos);
      poblarSelectorJugador(datos, lado);
      dibujarVistaActual(datos, lado);
    }"""

if viejo3 not in contenido:
    print("FALLO fix 3: bloque no encontrado")
else:
    contenido = contenido.replace(viejo3, nuevo3)
    print("OK fix 3")

# Fix 4: colores distinguibles en Action map
viejo4 = """      const grisPorTipo = {};
      ordenTipos.forEach((tipo, i) => {
        const valor = Math.round(20 + (i / (ordenTipos.length - 1)) * 170);
        grisPorTipo[tipo] = `rgb(${valor},${valor},${valor})`;
      });"""

nuevo4 = """      const grisPorTipo = {
        TakeOn: '#1a1a1a',
        BallRecovery: '#2563eb',
        Interception: '#16a34a',
        Tackle: '#dc2626',
        Aerial: '#9333ea',
        Clearance: '#0891b2',
        BlockedPass: '#ea580c',
        Challenge: '#65a30d',
        Foul: '#be185d',
        Dispossessed: '#78716c',
      };"""

if viejo4 not in contenido:
    print("FALLO fix 4: bloque no encontrado")
else:
    contenido = contenido.replace(viejo4, nuevo4)
    print("OK fix 4")

# Fix 5: tamano del recuadro de la cancha
viejo5 = """  svg {
    background: #f7f6f3;
    border-radius: 8px;
    width: 100%;
    height: auto;
  }"""

nuevo5 = """  svg {
    background: #f7f6f3;
    border-radius: 8px;
    width: 100%;
    max-width: 420px;
    height: auto;
    display: block;
    margin: 0 auto;
  }"""

if viejo5 not in contenido:
    print("FALLO fix 5: bloque no encontrado")
else:
    contenido = contenido.replace(viejo5, nuevo5)
    print("OK fix 5")

with open('index.html', 'w') as f:
    f.write(contenido)
print("ARCHIVO GUARDADO")

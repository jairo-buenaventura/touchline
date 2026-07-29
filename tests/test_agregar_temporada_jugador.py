"""Tests de agregar_temporada_jugador.py con un partido sintetico (no toca data/)."""
import agregar_temporada_jugador as atj

PARTIDO_SINTETICO = {
    "competicion": "liga_de_prueba",
    "temporada": "99/00",
    "home": {
        "equipo": "Equipo A",
        "jugadores": [{"id": 1, "nombre": "Jugador Uno", "x": 50.0, "y": 50.0, "toques": 40}],
        "pases": [{"de": 1, "a": 2, "veces": 5}],
        "tiros": [
            {"minuto": 10, "jugador": "Jugador Uno", "resultado": "Goal", "x": 90, "y": 50},
            {"minuto": 20, "jugador": "Jugador Uno", "resultado": "MissedShots", "x": 85, "y": 40},
        ],
        "acciones": [
            {"id": 1, "nombre": "Jugador Uno", "acciones": [
                {"tipo": "Aerial", "x": 60, "y": 40, "exitoso": True},
                {"tipo": "Aerial", "x": 61, "y": 41, "exitoso": False},
            ]}
        ],
        "recepcion_pases": [
            {"id": 1, "nombre": "Jugador Uno", "recepciones": [{"x": 70, "y": 50}],
             "pases_clave_recibidos": [], "asistencias_recibidas": [],
             "en_tercio_final": 3, "en_area_rival": 1, "cruces_recibidos": 0},
        ],
        "alineacion": {"formacion": "4-4-2", "titulares": [{"id": 1, "posicion": "FW"}], "banca": []},
    },
    "away": {
        "equipo": "Equipo B",
        "jugadores": [],
        "pases": [],
        "tiros": [],
        "acciones": [],
        "recepcion_pases": [],
        "alineacion": {"formacion": "4-3-3", "titulares": [], "banca": []},
    },
}


def test_procesar_lado_extrae_metricas_correctas():
    filas = []
    atj.procesar_lado(PARTIDO_SINTETICO, "home", filas)
    assert len(filas) == 1
    fila = filas[0]
    assert fila["nombre"] == "Jugador Uno"
    assert fila["toques"] == 40
    assert fila["pases_dados"] == 5
    assert fila["tiros"] == 2
    assert fila["goles"] == 1
    assert fila["tiros_al_arco"] == 1  # el Goal cuenta como al arco, el MissedShots no
    assert fila["acc_Aerial_total"] == 2
    assert fila["acc_Aerial_exitosas"] == 1
    assert fila["recepciones"] == 1
    assert fila["en_tercio_final"] == 3
    assert fila["posicion"] == "FW"
    assert fila["formacion_equipo"] == "4-4-2"


def test_procesar_lado_lado_vacio_no_genera_filas():
    filas = []
    atj.procesar_lado(PARTIDO_SINTETICO, "away", filas)
    assert filas == []

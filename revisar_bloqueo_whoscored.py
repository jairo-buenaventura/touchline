"""
revisar_bloqueo_whoscored.py
------------------------------
Diagnostico simple: hace una peticion normal a WhoScored y revisa si
la respuesta es la pagina real o la pantalla de bloqueo de Cloudflare
("Attention Required" / "Just a moment..."). No intenta evadir nada,
solo te dice que esta pasando.

Uso:
    python3 revisar_bloqueo_whoscored.py
"""

import urllib.request
import urllib.error

URL_PRUEBA = "https://www.whoscored.com/regions/81/tournaments/3/alemania-bundesliga"

SEÑALES_BLOQUEO = [
    "attention required",
    "just a moment",
    "cf-browser-verification",
    "cloudflare",
    "checking your browser",
]


def main():
    print(f"Probando: {URL_PRUEBA}\n")
    req = urllib.request.Request(
        URL_PRUEBA,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            codigo = resp.status
            contenido = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        codigo = e.code
        contenido = e.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"No se pudo conectar: {e}")
        return

    print(f"Codigo de respuesta HTTP: {codigo}")
    contenido_lower = contenido.lower()
    bloqueado = any(señal in contenido_lower for señal in SEÑALES_BLOQUEO)

    if bloqueado:
        print("\n[BLOQUEADO] La respuesta parece ser la pantalla de Cloudflare, no la pagina real.")
        print("Esto es normal para peticiones automatizadas simples (como esta).")
        print("No dice nada sobre si TU NAVEGADOR (Safari/Chrome) tambien esta bloqueado.")
    elif "bundesliga" in contenido_lower or "whoscored" in contenido_lower:
        print("\n[OK] La respuesta parece ser contenido real de WhoScored, no un bloqueo.")
    else:
        print("\n[SIN DETERMINAR] La respuesta no coincide claramente con ninguno de los dos casos.")
        print("Primeros 300 caracteres de la respuesta, para revisar a ojo:")
        print(contenido[:300])


if __name__ == "__main__":
    main()

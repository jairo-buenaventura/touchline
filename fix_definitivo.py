with open('fotmob_parser.py', 'r', encoding='utf-8') as f:
    contenido = f.read()

viejo = '''def encontrar_archivo_json(home_fotmob, away_fotmob, carpeta_data):
    candidatos = list(carpeta_data.glob("*.json"))
    candidatos = [c for c in candidatos if c.name != "lista.json"]
    h = normalizar(home_fotmob)
    a = normalizar(away_fotmob)
    h_tokens = set(h.split())
    a_tokens = set(a.split())
    for c in candidatos:
        nombre = normalizar(c.stem)
        nombre_tokens = set(nombre.replace("-", " ").split())
        if h_tokens & nombre_tokens and a_tokens & nombre_tokens:
            return c
    return None'''

nuevo = '''def encontrar_archivo_json(home_fotmob, away_fotmob, carpeta_data, nombre_html_stem=None):
    candidatos = list(carpeta_data.glob("*.json"))
    candidatos = [c for c in candidatos if c.name != "lista.json"]

    # Primero: intento exacto, quitando el sufijo _FotMob del nombre del HTML
    if nombre_html_stem:
        stem_limpio = nombre_html_stem
        if stem_limpio.endswith("_FotMob"):
            stem_limpio = stem_limpio[: -len("_FotMob")]
        for c in candidatos:
            if c.stem == stem_limpio:
                return c

    # Fallback: matching por substring exacto de nombres completos (no tokens sueltos)
    h = normalizar(home_fotmob)
    a = normalizar(away_fotmob)
    for c in candidatos:
        nombre = normalizar(c.stem)
        if h in nombre and a in nombre:
            return c
    return None'''

if viejo not in contenido:
    print("FALLO: no se encontro el texto exacto")
else:
    contenido = contenido.replace(viejo, nuevo)

    # Tambien actualizamos la llamada en main() para pasar el nombre del archivo html
    viejo_llamada = '''ruta_json = encontrar_archivo_json(
            datos_fotmob["home_nombre"], datos_fotmob["away_nombre"], carpeta_data
        )'''
    nuevo_llamada = '''ruta_json = encontrar_archivo_json(
            datos_fotmob["home_nombre"], datos_fotmob["away_nombre"], carpeta_data, archivo.stem
        )'''
    contenido = contenido.replace(viejo_llamada, nuevo_llamada)

    with open('fotmob_parser.py', 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("OK: parche aplicado")

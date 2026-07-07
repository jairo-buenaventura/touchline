with open('fotmob_parser.py', 'r', encoding='utf-8') as f:
    contenido = f.read()

viejo = '''def encontrar_archivo_json(home_fotmob, away_fotmob, carpeta_data):
    candidatos = list(carpeta_data.glob("*.json"))
    candidatos = [c for c in candidatos if c.name != "lista.json"]
    h = normalizar(home_fotmob)
    a = normalizar(away_fotmob)
    for c in candidatos:
        nombre = normalizar(c.stem)
        if h in nombre and a in nombre:
            return c
    return None'''

nuevo = '''def encontrar_archivo_json(home_fotmob, away_fotmob, carpeta_data):
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

if viejo not in contenido:
    print("FALLO: no se encontro el texto exacto")
else:
    contenido = contenido.replace(viejo, nuevo)
    with open('fotmob_parser.py', 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("OK: parche aplicado")

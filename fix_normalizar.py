with open('fotmob_parser.py', 'r', encoding='utf-8') as f:
    contenido = f.read()

viejo = '''def normalizar(nombre):
    base = nombre.strip().lower().replace("ó", "o").replace("í", "i")
    base = base.replace("cape verde", "cabo verde")
    base = base.replace("south korea", "republic of korea")
    return base'''

nuevo = '''import unicodedata

def normalizar(nombre):
    base = nombre.strip().lower()
    base = "".join(c for c in unicodedata.normalize("NFD", base) if unicodedata.category(c) != "Mn")
    base = base.replace("cape verde", "cabo verde")
    base = base.replace("south korea", "republic of korea")
    base = base.replace("atletico madrid", "atletico")
    base = base.replace("deportivo alaves", "alaves")
    return base'''

if viejo not in contenido:
    print("FALLO: no se encontro el texto exacto")
else:
    contenido = contenido.replace(viejo, nuevo)
    with open('fotmob_parser.py', 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("OK: parche aplicado")

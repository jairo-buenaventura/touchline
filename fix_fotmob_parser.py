with open('fotmob_parser.py', 'r', encoding='utf-8') as f:
    contenido = f.read()

viejo = '''        if valor is None:
            return None, None
        m2 = re.match(r"([\d.]+)\s*\((\d+)%\)", valor)'''

nuevo = '''        if valor is None:
            return None, None
        if not isinstance(valor, str):
            return num(valor), None
        m2 = re.match(r"([\d.]+)\s*\((\d+)%\)", valor)'''

if viejo not in contenido:
    print("FALLO: no se encontro el texto exacto")
else:
    contenido = contenido.replace(viejo, nuevo)
    with open('fotmob_parser.py', 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("OK: parche aplicado")

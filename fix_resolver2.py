with open('resolver_fotmob_pendientes.py', 'r', encoding='utf-8') as f:
    contenido = f.read()

viejo = "fragmento = html[idx:idx+900]"
nuevo = "fragmento = html[idx:idx+1500]"

if viejo not in contenido:
    print("FALLO: no se encontro el texto exacto")
else:
    contenido = contenido.replace(viejo, nuevo)
    with open('resolver_fotmob_pendientes.py', 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("OK: parche aplicado")

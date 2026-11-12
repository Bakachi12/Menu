"""Configuración del menú de la terminal principal."""
BEBIDAS = 'Bebidas'
COCINA = 'Cocina'
ACOMPANAMIENTO = 'Acompañamiento'
SECCIONES = (BEBIDAS, COCINA, ACOMPANAMIENTO)


def seccion_inicial(nombre, categoria):
    categoria = categoria.strip().casefold()
    if categoria in ('acompañamiento', 'acompañamientos'):
        return ACOMPANAMIENTO
    if categoria in ('cocina', 'comida', 'comidas', 'postre', 'postres'):
        return COCINA
    if categoria == 'general' and nombre.casefold() in ('hamburguesa', 'camarones'):
        return COCINA
    return BEBIDAS


def preparaciones_iniciales(nombre):
    return 'Al ajillo, Fritos, En salsa roja' if nombre.strip().casefold() == 'camarones' else ''


def opciones(texto):
    return list(dict.fromkeys(valor.strip() for valor in texto.split(',') if valor.strip()))


def acompanamientos(catalogo):
    nombres = [p['nombre'] for p in catalogo if p['seccion'] == ACOMPANAMIENTO]
    return list(dict.fromkeys(nombres)) or ['Papas fritas', 'Patacones', 'Yuca']

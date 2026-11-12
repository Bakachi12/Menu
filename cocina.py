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


def preparar_cocina(db):
    db.execute("""CREATE TABLE IF NOT EXISTS recargos_acompanamiento (
        nombre TEXT PRIMARY KEY, centimos INTEGER NOT NULL CHECK(centimos > 0))""")
    db.execute("""CREATE TABLE IF NOT EXISTS ordenes_cocina (
        id INTEGER PRIMARY KEY AUTOINCREMENT, unidad TEXT NOT NULL UNIQUE,
        mesa TEXT NOT NULL, cliente TEXT NOT NULL, plato TEXT NOT NULL,
        preparacion TEXT NOT NULL, acompanamiento TEXT NOT NULL, extra TEXT NOT NULL,
        fecha TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
        estado TEXT NOT NULL DEFAULT 'pendiente')""")
    db.execute("CREATE INDEX IF NOT EXISTS cocina_pendientes ON ordenes_cocina(estado, id)")


def sincronizar_comandas(db, mesa, anteriores, actuales):
    anteriores_ids = {p['unidad_cocina'] for p in anteriores if p.get('unidad_cocina')}
    actuales_ids = set()
    for p in actuales:
        unidad = p.get('unidad_cocina')
        if not unidad:
            continue
        actuales_ids.add(unidad)
        if unidad not in anteriores_ids:
            db.execute("""INSERT INTO ordenes_cocina
                (unidad, mesa, cliente, plato, preparacion, acompanamiento, extra)
                VALUES (?,?,?,?,?,?,?)""",
                (unidad, mesa, p.get('cliente_nombre', ''), p['nombre'], p.get('preparacion', ''),
                 p.get('acompanamiento', ''), p.get('extra', '')))
    for unidad in anteriores_ids - actuales_ids:
        db.execute("UPDATE ordenes_cocina SET estado='retirada' WHERE unidad=? AND estado='pendiente'", (unidad,))

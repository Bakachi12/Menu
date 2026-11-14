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


def preparaciones_con_recargo(texto):
    import json
    try:
        valores = json.loads(texto)
    except (ValueError, TypeError):
        valores = None
    if isinstance(valores, list):
        return {v['nombre']: max(0, int(v.get('centimos', 0))) for v in valores
                if isinstance(v, dict) and isinstance(v.get('nombre'), str) and v['nombre'].strip()}
    return dict.fromkeys((valor.strip() for valor in (texto or '').split(',') if valor.strip()), 0)


def seleccion_preparaciones(valor, disponibles):
    if isinstance(valor, str):
        valores = [valor] if valor in disponibles else (valor.split(' · ') if valor else [])
    elif isinstance(valor, list):
        valores = valor
    else:
        raise ValueError('Selecciona preparaciones válidas.')
    if (len(valores) > len(disponibles) or any(not isinstance(v, str) or v not in disponibles for v in valores)
            or len(set(valores)) != len(valores)):
        raise ValueError('La preparación ya no está disponible.')
    return valores


def opciones(texto):
    return list(preparaciones_con_recargo(texto))


def acompanamientos(catalogo):
    nombres = [p['nombre'] for p in catalogo if p['seccion'] == ACOMPANAMIENTO]
    return list(dict.fromkeys(nombres)) or ['Papas fritas', 'Patacones', 'Yuca']


def preparar_cocina(db):
    db.execute("CREATE TABLE IF NOT EXISTS platos_agotados (producto_id INTEGER PRIMARY KEY)")
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
        db.execute("UPDATE ordenes_cocina SET estado='retirada' WHERE unidad=? AND estado IN ('pendiente','lista')", (unidad,))


def platos_cocina(db):
    filas = db.execute("""SELECT p.id,p.nombre,p.categoria,p.seccion,a.producto_id IS NULL
        FROM productos p LEFT JOIN platos_agotados a ON a.producto_id=p.id
        WHERE p.activo=1 ORDER BY p.nombre COLLATE NOCASE, p.id""")
    return [dict(id=i, nombre=n, categoria=c, disponible=bool(disponible))
            for i,n,c,seccion,disponible in filas if (seccion or seccion_inicial(n,c)) == COCINA]


def cambiar_disponibilidad(db, identificador, disponible):
    db.execute("BEGIN IMMEDIATE")
    if not any(p['id'] == identificador for p in platos_cocina(db)):
        raise ValueError('El plato ya no pertenece al menú de cocina.')
    if disponible:
        db.execute("DELETE FROM platos_agotados WHERE producto_id=?", (identificador,))
    else:
        db.execute("INSERT OR IGNORE INTO platos_agotados VALUES (?)", (identificador,))


def validar_aumentos(db, anteriores, actuales):
    from collections import Counter
    def cantidades(productos):
        return Counter((p['nombre'], p.get('categoria', 'General')) for p in productos)
    aumentos = cantidades(actuales) - cantidades(anteriores)
    if aumentos:
        for nombre, categoria in db.execute("""SELECT p.nombre,p.categoria FROM platos_agotados a
                JOIN productos p ON p.id=a.producto_id"""):
            if (nombre, categoria) in aumentos:
                raise ValueError(f'{nombre}: No disponible')

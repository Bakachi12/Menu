"""Guía de datos: prepara la base local y las tablas de productos y ventas.

Las migraciones deben conservar la información anterior. Nunca se reemplaza
una base de datos existente con una vacía al actualizar el programa.
"""
from contextlib import closing
from pathlib import Path
from datetime import datetime
from uuid import uuid4
import sqlite3
import sys
import json
from PySide6.QtCore import QStandardPaths
from cocina import BEBIDAS, COCINA, seccion_inicial, preparaciones_iniciales
from clientes import centimos, nombre_operacion

def preparar_archivo_datos(carpeta):
    carpeta_datos = Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.GenericDataLocation
    )) / "TPVBar"
    carpeta_datos.mkdir(parents=True, exist_ok=True)
    destino = carpeta_datos / "ventas.db"

    # Una actualización nunca sustituye una base de datos que ya existe.
    if destino.exists():
        return destino

    carpeta_anterior = (Path(sys.executable).resolve().parent
                        if getattr(sys, "frozen", False) else carpeta)
    anterior = carpeta_anterior / "ventas.db"
    if not anterior.exists():
        return destino

    temporal = carpeta_datos / f"migracion-{uuid4().hex}.db"
    try:
        # SQLite backup conserva una copia coherente, incluido el diario WAL.
        with closing(sqlite3.connect(anterior.as_uri() + "?mode=ro", uri=True)) as origen:
            with closing(sqlite3.connect(str(temporal))) as copia:
                origen.backup(copia)
                if copia.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("La copia de la base de datos no pasó la comprobación.")
        # En Windows rename no sobrescribe un destino creado por otro proceso.
        try:
            temporal.rename(destino)
        except FileExistsError:
            pass
    finally:
        if temporal.exists():
            temporal.unlink()

    # La base original se conserva como respaldo.
    return destino


def inicializar_catalogo(sesion, productos_iniciales):
    """Crea tablas y agrega las columnas que falten, sin borrar productos ni ventas."""
    with sesion.conexion() as conexion:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                mesa TEXT NOT NULL,
                cliente TEXT,
                productos TEXT NOT NULL,
                total REAL NOT NULL
            )
        """)
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                precio_centimos INTEGER NOT NULL CHECK (precio_centimos > 0),
                categoria TEXT NOT NULL DEFAULT 'General',
                UNIQUE(nombre, categoria)
            )
        """)
        columnas_ventas = {fila[1] for fila in conexion.execute('PRAGMA table_info(ventas)')}
        for nombre, tipo in [('metodo_pago', 'TEXT'), ('cajero_id', 'INTEGER'), ('hoja_libre_id', 'INTEGER')]:
            if nombre not in columnas_ventas:
                conexion.execute(f'ALTER TABLE ventas ADD COLUMN {nombre} {tipo}')
        columnas = {
            fila[1]
            for fila in conexion.execute("PRAGMA table_info(productos)")
        }

        if "activo" not in columnas:
            conexion.execute("""
                ALTER TABLE productos
                ADD COLUMN activo INTEGER NOT NULL DEFAULT 1
            """)
        if "imagen" not in columnas:
            conexion.execute("""
                ALTER TABLE productos
                ADD COLUMN imagen TEXT
            """)
        if "seccion" not in columnas:
            conexion.execute("ALTER TABLE productos ADD COLUMN seccion TEXT")
        if "cantidad_acompanamientos" not in columnas:
            conexion.execute("ALTER TABLE productos ADD COLUMN cantidad_acompanamientos INTEGER NOT NULL DEFAULT 1")
        if "lleva_acompanamiento" not in columnas:
            conexion.execute("ALTER TABLE productos ADD COLUMN lleva_acompanamiento INTEGER NOT NULL DEFAULT 1")
            conexion.execute("UPDATE productos SET lleva_acompanamiento=0 WHERE lower(trim(nombre)) IN ('salchipapa', 'salchipapas')")
        if "preparaciones" not in columnas:
            conexion.execute("ALTER TABLE productos ADD COLUMN preparaciones TEXT")
        for producto in productos_iniciales:
            conexion.execute(
                "INSERT INTO productos(nombre, precio_centimos, categoria) VALUES (?, ?, ?) "
                "ON CONFLICT(nombre, categoria) DO NOTHING",
                (producto['nombre'], centimos(producto), 'General'),
            )

        sin_seccion = conexion.execute("SELECT id,nombre,categoria FROM productos WHERE seccion IS NULL OR seccion=''").fetchall()
        conexion.executemany("UPDATE productos SET seccion=? WHERE id=?",
                             [(seccion_inicial(n, c), i) for i, n, c in sin_seccion])
        conexion.execute("""CREATE VIEW IF NOT EXISTS productos_inventario_bar AS
            SELECT * FROM productos WHERE seccion='Bebidas'""")


def cargar_productos(sesion):
    """Devuelve solo productos activos para los botones de las mesas."""
    with sesion.conexion() as conexion:
        filas = conexion.execute(
            "SELECT id, nombre, precio_centimos, categoria, imagen, seccion, preparaciones, lleva_acompanamiento, cantidad_acompanamientos "
            "FROM productos WHERE activo = 1 ORDER BY id"
        ).fetchall()
    return [dict(id=identificador, nombre=n, precio=p / 100, categoria=c, imagen=i,
                 seccion=seccion or seccion_inicial(n, c),
                 preparaciones=preparaciones_iniciales(n) if prep is None else prep, lleva_acompanamiento=bool(lleva), cantidad_acompanamientos=cantidad)
            for identificador, n, p, c, i, seccion, prep, lleva, cantidad in filas]


METODOS_PAGO = ('Clave', 'Visa', 'Yappy', 'Efectivo')


def historial_cobros(sesion):
    """El alcance depende del usuario autenticado, incluso después de cerrar turno."""
    if not sesion.usuario:
        raise PermissionError('Inicia sesión para ver tus cobros.')
    consulta = """SELECT v.id, v.fecha, v.cliente, v.mesa, v.total,
                         COALESCE(v.metodo_pago, 'Sin registrar')
                  FROM ventas v LEFT JOIN turnos t ON t.id = v.turno_id"""
    parametros = ()
    if not sesion.es_admin():
        consulta += ' WHERE COALESCE(v.cajero_id, t.usuario_id) = ?'
        parametros = (sesion.usuario['id'],)
    with sesion.conexion() as db:
        return db.execute(consulta + ' ORDER BY v.id DESC', parametros).fetchall()


def registrar_venta(sesion, nombre_mesa, clientes, productos, turno_id=None, *, metodo_pago):
    """Cobro indivisible: registra venta, elimina pedido abierto y libera clientes.

    Si alguna escritura falla, SQLite revierte las tres operaciones.
    Solo después de que termine esta función se limpia la cuenta en pantalla.
    """
    if sesion.usuario is None:
        raise PermissionError('Inicia sesión para cobrar.')
    if sesion.usuario.get('rol') in ('mesero', 'cocinero'):
        raise PermissionError('Este rol no tiene permiso para cobrar.')
    es_venta_libre = sesion.usuario.get('tipo') == 'venta_libre'
    if turno_id is None and sesion.usuario['rol'] != 'admin' and not es_venta_libre:
        raise PermissionError('Un usuario de caja necesita un turno activo para cobrar.')
    if es_venta_libre and not sesion.inventario_libre_verificado:
        raise PermissionError('Verifica el inventario antes de cobrar.')
    if metodo_pago not in METODOS_PAGO:
        raise ValueError('Selecciona un método de pago.')
    total = sum(centimos(p) for p in productos) / 100
    with sesion.conexion() as conexion:
        conexion.execute('BEGIN IMMEDIATE')
        catalogo = {(n, c): seccion for n, c, seccion in conexion.execute("SELECT nombre,categoria,seccion FROM productos")}
        productos = [dict(p, seccion=catalogo.get((p['nombre'], p.get('categoria', 'General')))
                          or p.get('seccion') or seccion_inicial(p['nombre'], p.get('categoria', 'General')))
                     for p in productos]
        inventariables = [p for p in productos if p['seccion'] == BEBIDAS]
        if es_venta_libre:
            vendidos = {}
            for producto in inventariables:
                clave = (producto.get('id'), producto.get('nombre'), producto.get('categoria', 'General'))
                vendidos[clave] = vendidos.get(clave, 0) + 1
            for (producto_id, nombre, categoria), cantidad in vendidos.items():
                if producto_id is None:
                    fila = conexion.execute(
                        'SELECT id FROM productos WHERE nombre = ? AND categoria = ?',
                        (nombre, categoria),
                    ).fetchone()
                    producto_id = fila[0] if fila else None
                stock = conexion.execute('SELECT cantidad FROM existencias_inventario WHERE producto_id = ?',
                                         (producto_id,)).fetchone() if producto_id else None
                if not stock or stock[0] < cantidad:
                    raise ValueError(f'{nombre}: {cantidad} en el pedido y {stock[0] if stock else 0} disponibles. Vuelve al pedido para ajustar la cantidad.')
                conexion.execute('UPDATE existencias_inventario SET cantidad = cantidad - ? WHERE producto_id = ?',
                                 (cantidad, producto_id))
                conexion.execute('''INSERT INTO movimientos_inventario
                    (producto_id, producto_nombre, producto_categoria, tipo, cantidad, usuario_id, detalle)
                    VALUES (?, ?, ?, 'venta_libre', ?, ?, 'Venta cobrada por el perfil Venta libre')''',
                    (producto_id, nombre, categoria, cantidad, sesion.usuario['id']))
        elif turno_id is not None:
            turno = conexion.execute(
                'SELECT usuario_id, estado FROM turnos WHERE id = ?', (turno_id,)
            ).fetchone()
            if turno != (sesion.usuario['id'], 'activo'):
                raise PermissionError('El turno ya no está activo para este usuario.')
            cantidades_vendidas = {}
            for producto in inventariables:
                clave = (producto.get('nombre'), producto.get('categoria', 'General'))
                cantidades_vendidas[clave] = cantidades_vendidas.get(clave, 0) + 1
            for (nombre, categoria), cantidad in cantidades_vendidas.items():
                existencia_turno = conexion.execute("""
                    SELECT producto_id, producto_categoria, cantidad_apertura, cantidad_vendida
                    FROM turno_inventario
                    WHERE turno_id = ? AND producto_nombre = ? AND producto_categoria = ?
                """, (turno_id, nombre, categoria)).fetchone()
                if existencia_turno is None or existencia_turno[2] is None:
                    raise PermissionError(f'{nombre} no pertenece al inventario de este turno.')
                producto_id, categoria, apertura, vendida = existencia_turno
                if vendida + cantidad > apertura:
                    raise PermissionError(f'No hay suficientes unidades de {nombre} en el turno.')
                conexion.execute("""
                    UPDATE turno_inventario SET cantidad_vendida = cantidad_vendida + ?
                    WHERE turno_id = ? AND producto_id = ?
                """, (cantidad, turno_id, producto_id))
                conexion.execute("""
                    INSERT INTO movimientos_inventario
                        (producto_id, producto_nombre, producto_categoria, tipo, cantidad,
                         usuario_id, turno_id, detalle)
                    VALUES (?, ?, ?, 'venta', ?, ?, ?, ?)
                """, (
                    producto_id, nombre, categoria, cantidad,
                    sesion.usuario['id'], turno_id, f'Cobro · {metodo_pago}',
                ))
        hoja_libre_id=None
        if es_venta_libre:
            from hojas_venta_libre import venta
            hoja_libre_id=venta(conexion,sesion.usuario,productos)
        conexion.execute(
            'INSERT INTO ventas(fecha, mesa, cliente, productos, total, turno_id, metodo_pago, cajero_id, hoja_libre_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), nombre_operacion(nombre_mesa), clientes,
             json.dumps(productos, ensure_ascii=False), total, turno_id, metodo_pago, sesion.usuario['id'], hoja_libre_id),
        )
        conexion.execute('DELETE FROM pedidos_abiertos WHERE mesa = ?', (nombre_mesa,))
        conexion.execute('UPDATE clientes SET mesa = NULL WHERE mesa = ?', (nombre_mesa,))
        # Un pedido pendiente de la cuenta anterior nunca pasa a la siguiente.
        if conexion.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'solicitudes_table'").fetchone():
            conexion.execute("""UPDATE solicitudes_table SET estado = 'rechazada',
                responsable_id = ?, resuelta = ? WHERE mesa = ? AND estado = 'pendiente'""",
                (sesion.usuario['id'], datetime.now().isoformat(timespec='seconds'), nombre_mesa))


def cantidades_cocina_hoy(sesion):
    from collections import Counter
    sesion.exigir_admin()
    hoy = datetime.now().strftime('%Y-%m-%d')
    with sesion.conexion() as db:
        catalogo = {(n,c): seccion for n,c,seccion in db.execute("SELECT nombre,categoria,seccion FROM productos")}
        cantidades = Counter()
        for (contenido,) in db.execute("SELECT productos FROM ventas WHERE substr(fecha,1,10)=?", (hoy,)):
            for p in json.loads(contenido):
                nombre, categoria = p['nombre'], p.get('categoria', 'General')
                seccion = p.get('seccion') or catalogo.get((nombre,categoria)) or seccion_inicial(nombre,categoria)
                if seccion == COCINA:
                    cantidades[nombre] += 1
    return sorted(cantidades.items(), key=lambda par: (-par[1], par[0].casefold()))

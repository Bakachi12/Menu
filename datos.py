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
        for producto in productos_iniciales:
            conexion.execute(
                "INSERT INTO productos(nombre, precio_centimos, categoria) VALUES (?, ?, ?) "
                "ON CONFLICT(nombre, categoria) DO NOTHING",
                (producto['nombre'], centimos(producto), 'General'),
            )


def cargar_productos(sesion):
    """Devuelve solo productos activos para los botones de las mesas."""
    with sesion.conexion() as conexion:
        filas = conexion.execute(
            "SELECT nombre, precio_centimos, categoria, imagen FROM productos WHERE activo = 1 ORDER BY id"
        ).fetchall()
    return [dict(nombre=n, precio=p / 100, categoria=c, imagen=i) for n, p, c, i in filas]


def registrar_venta(sesion, nombre_mesa, clientes, productos, turno_id=None):
    """Cobro indivisible: registra venta, elimina pedido abierto y libera clientes.

    Si alguna escritura falla, SQLite revierte las tres operaciones.
    Solo después de que termine esta función se limpia la cuenta en pantalla.
    """
    if sesion.usuario is None:
        raise PermissionError('Inicia sesión para cobrar.')
    if turno_id is None and sesion.usuario['rol'] != 'admin':
        raise PermissionError('Un usuario de caja necesita un turno activo para cobrar.')
    total = sum(centimos(p) for p in productos) / 100
    with sesion.conexion() as conexion:
        conexion.execute('BEGIN IMMEDIATE')
        if turno_id is not None:
            turno = conexion.execute(
                'SELECT usuario_id, estado FROM turnos WHERE id = ?', (turno_id,)
            ).fetchone()
            if turno != (sesion.usuario['id'], 'activo'):
                raise PermissionError('El turno ya no está activo para este usuario.')
            cantidades_vendidas = {}
            for producto in productos:
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
                    VALUES (?, ?, ?, 'venta', ?, ?, ?, 'Unidades vendidas en un cobro')
                """, (
                    producto_id, nombre, categoria, cantidad,
                    sesion.usuario['id'], turno_id,
                ))
        conexion.execute(
            'INSERT INTO ventas(fecha, mesa, cliente, productos, total, turno_id) VALUES (?, ?, ?, ?, ?, ?)',
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), nombre_operacion(nombre_mesa), clientes,
             json.dumps(productos, ensure_ascii=False), total, turno_id),
        )
        conexion.execute('DELETE FROM pedidos_abiertos WHERE mesa = ?', (nombre_mesa,))
        conexion.execute('UPDATE clientes SET mesa = NULL WHERE mesa = ?', (nombre_mesa,))

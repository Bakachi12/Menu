"""Asignación de inventario y control de turnos de caja."""
import json
import sqlite3
from datetime import datetime, timedelta

from shiboken6 import isValid
from PySide6.QtCore import Qt, QTime, QEvent
from PySide6.QtGui import QIntValidator, QColor, QPainter
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QComboBox, QFrame,
    QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QScroller, QScrollArea, QTimeEdit, QTreeWidget,
    QTreeWidgetItem, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


def _fecha_hora_visible(valor):
    fecha = datetime.fromisoformat(valor) if isinstance(valor, str) else valor
    hora = fecha.strftime("%I:%M %p").lstrip("0")
    return f"{fecha:%d/%m/%Y} {hora}"


class GestionTurnos:
    def __init__(self, sesion):
        self.sesion = sesion
        with sesion.conexion() as db:
            habia_existencias = db.execute("""
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'existencias_inventario'
            """).fetchone() is not None
            db.execute("""
                CREATE TABLE IF NOT EXISTS turnos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                    nombre_cajero TEXT,
                    estado TEXT NOT NULL CHECK(estado IN ('pendiente', 'activo', 'cerrado')),
                    asignacion_fecha TEXT,
                    fecha_programada TEXT,
                    horario_id INTEGER,
                    apertura_fecha TEXT,
                    cierre_fecha TEXT
                )
            """)
            columnas_turnos = {fila[1] for fila in db.execute("PRAGMA table_info(turnos)")}
            if "nombre_cajero" not in columnas_turnos:
                db.execute("ALTER TABLE turnos ADD COLUMN nombre_cajero TEXT")
            if "asignacion_fecha" not in columnas_turnos:
                db.execute("ALTER TABLE turnos ADD COLUMN asignacion_fecha TEXT")
            if "fecha_programada" not in columnas_turnos:
                db.execute("ALTER TABLE turnos ADD COLUMN fecha_programada TEXT")
            if "horario_id" not in columnas_turnos:
                db.execute("ALTER TABLE turnos ADD COLUMN horario_id INTEGER")
            db.execute("""
                CREATE TABLE IF NOT EXISTS turno_inventario (
                    turno_id INTEGER NOT NULL REFERENCES turnos(id),
                    producto_id INTEGER NOT NULL REFERENCES productos(id),
                    producto_nombre TEXT NOT NULL,
                    producto_categoria TEXT NOT NULL DEFAULT 'General',
                    cantidad_asignada INTEGER NOT NULL CHECK(cantidad_asignada >= 0),
                    cantidad_apertura INTEGER CHECK(cantidad_apertura >= 0),
                    cantidad_agregada INTEGER NOT NULL DEFAULT 0 CHECK(cantidad_agregada >= 0),
                    cantidad_vendida INTEGER NOT NULL DEFAULT 0 CHECK(cantidad_vendida >= 0),
                    cantidad_cierre INTEGER CHECK(cantidad_cierre >= 0),
                    PRIMARY KEY(turno_id, producto_id)
                )
            """)
            columnas = {fila[1] for fila in db.execute("PRAGMA table_info(turno_inventario)")}
            if "producto_categoria" not in columnas:
                db.execute("""
                    ALTER TABLE turno_inventario
                    ADD COLUMN producto_categoria TEXT NOT NULL DEFAULT 'General'
                """)
            if "cantidad_vendida" not in columnas:
                db.execute("""
                    ALTER TABLE turno_inventario
                    ADD COLUMN cantidad_vendida INTEGER NOT NULL DEFAULT 0
                """)
            if "cantidad_agregada" not in columnas:
                db.execute("""
                    ALTER TABLE turno_inventario
                    ADD COLUMN cantidad_agregada INTEGER NOT NULL DEFAULT 0
                """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS existencias_inventario (
                    producto_id INTEGER PRIMARY KEY REFERENCES productos(id),
                    producto_nombre TEXT NOT NULL,
                    producto_categoria TEXT NOT NULL,
                    cantidad INTEGER NOT NULL DEFAULT 0 CHECK(cantidad >= 0)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS movimientos_inventario (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    producto_id INTEGER NOT NULL,
                    producto_nombre TEXT NOT NULL,
                    producto_categoria TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    cantidad INTEGER NOT NULL CHECK(cantidad > 0),
                    usuario_id INTEGER,
                    turno_id INTEGER,
                    detalle TEXT NOT NULL DEFAULT ''
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS horario_cajeros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dia_semana INTEGER NOT NULL CHECK(dia_semana BETWEEN 0 AND 6),
                    hora TEXT NOT NULL,
                    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                    UNIQUE(dia_semana, hora)
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS movimientos_inventario_fecha
                ON movimientos_inventario(id DESC)
            """)
            productos = db.execute(
                "SELECT id, nombre, categoria FROM productos_inventario_bar"
            ).fetchall()
            db.executemany("""
                INSERT OR IGNORE INTO existencias_inventario
                    (producto_id, producto_nombre, producto_categoria, cantidad)
                VALUES (?, ?, ?, 0)
            """, productos)
            if not habia_existencias:
                for producto_id, _, _ in productos:
                    anterior = db.execute("""
                        SELECT ti.cantidad_cierre
                        FROM turno_inventario ti JOIN turnos t ON t.id = ti.turno_id
                        WHERE ti.producto_id = ? AND t.estado = 'cerrado'
                              AND ti.cantidad_cierre IS NOT NULL
                        ORDER BY t.id DESC LIMIT 1
                    """, (producto_id,)).fetchone()
                    if anterior:
                        db.execute("""
                            UPDATE existencias_inventario SET cantidad = ?
                            WHERE producto_id = ?
                        """, (anterior[0], producto_id))
            db.execute("""
                UPDATE existencias_inventario
                SET producto_nombre = (
                        SELECT nombre FROM productos
                        WHERE productos.id = existencias_inventario.producto_id
                    ),
                    producto_categoria = (
                        SELECT categoria FROM productos
                        WHERE productos.id = existencias_inventario.producto_id
                    )
                WHERE EXISTS (
                    SELECT 1 FROM productos
                    WHERE productos.id = existencias_inventario.producto_id
                )
            """)
            db.execute("DROP INDEX IF EXISTS un_turno_abierto")
            db.execute("""
                CREATE TRIGGER IF NOT EXISTS un_solo_turno_abierto_al_insertar
                BEFORE INSERT ON turnos
                WHEN NEW.estado IN ('pendiente', 'activo')
                     AND EXISTS (
                         SELECT 1 FROM turnos
                         WHERE estado IN ('pendiente', 'activo')
                     )
                BEGIN
                    SELECT RAISE(ABORT, 'Ya existe un turno sin cerrar');
                END
            """)
            db.execute("""
                CREATE TRIGGER IF NOT EXISTS un_solo_turno_abierto_al_actualizar
                BEFORE UPDATE OF estado ON turnos
                WHEN NEW.estado IN ('pendiente', 'activo')
                     AND EXISTS (
                         SELECT 1 FROM turnos
                         WHERE id != OLD.id
                               AND estado IN ('pendiente', 'activo')
                     )
                BEGIN
                    SELECT RAISE(ABORT, 'Ya existe un turno sin cerrar');
                END
            """)
            columnas_ventas = {fila[1] for fila in db.execute("PRAGMA table_info(ventas)")}
            if "turno_id" not in columnas_ventas:
                db.execute(
                    "ALTER TABLE ventas ADD COLUMN turno_id INTEGER REFERENCES turnos(id)"
                )

    def empleados(self):
        self.sesion.exigir_admin()
        with self.sesion.conexion() as db:
            return db.execute(
                "SELECT id, nombre FROM usuarios WHERE rol = 'mesas' AND tipo = 'normal' AND eliminado=0 ORDER BY nombre"
            ).fetchall()

    def empleados_para_asignacion_tras_cierre(self, turno_cerrado_id):
        self.sesion.responsable_asignacion_tras_cierre(turno_cerrado_id)
        with self.sesion.conexion() as db:
            turno = db.execute(
                "SELECT usuario_id, estado FROM turnos WHERE id = ?",
                (turno_cerrado_id,),
            ).fetchone()
            if (
                turno is None
                or turno[1] != "cerrado"
                or (
                    not self.sesion.es_admin()
                    and turno[0] != self.sesion.usuario["id"]
                )
            ):
                raise PermissionError(
                    "La asignación manual solo está disponible después del cierre autorizado."
                )
            return db.execute(
                "SELECT id, nombre FROM usuarios WHERE rol = 'mesas' AND tipo = 'normal' AND eliminado=0 ORDER BY nombre"
            ).fetchall()

    def horarios_programados(self):
        self.sesion.exigir_admin()
        with self.sesion.conexion() as db:
            return db.execute("""
                SELECT h.id, h.dia_semana, h.hora, h.usuario_id, u.nombre
                FROM horario_cajeros h
                JOIN usuarios u ON u.id = h.usuario_id
                ORDER BY h.dia_semana, h.hora
            """).fetchall()

    def guardar_horario(self, dia_semana, hora, usuario_id):
        self.sesion.exigir_admin()
        if not isinstance(dia_semana, int) or not 0 <= dia_semana <= 6:
            raise ValueError("Selecciona un día válido.")
        try:
            datetime.strptime(hora, "%H:%M")
        except (TypeError, ValueError) as error:
            raise ValueError("Escribe una hora válida en formato HH:MM.") from error
        with self.sesion.conexion() as db:
            existe = db.execute(
                "SELECT 1 FROM usuarios WHERE id = ? AND rol = 'mesas' AND tipo = 'normal' AND eliminado=0",
                (usuario_id,),
            ).fetchone()
            if not existe:
                raise ValueError("Selecciona un cajero válido.")
            try:
                db.execute("""
                    INSERT INTO horario_cajeros(dia_semana, hora, usuario_id)
                    VALUES (?, ?, ?)
                """, (dia_semana, hora, usuario_id))
            except sqlite3.IntegrityError as error:
                raise ValueError(
                    "Ya hay un cajero programado para ese día y hora."
                ) from error

    def eliminar_horario(self, horario_id):
        self.sesion.exigir_admin()
        with self.sesion.conexion() as db:
            db.execute("DELETE FROM horario_cajeros WHERE id = ?", (horario_id,))

    def productos_disponibles(self):
        with self.sesion.conexion() as db:
            return db.execute(
                "SELECT id, nombre, categoria FROM productos_inventario_bar WHERE activo = 1 ORDER BY nombre COLLATE NOCASE, categoria"
            ).fetchall()

    def existencias(self):
        with self.sesion.conexion() as db:
            db.execute("""
                INSERT OR IGNORE INTO existencias_inventario
                    (producto_id, producto_nombre, producto_categoria, cantidad)
                SELECT id, nombre, categoria, 0 FROM productos_inventario_bar
            """)
            db.execute("""
                UPDATE existencias_inventario
                SET producto_nombre = (
                        SELECT nombre FROM productos
                        WHERE productos.id = existencias_inventario.producto_id
                    ),
                    producto_categoria = (
                        SELECT categoria FROM productos
                        WHERE productos.id = existencias_inventario.producto_id
                    )
                WHERE EXISTS (
                    SELECT 1 FROM productos
                    WHERE productos.id = existencias_inventario.producto_id
                )
            """)
            return db.execute("""
                SELECT e.producto_id, e.producto_nombre, e.producto_categoria, e.cantidad
                FROM existencias_inventario e
                JOIN productos_inventario_bar p ON p.id = e.producto_id
                WHERE p.activo = 1
                ORDER BY e.producto_nombre COLLATE NOCASE, e.producto_categoria
            """).fetchall()

    def hoja_inventarios(self):
        from hojas_venta_libre import reporte
        if self.sesion.es_venta_libre():
            return reporte(self.sesion)
        self.sesion.exigir_admin()
        with self.sesion.conexion() as db:
            turnos = db.execute("""
                SELECT t.id,
                       COALESCE(
                           t.asignacion_fecha,
                           (SELECT MIN(m.fecha) FROM movimientos_inventario m
                            WHERE m.turno_id = t.id AND m.tipo = 'entrega_cajero'),
                           t.apertura_fecha
                       ),
                       t.cierre_fecha,
                       COALESCE(t.nombre_cajero, u.nombre), t.estado,
                       ti.producto_nombre, ti.producto_categoria,
                       ti.cantidad_asignada, ti.cantidad_apertura,
                       ti.cantidad_agregada, ti.cantidad_vendida, ti.cantidad_cierre
                FROM turnos t
                JOIN usuarios u ON u.id = t.usuario_id
                JOIN turno_inventario ti ON ti.turno_id = t.id
                WHERE t.estado='cerrado' OR ti.producto_id IN (SELECT id FROM productos_inventario_bar)
                ORDER BY t.id DESC, ti.producto_nombre COLLATE NOCASE,
                         ti.producto_categoria
            """).fetchall()
            ventas = db.execute("""
                SELECT turno_id, productos FROM ventas
                WHERE turno_id IS NOT NULL
            """).fetchall()

        ventas_por_turno = {}
        for turno_id, contenido in ventas:
            try:
                productos_vendidos = json.loads(contenido)
            except (json.JSONDecodeError, TypeError) as error:
                raise ValueError("Una venta del reporte contiene datos dañados.") from error
            if not isinstance(productos_vendidos, list):
                raise ValueError("Una venta del reporte tiene un formato inválido.")
            for producto in productos_vendidos:
                if not isinstance(producto, dict):
                    raise ValueError("Una venta del reporte contiene un producto inválido.")
                nombre = producto.get("nombre")
                if not nombre or producto.get("seccion", "Bebidas") != "Bebidas":
                    continue
                categoria = producto.get("categoria", "General")
                try:
                    precio_centimos = round(float(producto["precio"]) * 100)
                except (KeyError, TypeError, ValueError, OverflowError) as error:
                    raise ValueError(
                        f"No se pudo calcular el importe vendido de {nombre}."
                    ) from error
                clave = (turno_id, nombre, categoria)
                conteo, importe = ventas_por_turno.get(clave, (0, 0))
                ventas_por_turno[clave] = (conteo + 1, importe + precio_centimos)

        reporte = []
        for (turno_id, asignada_fecha, cierre_fecha, cajero, estado, nombre, categoria,
             asignada, apertura, agregada, vendida_registrada, devuelta) in turnos:
            vendida_json, dinero_centimos = ventas_por_turno.get(
                (turno_id, nombre, categoria), (0, 0)
            )
            vendida = max(vendida_registrada, vendida_json)
            cantidad_esperada = (
                apertura if apertura is not None else asignada
            ) + agregada - vendida
            reporte.append({
                "turno_id": turno_id,
                "asignacion_fecha": asignada_fecha,
                "cierre_fecha": cierre_fecha,
                "cajero": cajero,
                "estado": estado,
                "producto": f"{nombre} · {categoria}",
                "nombre": nombre, "categoria": categoria,
                "recibida": apertura if apertura is not None else asignada,
                "agregada": agregada,
                "vendida": vendida,
                "dinero_centimos": dinero_centimos,
                "entregada": devuelta if devuelta is not None else 0,
                "faltante": (
                    max(0, cantidad_esperada - devuelta)
                    if cierre_fecha else None
                ),
                "sobrante": (
                    max(0, devuelta - cantidad_esperada)
                    if cierre_fecha else None
                ),
            })
        from hojas_venta_libre import reporte as reporte_libre
        return reporte + reporte_libre(self.sesion)

    def registrar_entrada(self, producto_id, cantidad):
        self.sesion.exigir_admin()
        if not isinstance(cantidad, int) or cantidad <= 0:
            raise ValueError("La entrada debe ser de al menos una unidad.")
        with self.sesion.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            producto = db.execute("""
                SELECT p.nombre, p.categoria FROM productos_inventario_bar p
                WHERE p.id = ? AND p.activo = 1
            """, (producto_id,)).fetchone()
            if producto is None:
                raise ValueError("Selecciona un producto activo.")
            db.execute("""
                INSERT OR IGNORE INTO existencias_inventario
                    (producto_id, producto_nombre, producto_categoria, cantidad)
                VALUES (?, ?, ?, 0)
            """, (producto_id, producto[0], producto[1]))
            db.execute("""
                UPDATE existencias_inventario
                SET producto_nombre = ?, producto_categoria = ?, cantidad = cantidad + ?
                WHERE producto_id = ?
            """, (producto[0], producto[1], cantidad, producto_id))
            db.execute("""
                INSERT INTO movimientos_inventario
                    (producto_id, producto_nombre, producto_categoria, tipo, cantidad,
                     usuario_id, detalle)
                VALUES (?, ?, ?, 'entrada_admin', ?, ?, 'Entrada nueva de inventario')
            """, (producto_id, producto[0], producto[1], cantidad, self.sesion.usuario["id"]))

    def agregar_inventario_a_turno(self, producto_id, cantidad, password_admin):
        if not self.sesion.usuario or self.sesion.es_admin():
            raise PermissionError("Esta acción debe realizarse desde la sesión del cajero.")
        if not isinstance(cantidad, int) or cantidad <= 0:
            raise ValueError("El inventario agregado debe ser de al menos una unidad.")
        administrador_id = self.sesion.identificar_admin(password_admin)
        if administrador_id is None:
            raise PermissionError("La contraseña de Admin no es correcta.")
        usuario_id = self.sesion.usuario["id"]
        with self.sesion.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            turno = db.execute("""
                SELECT id FROM turnos
                WHERE usuario_id = ? AND estado = 'activo'
            """, (usuario_id,)).fetchone()
            if turno is None:
                raise PermissionError("No hay un turno activo para agregar inventario.")
            producto = db.execute("""
                SELECT p.nombre, p.categoria
                FROM productos_inventario_bar p
                JOIN turno_inventario ti ON ti.producto_id = p.id
                WHERE p.id = ? AND p.activo = 1 AND ti.turno_id = ?
            """, (producto_id, turno[0])).fetchone()
            if producto is None:
                raise ValueError("Selecciona un producto activo del inventario del turno.")
            db.execute("""
                UPDATE turno_inventario
                SET cantidad_agregada = cantidad_agregada + ?
                WHERE turno_id = ? AND producto_id = ?
            """, (cantidad, turno[0], producto_id))
            db.execute("""
                INSERT INTO movimientos_inventario
                    (producto_id, producto_nombre, producto_categoria, tipo, cantidad,
                     usuario_id, turno_id, detalle)
                VALUES (?, ?, ?, 'agregado_turno', ?, ?, ?,
                        'Inventario adicional autorizado por Admin durante el turno')
            """, (
                producto_id, producto[0], producto[1], cantidad,
                administrador_id, turno[0],
            ))

    def agregar_existencia_venta_libre(self, producto_id, cantidad, password_admin):
        if not self.sesion.es_venta_libre():
            raise PermissionError("Esta acción solo está disponible para Venta libre.")
        if not self.sesion.inventario_libre_verificado:
            raise PermissionError("Verifica el inventario antes de agregar existencias.")
        if not isinstance(cantidad, int) or cantidad <= 0:
            raise ValueError("El inventario agregado debe ser de al menos una unidad.")
        administrador_id = self.sesion.identificar_admin(password_admin)
        if administrador_id is None:
            raise PermissionError("La contraseña de Admin no es correcta.")
        with self.sesion.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            producto = db.execute("""
                SELECT nombre, categoria FROM productos_inventario_bar
                WHERE id = ? AND activo = 1
            """, (producto_id,)).fetchone()
            if producto is None:
                raise ValueError("Selecciona un producto activo.")
            db.execute("""
                INSERT OR IGNORE INTO existencias_inventario
                    (producto_id, producto_nombre, producto_categoria, cantidad)
                VALUES (?, ?, ?, 0)
            """, (producto_id, producto[0], producto[1]))
            db.execute("""
                UPDATE existencias_inventario
                SET producto_nombre = ?, producto_categoria = ?, cantidad = cantidad + ?
                WHERE producto_id = ?
            """, (producto[0], producto[1], cantidad, producto_id))
            db.execute("""
                INSERT INTO movimientos_inventario
                    (producto_id, producto_nombre, producto_categoria, tipo, cantidad,
                     usuario_id, detalle)
                VALUES (?, ?, ?, 'entrada_venta_libre', ?, ?, ?)
            """, (
                producto_id, producto[0], producto[1], cantidad,
                administrador_id, "Entrada de inventario autorizada en Venta libre",
            ))
            from hojas_venta_libre import entrada
            entrada(db,self.sesion.usuario,producto_id,cantidad,producto[0],producto[1])

    def turno_abierto(self):
        with self.sesion.conexion() as db:
            fila = db.execute("""
                SELECT t.id, t.usuario_id, COALESCE(t.nombre_cajero, u.nombre),
                       t.estado, t.apertura_fecha, t.fecha_programada
                FROM turnos t JOIN usuarios u ON u.id = t.usuario_id
                WHERE t.estado IN ('pendiente', 'activo')
            """).fetchone()
            if fila is None:
                return None
            turno = dict(
                id=fila[0], usuario_id=fila[1], usuario=fila[2],
                estado=fila[3], apertura_fecha=fila[4], fecha_programada=fila[5],
            )
            turno["productos"] = db.execute("""
                SELECT producto_id, producto_nombre, producto_categoria, cantidad_asignada,
                       cantidad_apertura, cantidad_vendida, cantidad_cierre
                FROM turno_inventario WHERE turno_id = ? AND producto_id IN (SELECT id FROM productos_inventario_bar) ORDER BY producto_nombre COLLATE NOCASE
            """, (turno["id"],)).fetchall()
            return turno

    def turno_del_usuario(self, usuario_id):
        turno = self.turno_abierto()
        return turno if turno and turno["usuario_id"] == usuario_id else None

    def permite_operar(self):
        if self.sesion.usuario and self.sesion.usuario.get('rol') == 'mesero':
            return True
        if self.sesion.usuario and self.sesion.usuario.get('rol') == 'cocinero':
            return False
        if self.sesion.es_admin():
            return True
        if self.sesion.es_venta_libre():
            return self.sesion.inventario_libre_verificado
        return bool(
            self.sesion.usuario
            and (turno := self.turno_del_usuario(self.sesion.usuario["id"]))
            and turno["estado"] == "activo"
        )

    def exigir_turno_activo(self):
        self.exigir_acceso_venta()

    def exigir_acceso_venta(self):
        if self.sesion.usuario and self.sesion.usuario.get('rol') in ('mesero','cocinero'):
            raise PermissionError('Este rol no tiene permiso para cobrar ni administrar inventario.')
        if not self.sesion.usuario:
            raise PermissionError("Inicia sesión para continuar.")
        if self.sesion.es_venta_libre():
            if not self.sesion.inventario_libre_verificado:
                raise PermissionError("Verifica el inventario antes de vender.")
            return
        if not self.sesion.es_admin() and not self.permite_operar():
            raise PermissionError(
                "No tienes un turno activo. Abre Inventario y confirma tu asignación."
            )

    def turno_id_para_venta(self):
        if self.sesion.es_admin():
            return None
        if self.sesion.es_venta_libre():
            self.exigir_acceso_venta()
            return None
        if not self.sesion.usuario:
            raise PermissionError("Inicia sesión para continuar.")
        turno = self.turno_del_usuario(self.sesion.usuario["id"])
        if not turno or turno["estado"] != "activo":
            raise PermissionError(
                "No tienes un turno activo. Abre Inventario y confirma tu asignación."
            )
        return turno["id"]

    def verificar_inventario_venta_libre(self, cantidades):
        """Acepta el conteo del almacén antes de habilitar el perfil de venta libre."""
        if not self.sesion.es_venta_libre():
            raise PermissionError("Esta verificación solo corresponde a Venta libre.")
        if not isinstance(cantidades, dict) or any(
            not isinstance(n, int) or n < 0 for n in cantidades.values()
        ):
            raise ValueError("Indica cantidades enteras válidas.")
        with self.sesion.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            actuales = {
                p: (nombre, categoria, stock)
                for p, nombre, categoria, stock in db.execute("""
                    SELECT e.producto_id, e.producto_nombre, e.producto_categoria, e.cantidad
                    FROM existencias_inventario e JOIN productos_inventario_bar p ON p.id=e.producto_id
                    WHERE p.activo=1
                """)
            }
            if set(cantidades) != set(actuales):
                raise ValueError("Cuenta todos los productos del inventario mostrado.")
            if any(type(cantidad) is not int or cantidad < 0 for cantidad in cantidades.values()):
                raise ValueError("Completa el conteo físico de todos los productos.")
            for producto_id, contado in cantidades.items():
                nombre, categoria, sistema = actuales[producto_id]
                if contado != sistema:
                    diferencia = contado - sistema
                    db.execute("UPDATE existencias_inventario SET cantidad=? WHERE producto_id=?",
                               (contado, producto_id))
                    if diferencia:
                        db.execute("""
                            INSERT INTO movimientos_inventario
                                (producto_id,producto_nombre,producto_categoria,tipo,cantidad,usuario_id,detalle)
                            VALUES (?,?,?,?,?,?,?)
                        """, (producto_id, nombre, categoria,
                              'verificacion_venta_libre' if diferencia > 0 else 'faltante_venta_libre',
                              abs(diferencia), self.sesion.usuario['id'],
                              'Ajuste según conteo de apertura de Venta libre'))
            from hojas_venta_libre import abrir
            abrir(db,self.sesion.usuario,cantidades,actuales)
        self.sesion.inventario_libre_verificado = True

    @staticmethod
    def _contar_productos_vendidos(ventas):
        vendidos = {}
        for (contenido,) in ventas:
            try:
                productos = json.loads(contenido)
            except (json.JSONDecodeError, TypeError) as error:
                raise ValueError("Una venta del turno contiene productos dañados.") from error
            if not isinstance(productos, list):
                raise ValueError("Una venta del turno tiene un formato de productos inválido.")
            for producto in productos:
                if not isinstance(producto, dict):
                    raise ValueError("Una venta del turno tiene un producto inválido.")
                nombre = producto.get("nombre")
                if nombre and producto.get("seccion", "Bebidas") == "Bebidas":
                    clave = (nombre, producto.get("categoria", "General"))
                    vendidos[clave] = vendidos.get(clave, 0) + 1
        return vendidos

    def _crear_turno_pendiente(
        self, db, usuario_id, cantidades, fecha_asignacion,
        horario_id=None, fecha_programada=None, responsable_id=None,
    ):
        usuario = db.execute(
            "SELECT nombre FROM usuarios WHERE id = ? AND rol = 'mesas' AND tipo = 'normal' AND eliminado=0",
            (usuario_id,),
        ).fetchone()
        if usuario is None:
            raise ValueError("Selecciona un usuario de caja válido.")
        db.execute("""
            INSERT OR IGNORE INTO existencias_inventario
                (producto_id, producto_nombre, producto_categoria, cantidad)
            SELECT id, nombre, categoria, 0 FROM productos_inventario_bar WHERE activo = 1
        """)
        productos = db.execute(
            "SELECT id, nombre, categoria FROM productos_inventario_bar WHERE activo = 1"
        ).fetchall()
        asignados = {
            producto_id: (nombre, categoria)
            for producto_id, nombre, categoria in productos
        }
        if set(cantidades) != set(asignados):
            raise ValueError("El catálogo cambió; actualiza el inventario antes de asignar.")
        if not any(cantidad > 0 for cantidad in cantidades.values()):
            raise ValueError("Asigna al menos una unidad de un producto.")
        stock = {
            producto_id: disponible
            for producto_id, disponible in db.execute(
                "SELECT producto_id, cantidad FROM existencias_inventario"
            )
        }
        for producto_id, cantidad in cantidades.items():
            if cantidad > stock.get(producto_id, 0):
                nombre = asignados[producto_id][0]
                raise ValueError(
                    f"Solo hay {stock.get(producto_id, 0)} unidades disponibles de {nombre}."
                )
        turno_id = db.execute("""
            INSERT INTO turnos(
                usuario_id, nombre_cajero, estado, asignacion_fecha,
                horario_id, fecha_programada
            )
            VALUES (?, ?, 'pendiente', ?, ?, ?)
        """, (
            usuario_id, usuario[0], fecha_asignacion,
            horario_id, fecha_programada,
        )).lastrowid
        db.executemany("""
            INSERT INTO turno_inventario
                (turno_id, producto_id, producto_nombre, producto_categoria, cantidad_asignada)
            VALUES (?, ?, ?, ?, ?)
        """, [
            (turno_id, producto_id, nombre, categoria, cantidades[producto_id])
            for producto_id, (nombre, categoria) in asignados.items()
        ])
        for producto_id, cantidad in cantidades.items():
            if not cantidad:
                continue
            nombre, categoria = asignados[producto_id]
            db.execute("""
                UPDATE existencias_inventario SET cantidad = cantidad - ?
                WHERE producto_id = ?
            """, (cantidad, producto_id))
            db.execute("""
                INSERT INTO movimientos_inventario
                    (producto_id, producto_nombre, producto_categoria, tipo, cantidad,
                     usuario_id, turno_id, detalle)
                VALUES (?, ?, ?, 'entrega_cajero', ?, ?, ?, ?)
            """, (
                producto_id, nombre, categoria, cantidad, responsable_id, turno_id,
                "Inventario asignado desde el horario semanal"
                if horario_id is not None else "Inventario entregado para el turno",
            ))
        return turno_id

    @staticmethod
    def _proxima_ocurrencia(dia_semana, hora, ahora):
        hora_programada = datetime.strptime(hora, "%H:%M").time()
        dias_hasta = (dia_semana - ahora.weekday()) % 7
        fecha = ahora.replace(
            hour=hora_programada.hour,
            minute=hora_programada.minute,
            second=0,
            microsecond=0,
        ) + timedelta(days=dias_hasta)
        if fecha <= ahora:
            fecha += timedelta(days=7)
        return fecha

    def _asignar_proximo_horario(self, db, ahora):
        horarios = db.execute("""
            SELECT id, dia_semana, hora, usuario_id
            FROM horario_cajeros
        """).fetchall()
        if not horarios:
            return None
        siguientes = [
            (
                self._proxima_ocurrencia(dia, hora, ahora),
                horario_id,
                usuario_id,
            )
            for horario_id, dia, hora, usuario_id in horarios
        ]
        programado, horario_id, usuario_id = min(siguientes)
        usuario = db.execute(
            "SELECT nombre FROM usuarios WHERE id = ?",
            (usuario_id,),
        ).fetchone()
        db.execute("""
            INSERT OR IGNORE INTO existencias_inventario
                (producto_id, producto_nombre, producto_categoria, cantidad)
            SELECT id, nombre, categoria, 0 FROM productos_inventario_bar WHERE activo = 1
        """)
        cantidades = {
            producto_id: cantidad
            for producto_id, cantidad in db.execute("""
                SELECT p.id, e.cantidad
                FROM productos_inventario_bar p
                JOIN existencias_inventario e ON e.producto_id = p.id
                WHERE p.activo = 1
            """)
        }
        if not any(cantidades.values()):
            return {
                "usuario": usuario[0],
                "programado": programado.strftime("%Y-%m-%d %H:%M"),
                "asignado": False,
            }
        turno_id = self._crear_turno_pendiente(
            db,
            usuario_id,
            cantidades,
            ahora.strftime("%Y-%m-%d %H:%M:%S"),
            horario_id=horario_id,
            fecha_programada=programado.strftime("%Y-%m-%d %H:%M:%S"),
        )
        return {
            "turno_id": turno_id,
            "usuario": usuario[0],
            "programado": programado.strftime("%Y-%m-%d %H:%M"),
            "asignado": True,
        }

    def asignar(self, usuario_id, cantidades):
        self.sesion.exigir_admin()
        if not cantidades or any(
            not isinstance(cantidad, int) or cantidad < 0
            for cantidad in cantidades.values()
        ):
            raise ValueError("Indica cantidades iniciales válidas.")
        with self.sesion.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM turnos WHERE estado IN ('pendiente', 'activo')"
            ).fetchone():
                raise ValueError("Ya existe un turno sin cerrar.")
            self._crear_turno_pendiente(
                db,
                usuario_id,
                cantidades,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                responsable_id=self.sesion.usuario["id"],
            )

    def asignar_siguiente_tras_cierre(
        self, turno_cerrado_id, usuario_id, cantidades
    ):
        responsable_id = self.sesion.responsable_asignacion_tras_cierre(
            turno_cerrado_id
        )
        if not cantidades or any(
            not isinstance(cantidad, int) or cantidad < 0
            for cantidad in cantidades.values()
        ):
            raise ValueError("Indica cantidades iniciales válidas.")
        with self.sesion.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            turno = db.execute(
                "SELECT usuario_id, estado FROM turnos WHERE id = ?",
                (turno_cerrado_id,),
            ).fetchone()
            if (
                turno is None
                or turno[1] != "cerrado"
                or (
                    not self.sesion.es_admin()
                    and turno[0] != self.sesion.usuario["id"]
                )
            ):
                raise PermissionError(
                    "La asignación manual solo está disponible después del cierre autorizado."
                )
            if db.execute(
                "SELECT 1 FROM turnos WHERE estado IN ('pendiente', 'activo')"
            ).fetchone():
                raise ValueError("Ya existe un turno sin cerrar.")
            self._crear_turno_pendiente(
                db,
                usuario_id,
                cantidades,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                responsable_id=responsable_id,
            )
        self.sesion.revocar_asignacion_tras_cierre(turno_cerrado_id)

    def confirmar_apertura(self, turno_id, cantidades):
        if not self.sesion.usuario or self.sesion.es_admin():
            raise PermissionError("El usuario asignado debe confirmar la apertura.")
        with self.sesion.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            turno = db.execute(
                "SELECT usuario_id, estado FROM turnos WHERE id = ?", (turno_id,)
            ).fetchone()
            if turno != (self.sesion.usuario["id"], "pendiente"):
                raise PermissionError("Este inventario no está pendiente para tu usuario.")
            asignados = db.execute("""
                SELECT producto_id, producto_nombre, producto_categoria, cantidad_asignada
                FROM turno_inventario WHERE turno_id = ? AND producto_id IN (SELECT id FROM productos_inventario_bar)
            """,
                (turno_id,),
            ).fetchall()
            ids = {fila[0] for fila in asignados}
            if set(cantidades) != ids or any(
                not isinstance(cantidad, int) or cantidad < 0
                for cantidad in cantidades.values()
            ):
                raise ValueError("Completa un conteo válido para todos los productos.")
            if not any(cantidades.values()):
                raise ValueError("No se puede iniciar un turno con todo el inventario en cero.")
            for producto_id, nombre, categoria, asignada in asignados:
                cantidad = cantidades[producto_id]
                diferencia = cantidad - asignada
                if diferencia > 0:
                    actualizado = db.execute("""
                        UPDATE existencias_inventario SET cantidad = cantidad - ?
                        WHERE producto_id = ? AND cantidad >= ?
                    """, (diferencia, producto_id, diferencia))
                    if actualizado.rowcount != 1:
                        raise ValueError(
                            f"El conteo de {nombre} supera la asignación y las existencias disponibles."
                        )
                if diferencia:
                    tipo = "sobrante_apertura" if diferencia > 0 else "faltante_apertura"
                    db.execute("""
                        INSERT INTO movimientos_inventario
                            (producto_id, producto_nombre, producto_categoria, tipo, cantidad,
                             usuario_id, turno_id, detalle)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'Diferencia registrada al verificar la apertura')
                    """, (
                        producto_id, nombre, categoria, tipo, abs(diferencia),
                        self.sesion.usuario["id"], turno_id,
                    ))
            db.executemany("""
                UPDATE turno_inventario SET cantidad_apertura = ?
                WHERE turno_id = ? AND producto_id = ?
            """, [(cantidad, turno_id, producto_id) for producto_id, cantidad in cantidades.items()])
            db.execute("""
                UPDATE turnos SET estado = 'activo', apertura_fecha = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (turno_id,))

    def cancelar_asignacion(self, turno_id):
        self.sesion.exigir_admin()
        with self.sesion.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            turno = db.execute(
                "SELECT estado FROM turnos WHERE id = ?", (turno_id,)
            ).fetchone()
            if turno != ("pendiente",):
                raise ValueError("Solo se puede cancelar una asignación pendiente.")
            asignados = db.execute("""
                SELECT producto_id, producto_nombre, producto_categoria, cantidad_asignada
                FROM turno_inventario WHERE turno_id = ?
            """, (turno_id,)).fetchall()
            for producto_id, nombre, categoria, cantidad in asignados:
                if not cantidad:
                    continue
                db.execute("""
                    UPDATE existencias_inventario SET cantidad = cantidad + ?
                    WHERE producto_id = ?
                """, (cantidad, producto_id))
                db.execute("""
                    INSERT INTO movimientos_inventario
                        (producto_id, producto_nombre, producto_categoria, tipo, cantidad,
                         usuario_id, turno_id, detalle)
                    VALUES (?, ?, ?, 'cancelacion_entrega', ?, ?, ?, 'Inventario devuelto al cancelar asignación')
                """, (
                    producto_id, nombre, categoria, cantidad,
                    self.sesion.usuario["id"], turno_id,
                ))
            db.execute("DELETE FROM turno_inventario WHERE turno_id = ?", (turno_id,))
            db.execute("DELETE FROM turnos WHERE id = ?", (turno_id,))

    def resumen(self, turno_id):
        with self.sesion.conexion() as db:
            turno = db.execute(
                "SELECT estado FROM turnos WHERE id = ?", (turno_id,)
            ).fetchone()
            if turno is None:
                raise ValueError("El turno ya no existe.")
            productos = db.execute("""
                SELECT producto_id, producto_nombre, producto_categoria, cantidad_asignada,
                       cantidad_apertura, cantidad_agregada, cantidad_vendida,
                       cantidad_cierre
                FROM turno_inventario WHERE turno_id = ? AND (? = 'cerrado' OR producto_id IN (SELECT id FROM productos_inventario_bar)) ORDER BY producto_nombre COLLATE NOCASE
            """, (turno_id, turno[0])).fetchall()
            ventas = db.execute(
                "SELECT productos FROM ventas WHERE turno_id = ?", (turno_id,)
            ).fetchall()
        vendidos = self._contar_productos_vendidos(ventas)
        resumen = []
        for (producto_id, nombre, categoria, asignada, apertura, agregada,
             ventas_registradas, cierre) in productos:
            cantidad_vendida = max(
                vendidos.get((nombre, categoria), 0),
                ventas_registradas,
            )
            base = apertura if apertura is not None else asignada
            esperada = base + agregada - cantidad_vendida
            resumen.append({
                "producto_id": producto_id,
                "nombre": nombre,
                "categoria": categoria,
                "asignada": asignada,
                "apertura": apertura,
                "agregada": agregada,
                "vendida": cantidad_vendida,
                "esperada": esperada,
                "final": cierre,
                "faltante": None if cierre is None else max(0, esperada - cierre),
                "sobrante": None if cierre is None else max(0, cierre - esperada),
            })
        return resumen

    def cerrar(self, turno_id, cantidades):
        proximo_turno = None
        with self.sesion.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            turno = db.execute(
                "SELECT usuario_id, estado FROM turnos WHERE id = ?", (turno_id,)
            ).fetchone()
            if turno is None or turno[1] != "activo":
                raise ValueError("No hay un turno activo para cerrar.")
            if (not self.sesion.es_admin()
                    and (not self.sesion.usuario
                         or turno[0] != self.sesion.usuario["id"])):
                raise PermissionError("Solo el usuario asignado o Admin puede cerrar el turno.")
            registros = db.execute("""
                SELECT producto_id, producto_nombre, producto_categoria, cantidad_asignada,
                       cantidad_apertura, cantidad_agregada, cantidad_vendida
                FROM turno_inventario WHERE turno_id = ? AND producto_id IN (SELECT id FROM productos_inventario_bar)
            """, (turno_id,)).fetchall()
            ventas = db.execute(
                "SELECT productos FROM ventas WHERE turno_id = ?", (turno_id,)
            ).fetchall()
            vendidos = self._contar_productos_vendidos(ventas)
            ids = {fila[0] for fila in registros}
            if set(cantidades) != ids or any(
                not isinstance(cantidad, int) or cantidad < 0
                for cantidad in cantidades.values()
            ):
                raise ValueError("Completa un conteo final válido para todos los productos.")
            for (producto_id, nombre, categoria, asignada, apertura, agregada,
                 vendida_registrada) in registros:
                vendida = max(
                    vendidos.get((nombre, categoria), 0),
                    vendida_registrada,
                )
                cantidad_final = cantidades[producto_id]
                cantidad_esperada = (
                    (apertura if apertura is not None else asignada) + agregada - vendida
                )
                diferencia = cantidad_final - cantidad_esperada
                if diferencia > 0:
                    tipo_diferencia = "sobran"
                    raise ValueError(
                        f"No se puede cerrar el turno: {nombre}. "
                        f"Se esperan {cantidad_esperada} unidades y contaste {cantidad_final}; "
                        f"{tipo_diferencia} {abs(diferencia)}. Revisa el conteo, las entradas y las ventas antes de cerrar."
                    )
                db.execute("""
                    UPDATE turno_inventario SET cantidad_vendida = ?
                    WHERE turno_id = ? AND producto_id = ?
                """, (vendida, turno_id, producto_id))
                db.execute("""
                    UPDATE existencias_inventario SET cantidad = cantidad + ?
                    WHERE producto_id = ?
                """, (cantidad_final, producto_id))
                if cantidad_final:
                    db.execute("""
                        INSERT INTO movimientos_inventario
                            (producto_id, producto_nombre, producto_categoria, tipo, cantidad,
                             usuario_id, turno_id, detalle)
                        VALUES (?, ?, ?, 'devolucion_cierre', ?, ?, ?, 'Inventario conservado para el siguiente turno')
                    """, (
                        producto_id, nombre, categoria, cantidad_final,
                        self.sesion.usuario["id"], turno_id,
                    ))
                if diferencia:
                    tipo = "sobrante_cierre" if diferencia > 0 else "faltante_cierre"
                    db.execute("""
                        INSERT INTO movimientos_inventario
                            (producto_id, producto_nombre, producto_categoria, tipo, cantidad,
                             usuario_id, turno_id, detalle)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'Diferencia registrada durante el cierre')
                    """, (
                        producto_id, nombre, categoria, tipo, abs(diferencia),
                        self.sesion.usuario["id"], turno_id,
                    ))
            db.executemany("""
                UPDATE turno_inventario SET cantidad_cierre = ?
                WHERE turno_id = ? AND producto_id = ?
            """, [(cantidad, turno_id, producto_id) for producto_id, cantidad in cantidades.items()])
            ahora = datetime.now()
            db.execute("""
                UPDATE turnos SET estado = 'cerrado', cierre_fecha = ?
                WHERE id = ? AND estado = 'activo'
            """, (
                ahora.strftime("%Y-%m-%d %H:%M:%S"),
                turno_id,
            ))
            proximo_turno = self._asignar_proximo_horario(db, ahora)
        return proximo_turno


class PaginaInventario(QWidget):
    def __init__(self, sesion, gestion, parent=None, mostrar_cierre=False):
        super().__init__(parent)
        self.mostrar_cierre = mostrar_cierre
        self.sesion = sesion
        self.gestion = gestion
        self.al_cierre_turno = None
        self.setObjectName("PaginaInventario")
        self.setStyleSheet("""
            QWidget#PaginaInventario { background: #0b1425; color: #eaf3ff; }
            QLabel { color: #DCE4F0; background: transparent; font-size: 17px; }
            QLabel#TituloInventario { color: #79eaff; font-size: 29px; font-weight: 600; }
            QLabel#SubtituloInventario { color: #A8B8CE; font-size: 16px; }
            QLabel#EstadoInventario {
                background: #1c302c; border: 1px solid #20354f; border-radius: 12px;
                color: #79eaff; padding: 14px 18px; font-size: 17px;
            }
            QWidget#TarjetaInventario {
                background: #111f35; border: 1px solid #26677d; border-radius: 16px;
            }
            QWidget#PaginaInventario QComboBox, QWidget#PaginaInventario QLineEdit {
                background: #101e34; color: #eaf3ff; border: 1px solid #287b99;
                border-radius: 10px; padding: 10px 14px; font-size: 19px; min-height: 36px;
            }
            QWidget#PaginaInventario QComboBox QAbstractItemView {
                background: #111f35; color: #eaf3ff; border: 1px solid #287b99;
                selection-background-color: #20d9f5; selection-color: #111827;
                outline: 0;
            }
            QWidget#PaginaInventario QComboBox QAbstractItemView::item {
                min-height: 48px; padding: 8px 12px;
            }
            QWidget#PaginaInventario QLineEdit#CantidadInventario {
                background: #101e34; color: #FFFFFF; border: 2px solid #287b99;
                border-radius: 10px; padding: 8px; font-size: 23px; font-weight: 600;
                min-width: 132px; min-height: 52px;
            }
            QWidget#PaginaInventario QLineEdit#CantidadInventario:focus { border-color: #f34bcb; }
            QWidget#PaginaInventario QPushButton {
                background: #112e45; color: #eaf3ff; border: 1px solid #287b99;
                border-radius: 12px; font-size: 18px; font-weight: 600;
                padding: 12px 18px; min-height: 52px;
            }
            QWidget#PaginaInventario QPushButton:hover { border-color: #f34bcb; color: #79eaff; }
            QWidget#PaginaInventario QPushButton:pressed { background: #1a4260; }
            QWidget#PaginaInventario QPushButton#AccionPrincipal {
                background: #20d9f5; color: #111827; border-color: #20d9f5;
            }
            QWidget#PaginaInventario QPushButton#AccionPeligro {
                background: #71343C; color: white; border-color: #A65660;
            }
            QWidget#PaginaInventario QPushButton:disabled {
                background: #263248; color: #8492A8; border-color: #26677d;
            }
            QScrollArea { border: none; background: transparent; }
            QFrame#SeparadorInventario { background: #26677d; max-height: 1px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        titulo = QLabel("Inventario y turnos")
        titulo.setObjectName("TituloInventario")
        layout.addWidget(titulo)
        subtitulo = QLabel("Asigna productos al cajero y controla cada turno.")
        subtitulo.setObjectName("SubtituloInventario")
        layout.addWidget(subtitulo)
        from interfaz_adaptable import es_android
        if es_android():
            titulo.hide();subtitulo.hide()
        self.estado = QLabel()
        self.estado.setObjectName("EstadoInventario")
        self.estado.setWordWrap(True)
        layout.addWidget(self.estado)

        self.contenido = QWidget()
        self.contenido.setStyleSheet("background: transparent;")
        self.contenido_layout = QVBoxLayout(self.contenido)
        self.contenido_layout.setContentsMargins(0, 0, 0, 0)
        self.contenido_layout.setSpacing(16)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.contenido)
        QScroller.grabGesture(
            self.scroll.viewport(), QScroller.ScrollerGestureType.TouchGesture
        )
        layout.addWidget(self.scroll, 1)

        self.mensaje = QLabel()
        self.mensaje.setWordWrap(True)
        self.mensaje.setMinimumHeight(28)
        layout.addWidget(self.mensaje)
        self.al_cambio_turno = None
        self._diferencias_apertura_confirmadas = None
        self._autorizacion_cierre = False
        self._resumen_cierre = None
        self._turno_cierre = None
        self.modo_admin = "general"
        self.actualizar()

    @staticmethod
    def _tarjeta(titulo, descripcion=""):
        tarjeta = QWidget()
        tarjeta.setObjectName("TarjetaInventario")
        layout = QVBoxLayout(tarjeta)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)
        encabezado = QLabel(titulo)
        encabezado.setStyleSheet("color: #79eaff; font-size: 22px; font-weight: 600;")
        layout.addWidget(encabezado)
        if descripcion:
            ayuda = QLabel(descripcion)
            ayuda.setObjectName("SubtituloInventario")
            ayuda.setProperty("ayudaCompacta",True)
            ayuda.setWordWrap(True)
            layout.addWidget(ayuda)
        return tarjeta, layout

    @staticmethod
    def _boton(texto, accion, object_name=None):
        boton = QPushButton(texto)
        boton.setMinimumSize(260, 68)
        boton.setCursor(Qt.CursorShape.PointingHandCursor)
        if object_name:
            boton.setObjectName(object_name)
        if object_name == "AccionPrincipal":
            boton.setStyleSheet("""
                QPushButton { background: #20d9f5; color: #111827; border: 2px solid #20d9f5;
                    border-radius: 12px; padding: 14px 20px; font-size: 19px; font-weight: bold; }
                QPushButton:hover { background: #79eaff; border-color: #79eaff; }
                QPushButton:pressed { background: #f34bcb; }
                QPushButton:disabled { background: #20354f; color: #A8B4C8; border-color: #20354f; }
            """)
        elif object_name == "AccionPeligro":
            boton.setStyleSheet("""
                QPushButton { background: #71343C; color: white; border: 2px solid #A65660;
                    border-radius: 12px; padding: 14px 20px; font-size: 19px; font-weight: bold; }
                QPushButton:hover { background: #8A414A; }
            """)
        boton.clicked.connect(accion)
        return boton

    def _mostrar_mensaje(self, texto, error=False):
        self.mensaje.setText(texto)
        self.mensaje.setStyleSheet(
            "color: #FFAEAE; font-size: 16px;" if error
            else "color: #54e3b7; font-size: 16px;"
        )

    def _limpiar_contenido(self):
        while self.contenido_layout.count():
            elemento = self.contenido_layout.takeAt(0)
            widget = elemento.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _campo_cantidad(self, valor=0):
        campo = QLineEdit(str(valor))
        campo.setObjectName("CantidadInventario")
        campo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        campo.setMaxLength(6)
        campo.setPlaceholderText("0")
        campo.setInputMethodHints(
            Qt.InputMethodHint.ImhDigitsOnly | Qt.InputMethodHint.ImhNoPredictiveText
        )
        campo.setValidator(QIntValidator(0, 999999, campo))
        campo.setMinimumSize(132, 66)
        return campo

    @staticmethod
    def _cantidad_de(campo):
        texto = campo.text().strip()
        if not texto:
            raise ValueError("Completa la cantidad de todos los productos.")
        return int(texto)

    def _agregar_fila_producto(self, layout, nombre, cantidad, columna=None):
        fila = QFrame()
        fila.setObjectName("FilaInventario")
        fila.setStyleSheet(
            "QFrame#FilaInventario { background: #0b1425; border: 1px solid #26344B; "
            "border-radius: 10px; }"
        )
        from interfaz_adaptable import es_android
        estrecho=es_android() and self.window().width()<760
        fila_layout = QVBoxLayout(fila) if estrecho else QHBoxLayout(fila)
        fila_layout.setContentsMargins(14, 8, 14, 8)
        etiqueta = QLabel(nombre)
        etiqueta.setWordWrap(True)
        fila_layout.addWidget(etiqueta, 1)
        if columna:
            indicador = QLabel(columna)
            indicador.setWordWrap(True)
            indicador.setStyleSheet("color: #A8B8CE; font-size: 15px;")
            fila_layout.addWidget(indicador)
        fila_layout.addWidget(cantidad)
        layout.addWidget(fila)

    def actualizar(self):
        admin = self.sesion.es_admin()
        self._limpiar_contenido()
        self._diferencias_apertura_confirmadas = None
        self._autorizacion_cierre = False
        turno_cerrado_id = (
            self._turno_cierre["id"]
            if self._resumen_cierre and self._turno_cierre
            else None
        )
        asignacion_tras_cierre = bool(
            turno_cerrado_id is not None
            and self.sesion.puede_asignar_tras_cierre(turno_cerrado_id)
        )
        try:
            productos = self.gestion.productos_disponibles()
            turno = self.gestion.turno_abierto()
            existencias = (
                self.gestion.existencias()
                if admin or asignacion_tras_cierre else []
            )
        except sqlite3.Error as error:
            self.estado.setText(f"No se pudo cargar el inventario: {error}")
            self._mostrar_mensaje(str(error), error=True)
            return
        propio = turno and self.sesion.usuario and turno["usuario_id"] == self.sesion.usuario["id"]
        if turno is None:
            self.estado.setText("Sin turno activo")
        elif admin or propio:
            detalle = "Pendiente de apertura" if turno["estado"] == "pendiente" else "Turno activo"
            if turno["fecha_programada"]:
                detalle += f' · Programado: {_fecha_hora_visible(turno["fecha_programada"])}'
            self.estado.setText(f"{detalle}  ·  Cajero: {turno['usuario']}")
        else:
            self.estado.setText(f"Turno asignado a {turno['usuario']}")
        self._mostrar_mensaje("")

        if admin:
            if self.modo_admin == "asignar":
                if turno is None:
                    self._construir_asignacion(
                        productos,
                        existencias,
                        turno_cerrado_id if asignacion_tras_cierre else None,
                    )
                elif turno["estado"] == "pendiente":
                    self._construir_cancelacion(turno)
            elif self.modo_admin == "entrada":
                self._construir_entradas(productos, existencias, False)
            elif self.modo_admin == "existencias":
                self._construir_existencias(productos, existencias)
            else:
                if turno is None and self._resumen_cierre and asignacion_tras_cierre:
                    self._construir_asignacion(
                        productos, existencias, turno_cerrado_id
                    )
                self._construir_entradas(productos, existencias)
                if turno is None and not self._resumen_cierre:
                    self._construir_asignacion(productos, existencias)
                elif turno and turno["estado"] == "pendiente":
                    self._construir_cancelacion(turno)
        elif turno is None and asignacion_tras_cierre:
            self._construir_asignacion(
                productos, existencias, turno_cerrado_id
            )

        if propio and turno["estado"] == "pendiente":
            self._construir_apertura(turno)
        elif (
            turno and turno["estado"] == "activo"
            and (propio or (admin and self.modo_admin == "general"))
        ):
            if getattr(self, 'mostrar_cierre', False):
                self._construir_cierre(turno)
            else:
                self._construir_disponible_turno(turno)
        elif turno is None and self._resumen_cierre and (
            not admin or self.modo_admin in {"general", "asignar"}
        ):
            self._construir_resumen_cierre(self._resumen_cierre)
        elif turno is None and not admin:
            tarjeta, card_layout = self._tarjeta(
                "Aún no tienes inventario asignado",
                "Pide al administrador que te asigne un turno. Al iniciar, verifica el conteo físico.",
            )
            self.contenido_layout.addWidget(tarjeta)
        from interfaz_adaptable import es_android
        tarjetas=[self.contenido_layout.itemAt(i).widget() for i in range(self.contenido_layout.count()) if self.contenido_layout.itemAt(i).widget()]
        if es_android() and len(tarjetas)>1:
            from PySide6.QtWidgets import QTabWidget
            pestanas=QTabWidget()
            pestanas.setDocumentMode(True)
            for tarjeta in tarjetas:
                self.contenido_layout.removeWidget(tarjeta)
                texto=tarjeta.findChildren(QLabel)[0].text()
                nombre=('Entradas' if texto.startswith('Registrar inventario') else 'Existencias' if texto=='Inventario disponible' else 'Asignación' if texto.startswith('Asignar') else texto)
                area=QScrollArea();area.setWidgetResizable(True);area.setWidget(tarjeta)
                pestanas.addTab(area,nombre)
            self.contenido_layout.addWidget(pestanas,1)
        else:
            self.contenido_layout.addStretch(1)

    def abrir_seccion_admin(self, modo):
        self.sesion.exigir_admin()
        if modo not in {"asignar", "entrada", "existencias"}:
            raise ValueError("Selecciona una sección de inventario válida.")
        self.modo_admin = modo
        self.actualizar()

    def _construir_entradas(self, productos, existencias, mostrar_existencias=True):
        tarjeta, layout = self._tarjeta(
            "Registrar inventario recibido",
            "Añade las unidades que llegaron al almacén. Cada entrada queda guardada en el historial.",
        )
        self.selector_entrada = QComboBox()
        self.selector_entrada.setMinimumHeight(58)
        existencias_por_id = {
            producto_id: cantidad
            for producto_id, _, _, cantidad in existencias
        }
        for producto_id, nombre, categoria in productos:
            disponible = existencias_por_id.get(producto_id, 0)
            self.selector_entrada.addItem(
                f"{nombre} · {categoria}  (disponibles: {disponible})", producto_id
            )
        layout.addWidget(self.selector_entrada)
        self.cantidad_entrada = self._campo_cantidad()
        self.cantidad_entrada.setPlaceholderText("Cantidad recibida")
        fila_entrada = QHBoxLayout()
        fila_entrada.addWidget(QLabel("Unidades nuevas"))
        fila_entrada.addStretch(1)
        fila_entrada.addWidget(self.cantidad_entrada)
        layout.addLayout(fila_entrada)
        self.btn_registrar_entrada = self._boton(
            "Registrar entrada al inventario", self.registrar_entrada, "AccionPrincipal"
        )
        self.btn_registrar_entrada.setEnabled(bool(productos))
        layout.addWidget(self.btn_registrar_entrada)
        self.contenido_layout.addWidget(tarjeta)

        if mostrar_existencias:
            self._construir_existencias(productos, existencias)

    def _construir_existencias(self, productos, existencias):
        existencias_por_id = {
            producto_id: cantidad
            for producto_id, _, _, cantidad in existencias
        }
        existencias_tarjeta, existencias_layout = self._tarjeta(
            "Inventario disponible",
            "Existencias en almacén listas para asignar al siguiente cajero.",
        )
        for producto_id, nombre, categoria in productos:
            disponible = existencias_por_id.get(producto_id, 0)
            self._agregar_existencia(
                existencias_layout, f"{nombre} · {categoria}", disponible
            )
        if not productos:
            existencias_layout.addWidget(QLabel("Agrega productos en Productos para recibir inventario."))
        self.contenido_layout.addWidget(existencias_tarjeta)

    @staticmethod
    def _agregar_existencia(layout, nombre, cantidad):
        fila = QFrame()
        fila.setObjectName("FilaExistencia")
        fila.setStyleSheet(
            "QFrame#FilaExistencia { background: #0b1425; border: 1px solid #26344B; "
            "border-radius: 10px; }"
        )
        fila_layout = QHBoxLayout(fila)
        fila_layout.setContentsMargins(14, 8, 14, 8)
        etiqueta = QLabel(nombre)
        etiqueta.setWordWrap(True)
        fila_layout.addWidget(etiqueta, 1)
        unidades = QLabel(f"{cantidad} unidades")
        unidades.setStyleSheet("color: #79eaff; font-size: 18px; font-weight: bold;")
        fila_layout.addWidget(unidades)
        layout.addWidget(fila)

    def _construir_asignacion(
        self, productos, existencias, turno_cerrado_id=None
    ):
        tarjeta, layout = self._tarjeta(
            "Asignar siguiente cajero" if turno_cerrado_id else "Asignar inventario al cajero",
            (
                "Elige al próximo cajero; las cantidades disponibles ya están preparadas "
                "para asignarse de forma rápida."
                if turno_cerrado_id else
                "Selecciona un usuario y las cantidades disponibles que entregas para su turno."
            ),
        )
        etiqueta_usuario = QLabel("Usuario de caja")
        self.selector_usuario = QComboBox()
        self.selector_usuario.setMinimumHeight(58)
        try:
            empleados = (
                self.gestion.empleados_para_asignacion_tras_cierre(
                    turno_cerrado_id
                )
                if turno_cerrado_id is not None
                else self.gestion.empleados()
            )
            for usuario_id, nombre in empleados:
                self.selector_usuario.addItem(nombre, usuario_id)
        except (PermissionError, ValueError, sqlite3.Error) as error:
            self._mostrar_mensaje(f"No se pudieron cargar los usuarios: {error}", error=True)
            self.selector_usuario.setEnabled(False)
        layout.addWidget(etiqueta_usuario)
        layout.addWidget(self.selector_usuario)
        disponibles = {
            producto_id: cantidad
            for producto_id, _, _, cantidad in existencias
        }
        if turno_cerrado_id is not None and not any(disponibles.values()):
            aviso = QLabel(
                "No hay existencias para asignar. Admin debe registrar una entrada "
                "de inventario antes de continuar."
            )
            aviso.setWordWrap(True)
            layout.addWidget(aviso)
        self.controles_cantidades = {}
        if not productos:
            layout.addWidget(QLabel("Agrega productos en Productos y registra una entrada antes de asignar el turno."))
        filas_layout=layout
        from interfaz_adaptable import es_android
        from PySide6.QtWidgets import QSizePolicy
        if es_android():
            filas_scroll=QScrollArea();filas_scroll.setWidgetResizable(True)
            filas_scroll.setMinimumHeight(0)
            filas_scroll.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Ignored)
            filas_contenido=QWidget();filas_layout=QVBoxLayout(filas_contenido)
            filas_layout.setContentsMargins(0,0,0,0)
            filas_scroll.setWidget(filas_contenido);layout.addWidget(filas_scroll,1)
        for producto_id, nombre, categoria in productos:
            disponible = disponibles.get(producto_id, 0)
            cantidad = self._campo_cantidad(disponible)
            self.controles_cantidades[producto_id] = cantidad
            cantidad.setPlaceholderText("Cantidad a entregar")
            self._agregar_fila_producto(
                filas_layout, f"{nombre} · {categoria}", cantidad, f"Disponible: {disponible}"
            )
        self.btn_asignar = self._boton(
            "Asignar siguiente cajero" if turno_cerrado_id
            else "Asignar inventario e iniciar entrega",
            lambda checked=False, turno_id=turno_cerrado_id: self.asignar(turno_id),
            "AccionPrincipal",
        )
        self.btn_asignar.setEnabled(bool(
            productos and self.selector_usuario.count() and any(disponibles.values())
        ))
        layout.addWidget(self.btn_asignar)
        self.contenido_layout.addWidget(tarjeta)

    def registrar_entrada(self):
        if not self.sesion.es_admin():
            self._mostrar_mensaje("Solo Admin puede registrar inventario recibido.", error=True)
            return
        producto_id = self.selector_entrada.currentData()
        if producto_id is None:
            self._mostrar_mensaje("Selecciona un producto del catálogo.", error=True)
            return
        try:
            cantidad = self._cantidad_de(self.cantidad_entrada)
            self.gestion.registrar_entrada(producto_id, cantidad)
        except (ValueError, PermissionError, sqlite3.Error) as error:
            self._mostrar_mensaje(str(error), error=True)
            return
        self.actualizar()
        self._mostrar_mensaje(
            "Entrada guardada. Las existencias disponibles se actualizaron."
        )

    def _construir_cancelacion(self, turno):
        tarjeta, layout = self._tarjeta(
            "Asignación pendiente",
            f"El cajero {turno['usuario']} aún no ha confirmado la apertura.",
        )
        self.btn_cancelar_asignacion = self._boton(
            "Cancelar esta asignación", self.preparar_cancelacion, "AccionPeligro"
        )
        layout.addWidget(self.btn_cancelar_asignacion)
        self.btn_mantener_asignacion = self._boton(
            "No, mantener asignación", self.actualizar
        )
        self.btn_mantener_asignacion.hide()
        layout.addWidget(self.btn_mantener_asignacion)
        self.contenido_layout.addWidget(tarjeta)

    def _construir_apertura(self, turno):
        tarjeta, layout = self._tarjeta(
            "Verificar inventario de apertura",
            "Cuenta los productos recibidos y compara el total con la asignación del administrador.",
        )
        self.controles_apertura = {}
        self._diferencias_apertura_confirmadas = None
        for producto_id, nombre, categoria, asignada, _, _, _ in turno["productos"]:
            cantidad = self._campo_cantidad(asignada)
            self.controles_apertura[producto_id] = cantidad
            self._agregar_fila_producto(
                layout, f"{nombre} · {categoria}", cantidad, f"Asignado: {asignada}"
            )
        self.btn_confirmar_apertura = self._boton(
            "Confirmar inventario y comenzar turno", self.confirmar_apertura, "AccionPrincipal"
        )
        self.aviso_apertura = QLabel()
        self.aviso_apertura.setWordWrap(True)
        self.aviso_apertura.setStyleSheet(
            "background: #40272B; color: #FFD5A0; border: 1px solid #A65660; "
            "border-radius: 10px; padding: 14px; font-size: 16px;"
        )
        self.aviso_apertura.hide()
        layout.addWidget(self.aviso_apertura)
        layout.addWidget(self.btn_confirmar_apertura)
        self.contenido_layout.addWidget(tarjeta)

    def _construir_disponible_turno(self, turno):
        tarjeta, layout = self._tarjeta(
            "Inventario disponible del turno",
            "Unidades disponibles para vender: inventario inicial + entradas − ventas. Para cerrar o cambiar turno, usa el botón de Inicio.",
        )
        filas = self.gestion.resumen(turno['id'])
        for producto in filas:
            disponible = QLabel(str(producto['esperada']))
            disponible.setStyleSheet('color: #ff69d5; font-size: 26px; font-weight: bold; padding: 8px;')
            self._agregar_fila_producto(
                layout, producto['nombre'], disponible,
                f"Vendidas: {producto['vendida']} · Agregadas: {producto['agregada']}",
            )
        if not filas:
            layout.addWidget(QLabel("Este turno no tiene productos asignados."))
        layout.addWidget(self._boton("Actualizar existencias", self.actualizar))
        self.contenido_layout.addWidget(tarjeta)

    def _construir_cierre(self, turno):
        tarjeta, layout = self._tarjeta(
            "Cierre de turno",
            "El cajero puede permanecer conectado. Ingresa la contraseña de Admin para autorizar el cierre.",
        )
        self.password_admin = QLineEdit()
        self.password_admin.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_admin.setMaxLength(128)
        self.password_admin.setPlaceholderText("Contraseña de Admin")
        layout.addWidget(self.password_admin)
        self.btn_autorizar_cierre = self._boton(
            "Autorizar cierre", self.autorizar_cierre
        )
        layout.addWidget(self.btn_autorizar_cierre)
        self.panel_conteo_final = QWidget()
        self.panel_conteo_layout = QVBoxLayout(self.panel_conteo_final)
        self.panel_conteo_layout.setContentsMargins(0, 10, 0, 0)
        self.panel_conteo_layout.setSpacing(12)
        self.panel_conteo_final.hide()
        layout.addWidget(self.panel_conteo_final)
        self._turno_cierre = turno
        self.contenido_layout.addWidget(tarjeta)

    def _construir_resumen_cierre(self, resumen):
        tarjeta, layout = self._tarjeta(
            "Turno cerrado",
            "Resumen final de ventas e inventario.",
        )
        for item in resumen:
            texto = (
                f'{item["nombre"]} · {item["categoria"]}\n'
                f'Agregado: {item["agregada"]}  ·  Vendido: {item["vendida"]}  ·  '
                f'Final: {item["final"]}  ·  '
                f'Faltante: {item["faltante"]}  ·  Sobrante: {item["sobrante"]}'
            )
            etiqueta = QLabel(texto)
            etiqueta.setWordWrap(True)
            etiqueta.setStyleSheet(
                "background: #0b1425; border: 1px solid #26344B; border-radius: 10px; "
                "padding: 14px; font-size: 16px;"
            )
            layout.addWidget(etiqueta)
        self.contenido_layout.addWidget(tarjeta)

    def _cantidades_apertura(self):
        return self._cantidades(self.controles_apertura)

    def _cantidades(self, controles):
        return {
            producto_id: self._cantidad_de(control)
            for producto_id, control in controles.items()
        }

    def _limpiar_panel_conteo(self):
        while self.panel_conteo_layout.count():
            elemento = self.panel_conteo_layout.takeAt(0)
            widget = elemento.widget()
            if widget is not None:
                widget.deleteLater()

    def asignar(self, turno_cerrado_id=None):
        if not self.sesion.es_admin() and turno_cerrado_id is None:
            self._mostrar_mensaje("Solo Admin puede asignar inventario.", error=True)
            return
        usuario_id = self.selector_usuario.currentData()
        if usuario_id is None:
            self._mostrar_mensaje("Crea primero un usuario de caja.", error=True)
            return
        try:
            cantidades = self._cantidades(self.controles_cantidades)
        except ValueError as error:
            self._mostrar_mensaje(str(error), error=True)
            return
        try:
            if turno_cerrado_id is not None:
                self.gestion.asignar_siguiente_tras_cierre(
                    turno_cerrado_id, usuario_id, cantidades
                )
            else:
                self.gestion.asignar(usuario_id, cantidades)
        except (ValueError, PermissionError, sqlite3.Error) as error:
            self._mostrar_mensaje(str(error), error=True)
            return
        self._resumen_cierre = None
        self.actualizar()
        if self.al_cambio_turno and not self.sesion.es_admin():
            self.al_cambio_turno()
        self._mostrar_mensaje("Inventario asignado. El cajero debe verificarlo al iniciar.")

    def preparar_cancelacion(self):
        try:
            turno = self.gestion.turno_abierto()
        except sqlite3.Error as error:
            self._mostrar_mensaje(f"No se pudo leer la asignación: {error}", error=True)
            return
        if turno is None or turno["estado"] != "pendiente":
            return
        self._mostrar_mensaje(
            f"Confirma la cancelación del inventario pendiente de {turno['usuario']}."
        )
        self.btn_cancelar_asignacion.setText("Sí, cancelar asignación")
        self.btn_cancelar_asignacion.clicked.disconnect()
        self.btn_cancelar_asignacion.clicked.connect(self.cancelar_asignacion)
        self.btn_mantener_asignacion.show()

    def cancelar_asignacion(self):
        try:
            turno = self.gestion.turno_abierto()
        except sqlite3.Error as error:
            self._mostrar_mensaje(f"No se pudo leer la asignación: {error}", error=True)
            return
        if turno is None or turno["estado"] != "pendiente":
            self.actualizar()
            return
        try:
            self.gestion.cancelar_asignacion(turno["id"])
        except (ValueError, PermissionError, sqlite3.Error) as error:
            self._mostrar_mensaje(str(error), error=True)
            return
        self.actualizar()
        self._mostrar_mensaje("Asignación cancelada.")

    def confirmar_apertura(self):
        try:
            turno = self.gestion.turno_abierto()
        except sqlite3.Error as error:
            self._mostrar_mensaje(f"No se pudo leer el turno: {error}", error=True)
            return
        if turno is None or turno["estado"] != "pendiente":
            return
        try:
            cantidades = self._cantidades_apertura()
        except ValueError as error:
            self._mostrar_mensaje(str(error), error=True)
            return
        diferencias = []
        for producto_id, nombre, categoria, asignada, _, _, _ in turno["productos"]:
            contado = cantidades[producto_id]
            if contado < asignada:
                diferencias.append(
                    (producto_id, f"Faltante de {asignada - contado} · {nombre} ({categoria})")
                )
            elif contado > asignada:
                diferencias.append(
                    (producto_id, f"Sobrante de {contado - asignada} · {nombre} ({categoria})")
                )
        firma_diferencias = tuple(diferencias)
        if diferencias and firma_diferencias != self._diferencias_apertura_confirmadas:
            self._diferencias_apertura_confirmadas = firma_diferencias
            self.aviso_apertura.setText(
                "Hay diferencias en el inventario:\n"
                + "\n".join(detalle for _, detalle in diferencias)
                + "\nAl continuar, cada diferencia quedará registrada en el historial."
            )
            self.aviso_apertura.show()
            self.btn_confirmar_apertura.setText("Registrar diferencias y comenzar turno")
            return
        try:
            self.gestion.confirmar_apertura(turno["id"], cantidades)
        except (ValueError, PermissionError, sqlite3.Error) as error:
            self._mostrar_mensaje(str(error), error=True)
            return
        self.aviso_apertura.hide()
        self._resumen_cierre = None
        if self.al_cambio_turno:
            self.al_cambio_turno()
        else:
            self.actualizar()
        self._mostrar_mensaje("Apertura confirmada. El turno está listo para vender.")

    def autorizar_cierre(self):
        try:
            autorizado = self.sesion.autorizar_asignacion_tras_cierre(
                self.password_admin.text(), self._turno_cierre["id"]
            )
        except sqlite3.Error as error:
            self._mostrar_mensaje(f"No se pudo validar la contraseña: {error}", error=True)
            return
        if not autorizado:
            self.password_admin.clear()
            self._mostrar_mensaje("La contraseña de Admin no es correcta.", error=True)
            self.password_admin.setFocus()
            return
        self._autorizacion_cierre = True
        self.password_admin.clear()
        self.password_admin.setEnabled(False)
        self.btn_autorizar_cierre.setEnabled(False)
        self._mostrar_mensaje("Cierre autorizado. Cuenta el inventario final para continuar.")
        self._mostrar_conteo_final()

    def _mostrar_conteo_final(self):
        self._limpiar_panel_conteo()
        self.controles_finales = {}
        try:
            self.resumen_actual = self.gestion.resumen(self._turno_cierre["id"])
        except (ValueError, sqlite3.Error) as error:
            self._mostrar_mensaje(f"No se pudo preparar el resumen: {error}", error=True)
            return
        titulo = QLabel("Ventas del turno e inventario final")
        titulo.setStyleSheet("color: #79eaff; font-size: 20px; font-weight: 600;")
        self.panel_conteo_layout.addWidget(titulo)
        for producto in self.resumen_actual:
            cantidad = self._campo_cantidad("")
            cantidad.setPlaceholderText("Escribe la cantidad")
            self.controles_finales[producto["producto_id"]] = cantidad
            info = (
                f'{producto["nombre"]} · {producto["categoria"]}  |  '
                f'Agregado: {producto["agregada"]}  |  '
                f'Unidades vendidas: {producto["vendida"]}'
            )
            self._agregar_fila_producto(
                self.panel_conteo_layout, info, cantidad, "Inventario final"
            )
        self.btn_finalizar_cierre = self._boton(
            "Confirmar inventario y cerrar turno", self.finalizar_cierre, "AccionPeligro"
        )
        self.panel_conteo_layout.addWidget(self.btn_finalizar_cierre)
        self.panel_conteo_final.show()

    def finalizar_cierre(self):
        if not self._autorizacion_cierre:
            self._mostrar_mensaje("Se necesita autorización de Admin.", error=True)
            return
        try:
            cantidades = self._cantidades(self.controles_finales)
        except ValueError as error:
            self._mostrar_mensaje(str(error), error=True)
            return
        try:
            proximo_turno = self.gestion.cerrar(
                self._turno_cierre["id"], cantidades
            )
        except (ValueError, PermissionError, sqlite3.Error) as error:
            self._mostrar_mensaje(str(error), error=True)
            return
        for producto in self.resumen_actual:
            producto["final"] = cantidades[producto["producto_id"]]
            diferencia = producto["esperada"] - producto["final"]
            producto["faltante"] = max(0, diferencia)
            producto["sobrante"] = max(0, -diferencia)
        self._resumen_cierre = self.resumen_actual
        if proximo_turno and proximo_turno["asignado"]:
            self.sesion.revocar_asignacion_tras_cierre(
                self._turno_cierre["id"]
            )
        self.actualizar()
        if self.al_cierre_turno:
            self.al_cierre_turno()
        elif self.al_cambio_turno:
            self.al_cambio_turno()
        if proximo_turno and proximo_turno["asignado"]:
            mensaje = (
                f'Turno cerrado. El inventario se asignó a {proximo_turno["usuario"]}; '
                f'su turno queda pendiente para '
                f'{_fecha_hora_visible(proximo_turno["programado"])}.'
            )
        elif proximo_turno:
            mensaje = (
                f'El siguiente horario es para {proximo_turno["usuario"]} '
                f'el {_fecha_hora_visible(proximo_turno["programado"])}, '
                "pero no hay existencias disponibles "
                "para crear la asignación automática. Puedes elegir otro cajero "
                "en esta pantalla cuando haya inventario disponible."
            )
        else:
            mensaje = (
                "Turno cerrado. Selecciona al siguiente cajero en esta pantalla "
                "para asignarle el inventario."
            )
        faltantes = [
            f'{producto["nombre"]}: {producto["faltante"]}'
            for producto in self._resumen_cierre
            if producto["faltante"]
        ]
        if faltantes:
            mensaje += " Faltantes registrados: " + ", ".join(faltantes) + "."
        self._mostrar_mensaje(mensaje, error=bool(faltantes))


class PaginaHojaInventarios(QWidget):
    def __init__(self, gestion, parent=None):
        super().__init__(parent)
        self.gestion = gestion
        self.setObjectName("PaginaHojaInventarios")
        self.setStyleSheet("""
            QWidget#PaginaHojaInventarios { background: #0b1425; color: #eaf3ff; }
            QLabel { color: #DCE4F0; background: transparent; font-size: 17px; }
            QLabel#TituloHojaInventarios {
                color: #79eaff; font-size: 29px; font-weight: 600;
            }
            QLabel#EstadoHojaInventarios { color: #FFAEAE; font-size: 16px; }
            QFrame#TarjetaTurnoHoja {
                background: #111f35; border: 1px solid #173653; border-radius: 16px;
            }
            QFrame#TarjetaTurnoHoja:hover {
                background: #1B293F; border: 1px solid #20d9f5;
            }
            QPushButton#TurnoHoja {
                background: transparent; color: #eaf3ff; border: none;
                text-align: left; padding: 18px; font-size: 17px;
            }
            QPushButton#TurnoHoja:pressed { color: #79eaff; padding-top: 20px; }
            QLabel#EstadoTurnoHoja { color: #79eaff; font-size: 14px; font-weight: bold; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Hoja de inventarios")
        titulo.setObjectName("TituloHojaInventarios")
        layout.addWidget(titulo)
        subtitulo = QLabel("Consulta los turnos y toca una tarjeta para abrir su detalle.")
        self.subtitulo=subtitulo
        subtitulo.setWordWrap(True)
        layout.addWidget(subtitulo)

        self.estado = QLabel()
        self.estado.setObjectName("EstadoHojaInventarios")
        self.estado.setWordWrap(True)
        layout.addWidget(self.estado)

        self.contenedor_tarjetas = QWidget()
        self.contenedor_tarjetas.setStyleSheet("background-color: #0b1425; border: none;")
        self.lista_tarjetas = QVBoxLayout(self.contenedor_tarjetas)
        self.lista_tarjetas.setContentsMargins(2, 4, 8, 4)
        self.lista_tarjetas.setSpacing(12)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { background-color: #0b1425; border: none; }")
        self.scroll.viewport().setStyleSheet("background-color: #0b1425; border: none;")
        self.scroll.setWidget(self.contenedor_tarjetas)
        layout.addWidget(self.scroll, 1)
        self.detalle = None
        from PySide6.QtCore import QDate
        from PySide6.QtWidgets import QDateEdit
        self.rango_fechas=None
        filtro=QHBoxLayout()
        filtro.addWidget(QLabel('Fecha del turno · Desde'))
        self.fecha_desde=QDateEdit(QDate.currentDate());self.fecha_hasta=QDateEdit(QDate.currentDate())
        for campo in (self.fecha_desde,self.fecha_hasta):
            campo.setCalendarPopup(True);campo.setDisplayFormat('dd/MM/yyyy')
        filtro.addWidget(self.fecha_desde);filtro.addWidget(QLabel('Hasta'));filtro.addWidget(self.fecha_hasta)
        filtrar=QPushButton('Filtrar');filtrar.clicked.connect(self.aplicar_fechas);filtro.addWidget(filtrar)
        todas=QPushButton('Todas las fechas');todas.clicked.connect(self.quitar_fechas);filtro.addWidget(todas)
        layout.insertLayout(2,filtro)

    def aplicar_fechas(self):
        desde=self.fecha_desde.date().toPython();hasta=self.fecha_hasta.date().toPython()
        if desde>hasta:
            self.estado.setText('La fecha Desde no puede ser posterior a Hasta.');return
        self.rango_fechas=(desde,hasta);self.actualizar()

    def quitar_fechas(self):
        self.rango_fechas=None;self.actualizar()

    @staticmethod
    def fecha_turno(fila):
        try:return datetime.fromisoformat(fila.get('asignacion_fecha') or '').replace(tzinfo=None)
        except (ValueError,TypeError):return datetime.min

    def _abrir_detalle(self, turno, filas):
        """Abre una tabla modal dibujada dentro de la ventana principal."""
        from resumen_pagos import resumen_pagos_hoja
        try:
            resumen=resumen_pagos_hoja(self.gestion.sesion,turno['turno_id'],filas,incluir_cocina=True)
        except (ValueError,PermissionError,sqlite3.Error) as error:
            self.estado.setText(f'No se pudieron cargar los cobros: {error}')
            return
        self.estado.clear()
        if self.detalle is not None:
            self.detalle.close()
        cierre=None
        if (getattr(self,'al_cerrar_hoja',None) and turno['turno_id']<0 and turno['estado']=='activo'
                and self.gestion.sesion.es_venta_libre()):
            cierre=lambda:self.al_cerrar_hoja(-turno['turno_id'])
        self.detalle = _DetalleHojaInventario(self.window(), turno, filas, resumen,cierre)
        self.detalle.show()

    def _vaciar_tarjetas(self):
        while self.lista_tarjetas.count():
            elemento = self.lista_tarjetas.takeAt(0)
            widget = elemento.widget()
            if widget is not None:
                widget.deleteLater()

    def actualizar(self):
        try:
            filas = self.gestion.hoja_inventarios()
        except (ValueError, PermissionError, sqlite3.Error) as error:
            self.estado.setText(f"No se pudo cargar la hoja de inventarios: {error}")
            self._vaciar_tarjetas()
            return

        self.estado.clear()
        self.subtitulo.setText('Mostrando todas las fechas · Más recientes primero.')
        if self.rango_fechas:
            desde,hasta=self.rango_fechas
            self.subtitulo.setText(f'Turnos asignados del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y} · Más recientes primero.')
            filas=[f for f in filas if desde<=self.fecha_turno(f).date()<=hasta]
        filas=sorted(filas,key=lambda f:(self.fecha_turno(f),abs(f['turno_id'])),reverse=True)
        self._vaciar_tarjetas()
        turnos = {}
        for fila in filas:
            turnos.setdefault(fila["turno_id"], []).append(fila)
        for filas_turno in turnos.values():
            primera = filas_turno[0]
            cierre = primera["cierre_fecha"] or (
                "Pendiente de apertura" if primera["estado"] == "pendiente"
                else "Turno en curso"
            )
            tarjeta = QFrame()
            tarjeta.setObjectName("TarjetaTurnoHoja")
            tarjeta.setFrameShape(QFrame.Shape.StyledPanel)
            fila_tarjeta = QHBoxLayout(tarjeta)
            fila_tarjeta.setContentsMargins(8, 4, 8, 4)
            boton = QPushButton(
                f'Cajero  ·  {primera["cajero"]}\n'
                f'Asignado  ·  {primera["asignacion_fecha"] or "No disponible"}\n'
                f'Cierre  ·  {cierre}     ›'
            )
            boton.setObjectName("TurnoHoja")
            boton.setMinimumHeight(100)
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.clicked.connect(
                lambda checked=False, t=primera.copy(), detalle=filas_turno.copy():
                    self._abrir_detalle(t, detalle)
            )
            fila_tarjeta.addWidget(boton, 1)
            estado = QLabel(primera["estado"].capitalize())
            estado.setObjectName("EstadoTurnoHoja")
            fila_tarjeta.addWidget(estado)
            tarjeta.setCursor(Qt.CursorShape.PointingHandCursor)
            tarjeta.mousePressEvent = lambda evento, b=boton: b.click()
            self.lista_tarjetas.addWidget(tarjeta)
        if not filas:
            vacio = QLabel("No hay hojas en el intervalo seleccionado." if self.rango_fechas else "Todavía no hay turnos asignados.")
            vacio.setStyleSheet("color: #AABAD0; padding: 22px; font-size: 18px;")
            self.lista_tarjetas.addWidget(vacio)
        self.lista_tarjetas.addStretch(1)


class _DetalleHojaInventario(QWidget):
    """Ventana emergente integrada; bloquea solo el contenido de la aplicación."""
    def __init__(self, parent, turno, filas, resumen=None,al_cerrar_hoja=None):
        super().__init__(parent)
        self.ventana = parent
        self.contenido = parent.centralWidget()
        self.contenido_habilitado = self.contenido.isEnabled()
        self.foco_anterior = QApplication.focusWidget()
        self.setObjectName("DetalleHojaInventario")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(parent.rect())
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            QWidget#DetalleHojaInventario { background: rgba(3, 8, 17, 225); }
            QFrame#TarjetaDetalleHoja { background: #111D2F; border: 1px solid #465064; border-radius: 20px; }
            QLabel { color: #DCE4F0; background: transparent; }
            QLabel#TituloDetalleHoja { color: #79eaff; font-size: 25px; font-weight: bold; }
            QTableWidget { background: #0B1525; alternate-background-color: #152136;
                color: #eaf3ff; gridline-color: #173653; border: 1px solid #173653;
                border-radius: 10px; font-size: 15px; }
            QHeaderView::section { background: #112e45; color: #79eaff;
                border: none; padding: 10px; font-weight: bold; }
            QPushButton { background: #20d9f5; color: #0b1425; border: none;
                border-radius: 9px; padding: 14px 24px; font-size: 16px; font-weight: bold; }
            QPushButton:hover { background: #79eaff; }
        """)
        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(12, 12, 12, 12)
        tarjeta = QFrame()
        tarjeta.setObjectName("TarjetaDetalleHoja")
        tarjeta.setMaximumWidth(16777215)
        interior = QVBoxLayout(tarjeta)
        interior.setContentsMargins(24, 20, 24, 22)
        interior.setSpacing(12)
        encabezado = QHBoxLayout()
        titulos = QVBoxLayout()
        titulo = QLabel(f"Turno de {turno['cajero']}")
        titulo.setObjectName("TituloDetalleHoja")
        titulos.addWidget(titulo)
        subtitulo = QLabel(
            f"Asignado: {turno['asignacion_fecha'] or 'No disponible'}    ·    "
            f"Cierre: {turno['cierre_fecha'] or ('Pendiente de apertura' if turno['estado'] == 'pendiente' else 'Turno en curso')}"
        )
        subtitulo.setWordWrap(True)
        titulos.addWidget(subtitulo)
        encabezado.addLayout(titulos, 1)
        estado = QLabel(turno["estado"].capitalize())
        estado.setStyleSheet("color: #79eaff; font-size: 15px; font-weight: bold;")
        encabezado.addWidget(estado)
        interior.addLayout(encabezado)
        tabla = QTableWidget(len(filas), 8)
        tabla.setObjectName("CuadriculaHojaInventario")
        tabla.setHorizontalHeaderLabels([
            "Producto", "Recibido", "Agregado", "Vendido", "Importe B/.",
            "Saldo sistema" if filas and filas[0]["turno_id"] < 0 else "Entregado", "Faltantes", "Sobrantes",
        ])
        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabla.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        tabla.setAlternatingRowColors(True)
        tabla.verticalHeader().hide()
        tabla.setWordWrap(True)
        tabla.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        tabla.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for columna in range(1, 8):
            tabla.horizontalHeader().setSectionResizeMode(columna, QHeaderView.ResizeMode.ResizeToContents)
        for i, fila in enumerate(filas):
            valores = [
                fila["producto"], str(fila["recibida"]), str(fila["agregada"]),
                str(fila["vendida"]), f'B/. {fila["dinero_centimos"] / 100:.2f}',
                str(fila["entregada"]) if fila["cierre_fecha"] or fila["turno_id"] < 0 else "Pendiente",
                str(fila["faltante"]) if fila["faltante"] is not None else ("No contado" if fila["turno_id"] < 0 else "Pendiente"),
                str(fila["sobrante"]) if fila["sobrante"] is not None else ("No contado" if fila["turno_id"] < 0 else "Pendiente"),
            ]
            for j, valor in enumerate(valores):
                celda = QTableWidgetItem(valor)
                if j:
                    celda.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tabla.setItem(i, j, celda)
            tabla.setRowHeight(i, 52)
        tabla.setMinimumHeight(min(170, max(90, len(filas) * 52)))
        tabla.setMaximumHeight(16777215)
        interior.addWidget(tabla, 1)
        if resumen is not None:
            from PySide6.QtGui import QColor
            importes=dict(resumen['importes'])
            cocina_importe=resumen.get('cocina_centimos',0)
            cocina_unidades=resumen.get('cocina_unidades',0)
            if cocina_unidades:
                indice=tabla.rowCount();tabla.insertRow(indice)
                for col,texto in ((0,'VENTAS DE COCINA · Resumen'),(3,str(cocina_unidades)),(4,f'B/. {cocina_importe/100:.2f}')):
                    tabla.setItem(indice,col,QTableWidgetItem(texto))
                tabla.setRowHeight(indice,42)
            inicio_pagos=tabla.rowCount()
            total_tabla=sum(f['dinero_centimos'] for f in filas)+cocina_importe
            diferencia=total_tabla-sum(importes.values())
            if diferencia:
                importes['Sin conciliar' if diferencia>0 else 'Diferencia por revisar']=diferencia
            tabla.setRowCount(inicio_pagos+len(importes)+1)
            for indice,(metodo,importe) in enumerate(importes.items(),inicio_pagos):
                tabla.setSpan(indice,0,1,3)
                for col in range(8):
                    if col in (1,2):continue
                    texto=metodo if col==3 else f'B/. {importe/100:.2f}' if col==4 else ''
                    celda=QTableWidgetItem(texto)
                    celda.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    celda.setBackground(QColor('#112e45'))
                    tabla.setItem(indice,col,celda)
                tabla.setRowHeight(indice,34)
            ultima=tabla.rowCount()-1
            tabla.setSpan(ultima,0,1,3)
            for col,texto in ((0,'TOTAL VENDIDO'),(3,str(sum(f['vendida'] for f in filas)+cocina_unidades)),(4,f'B/. {total_tabla/100:.2f}')):
                celda=QTableWidgetItem(texto)
                fuente=celda.font();fuente.setBold(True);celda.setFont(fuente)
                celda.setForeground(QColor('#79eaff'));celda.setBackground(QColor('#173653'))
                if col:celda.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tabla.setItem(ultima,col,celda)
            tabla.setRowHeight(ultima,42)
            tabla.setMinimumHeight(min(max(90,parent.height()-220),sum(tabla.rowHeight(i) for i in range(tabla.rowCount()))+tabla.horizontalHeader().height()+6))
            if diferencia or resumen['ambiguas']:
                aviso=QLabel('Los importes sin conciliar no tienen un cobro identificable. El total corresponde al inventario y la cocina de esta hoja.')
                aviso.setWordWrap(True);aviso.setStyleSheet('color:#a8bad0; font-size:12px;')
                interior.addWidget(aviso)
        acciones=QHBoxLayout()
        if resumen is not None:
            cocina=QPushButton('Ver cocina detallada')
            cocina.setEnabled(bool(resumen.get('cocina')))
            cocina.clicked.connect(lambda:self.mostrar_cocina(resumen.get('cocina',[])))
            acciones.addWidget(cocina)
        if al_cerrar_hoja is not None:
            cerrar_hoja=QPushButton('Cerrar hoja de inventario')
            cerrar_hoja.clicked.connect(al_cerrar_hoja)
            acciones.addWidget(cerrar_hoja)
        acciones.addStretch(1)
        cerrar = QPushButton("Cerrar detalle")
        cerrar.setMinimumHeight(52)
        cerrar.clicked.connect(self.close)
        acciones.addWidget(cerrar)
        interior.addLayout(acciones)
        exterior.addWidget(tarjeta,1)
        self.tabla_hoja=tabla
        self.alturas_hoja=[tabla.rowHeight(i) for i in range(tabla.rowCount())]
        self.ventana.installEventFilter(self)

    def ajustar_filas(self):
        tabla=getattr(self,'tabla_hoja',None)
        if tabla is None:return
        disponible=max(1,tabla.viewport().height()-2)
        escala=min(1,disponible/max(1,sum(self.alturas_hoja)))
        for i,alto in enumerate(self.alturas_hoja):tabla.setRowHeight(i,max(32,int(alto*escala)))

    def mostrar_cocina(self,platos):
        from dialogos import DialogoIntegrado
        dialogo=DialogoIntegrado(self.ventana);dialogo.setWindowTitle('Ventas de cocina detalladas')
        dialogo.setStyleSheet(self.styleSheet()+'QDialog {background:#101b2e; color:#eaf3ff;}')
        layout=QVBoxLayout(dialogo)
        tabla=QTableWidget(len(platos),5)
        tabla.setHorizontalHeaderLabels(['Plato','Preparación','Acompañamiento / Extra','Unidades','Importe B/.'])
        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabla.verticalHeader().hide()
        for i,p in enumerate(platos):
            for j,texto in enumerate((p['nombre'],p['preparacion'], ' / '.join(x for x in (p['acompanamiento'],p['extra']) if x),str(p['unidades']),f"B/. {p['centimos']/100:.2f}")):
                tabla.setItem(i,j,QTableWidgetItem(texto))
        layout.addWidget(tabla)
        self.hide()
        try:dialogo.exec()
        finally:
            if isValid(self.ventana) and self.ventana.isVisible():
                self.contenido.setEnabled(False);self.show();self.raise_()

    def showEvent(self, evento):
        self.contenido.setEnabled(False)
        super().showEvent(evento)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0,self.ajustar_filas)

    def closeEvent(self, evento):
        self.ventana.removeEventFilter(self)
        self.contenido.setEnabled(self.contenido_habilitado)
        foco = self.foco_anterior
        if foco is not None and isValid(foco) and foco.isVisible():
            foco.setFocus()
        super().closeEvent(evento)

    def eventFilter(self, objeto, evento):
        if objeto is self.ventana:
            if evento.type() == QEvent.Type.Resize:
                self.setGeometry(self.ventana.rect())
                self.raise_()
            elif evento.type() == QEvent.Type.Close:
                self.close()
        return False

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.ajustar_filas()
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.fillRect(self.rect(), QColor(3, 8, 17, 215))


class PaginaHorarioTurnos(QWidget):
    DIAS = (
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo",
    )

    def __init__(self, gestion, parent=None):
        super().__init__(parent)
        self.gestion = gestion
        self.setObjectName("PaginaHorarioTurnos")
        self.setStyleSheet("""
            QWidget#PaginaHorarioTurnos { background: #0b1425; color: #eaf3ff; }
            QLabel { color: #DCE4F0; background: transparent; font-size: 17px; }
            QLabel#TituloHorarioTurnos {
                color: #79eaff; font-size: 29px; font-weight: 600;
            }
            QLabel#EstadoHorarioTurnos { color: #54e3b7; font-size: 16px; }
            QWidget#PaginaHorarioTurnos QComboBox,
            QWidget#PaginaHorarioTurnos QTimeEdit {
                background: #101e34; color: #eaf3ff; border: 1px solid #287b99;
                border-radius: 10px; padding: 10px 14px; font-size: 19px;
                min-height: 48px;
            }
            QWidget#PaginaHorarioTurnos QComboBox QAbstractItemView {
                background: #111f35; color: #eaf3ff; selection-background-color: #20d9f5;
                selection-color: #111827;
            }
            QWidget#PaginaHorarioTurnos QPushButton {
                background: #20d9f5; color: #111827; border: 2px solid #20d9f5;
                border-radius: 12px; padding: 14px 20px; font-size: 19px;
                font-weight: bold; min-height: 54px;
            }
            QWidget#PaginaHorarioTurnos QPushButton#EliminarHorario {
                background: #71343C; color: white; border-color: #A65660;
            }
            QTreeWidget {
                background: #0b1425; alternate-background-color: #182337;
                color: #eaf3ff; gridline-color: #287b99;
                border: 1px solid #287b99; border-radius: 8px; font-size: 16px;
            }
            QHeaderView::section {
                background: #112e45; color: #79eaff; border: 1px solid #287b99;
                padding: 10px; font-size: 15px; font-weight: bold;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Horario semanal de cajeros")
        titulo.setObjectName("TituloHorarioTurnos")
        layout.addWidget(titulo)
        descripcion = QLabel(
            "Al cerrar un turno, el siguiente horario futuro recibe automáticamente "
            "todo el inventario disponible y queda pendiente de apertura."
        )
        descripcion.setWordWrap(True)
        layout.addWidget(descripcion)

        controles = QHBoxLayout()
        self.selector_dia = QComboBox()
        for dia, nombre in enumerate(self.DIAS):
            self.selector_dia.addItem(nombre, dia)
        controles.addWidget(self.selector_dia, 1)

        self.selector_hora = QTimeEdit()
        self.selector_hora.setDisplayFormat("h:mm AP")
        self.selector_hora.setTime(QTime(8, 0))
        self.selector_hora.setMinimumWidth(140)
        controles.addWidget(self.selector_hora)

        self.selector_cajero = QComboBox()
        self.selector_cajero.setMinimumWidth(220)
        controles.addWidget(self.selector_cajero, 1)
        layout.addLayout(controles)

        self.btn_agregar_horario = QPushButton("Agregar al horario")
        self.btn_agregar_horario.clicked.connect(self.agregar_horario)
        layout.addWidget(self.btn_agregar_horario)

        self.horarios = QTreeWidget()
        self.horarios.setColumnCount(4)
        self.horarios.setHeaderLabels(["Día", "Próxima fecha", "Hora", "Cajero"])
        self.horarios.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.horarios.setAlternatingRowColors(True)
        self.horarios.setRootIsDecorated(False)
        self.horarios.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horarios.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.horarios.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.horarios.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.horarios, 1)

        self.btn_eliminar_horario = QPushButton("Eliminar horario seleccionado")
        self.btn_eliminar_horario.setObjectName("EliminarHorario")
        self.btn_eliminar_horario.clicked.connect(self.eliminar_horario)
        layout.addWidget(self.btn_eliminar_horario)

        self.estado = QLabel()
        self.estado.setObjectName("EstadoHorarioTurnos")
        self.estado.setWordWrap(True)
        layout.addWidget(self.estado)
        self.actualizar()

    def actualizar(self):
        self.selector_cajero.clear()
        self.horarios.clear()
        try:
            for usuario_id, nombre in self.gestion.empleados():
                self.selector_cajero.addItem(nombre, usuario_id)
            ahora = datetime.now()
            for horario_id, dia, hora, _, cajero in self.gestion.horarios_programados():
                proxima_fecha = GestionTurnos._proxima_ocurrencia(dia, hora, ahora)
                hora_visible = proxima_fecha.strftime("%I:%M %p").lstrip("0")
                elemento = QTreeWidgetItem([
                    self.DIAS[dia],
                    proxima_fecha.strftime("%d/%m/%Y"),
                    hora_visible,
                    cajero,
                ])
                elemento.setData(0, Qt.ItemDataRole.UserRole, horario_id)
                self.horarios.addTopLevelItem(elemento)
        except (ValueError, PermissionError, sqlite3.Error) as error:
            self.estado.setText(f"No se pudo cargar el horario: {error}")
            self.btn_agregar_horario.setEnabled(False)
            return
        self.btn_agregar_horario.setEnabled(bool(self.selector_cajero.count()))
        if not self.selector_cajero.count():
            self.estado.setText("Primero agrega usuarios de caja en Usuarios y permisos.")
        elif not self.horarios.topLevelItemCount():
            self.estado.setText("Todavía no hay turnos semanales configurados.")
        else:
            self.estado.setText("")

    def agregar_horario(self):
        usuario_id = self.selector_cajero.currentData()
        if usuario_id is None:
            self.estado.setText("Selecciona un cajero.")
            return
        try:
            self.gestion.guardar_horario(
                self.selector_dia.currentData(),
                self.selector_hora.time().toString("HH:mm"),
                usuario_id,
            )
        except (ValueError, PermissionError, sqlite3.Error) as error:
            self.estado.setText(str(error))
            return
        self.actualizar()
        self.estado.setText("Horario semanal guardado.")

    def eliminar_horario(self):
        elemento = self.horarios.currentItem()
        if elemento is None:
            self.estado.setText("Selecciona un horario para eliminar.")
            return
        horario_id = elemento.data(0, Qt.ItemDataRole.UserRole)
        try:
            self.gestion.eliminar_horario(horario_id)
        except (PermissionError, sqlite3.Error) as error:
            self.estado.setText(f"No se pudo eliminar el horario: {error}")
            return
        self.actualizar()
        self.estado.setText("Horario eliminado.")

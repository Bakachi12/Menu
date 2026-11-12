"""PedidosTable: solicitudes LAN; solo el TPV puede aceptarlas o rechazarlas.

Sin dependencia de Qt: cada operación usa su propia conexión SQLite. Los hilos
HTTP nunca escriben cuentas, ventas ni inventario.
"""
from cocina import preparar_cocina
from pedidos_cocina import PAGINA as PAGINA_COCINA
from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread, Lock
from time import monotonic
from urllib.parse import urlsplit
import hashlib
import json
import secrets
import sqlite3
import uuid


class SolicitudesTable:
    def __init__(self, ruta):
        self.ruta = str(ruta)
        with self.conexion() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS solicitudes_table (
                id TEXT PRIMARY KEY, dispositivo TEXT NOT NULL, mesa TEXT NOT NULL,
                cliente_id INTEGER, productos TEXT NOT NULL, nota TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'pendiente', fecha TEXT NOT NULL,
                responsable_id INTEGER, resuelta TEXT
            )''')

            db.execute("""CREATE TABLE IF NOT EXISTS terminales_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, huella TEXT NOT NULL UNIQUE
            )""")
            preparar_cocina(db)
            if 'tipo' not in {r[1] for r in db.execute('PRAGMA table_info(terminales_table)')}:
                db.execute("ALTER TABLE terminales_table ADD COLUMN tipo TEXT NOT NULL DEFAULT 'mesas'")
            columnas = {r[1] for r in db.execute('PRAGMA table_info(solicitudes_table)')}
            for campo, tipo in [('emisor_id', 'INTEGER'), ('emisor', 'TEXT')]:
                if campo not in columnas:
                    db.execute(f'ALTER TABLE solicitudes_table ADD COLUMN {campo} {tipo}')

    @contextmanager
    def conexion(self):
        db = sqlite3.connect(self.ruta, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def vincular(self, nombre, tipo="mesas"):
        clave = secrets.token_urlsafe(32)
        with self.conexion() as db:
            cursor = db.execute("INSERT INTO terminales_table(nombre, huella, tipo) VALUES (?, ?, ?)",
                                (nombre.strip()[:60], hashlib.sha256(clave.encode()).hexdigest(), tipo))
            identificador = cursor.lastrowid
            if not nombre.strip():
                db.execute("UPDATE terminales_table SET nombre=? WHERE id=?",
                           (f"Terminal {identificador}", identificador))
        return clave

    def terminales(self):
        with self.conexion() as db:
            return db.execute("SELECT id, nombre FROM terminales_table ORDER BY id").fetchall()

    def revocar(self, identificador):
        with self.conexion() as db:
            db.execute("DELETE FROM terminales_table WHERE id=?", (identificador,))

    def terminal(self, clave):
        with self.conexion() as db:
            return db.execute("SELECT id,nombre,tipo FROM terminales_table WHERE huella=?",
                              (hashlib.sha256(clave.encode()).hexdigest(),)).fetchone()

    def resumen(self, incluir_catalogo=True):
        with self.conexion() as db:
            productos = [dict(r) for r in db.execute('''SELECT id, nombre,
                precio_centimos, categoria FROM productos WHERE activo = 1 ORDER BY id''')] if incluir_catalogo else []
            mesas = []
            for (nombre,) in db.execute('SELECT nombre FROM mesas_configuracion ORDER BY id'):
                fila = db.execute('SELECT productos FROM pedidos_abiertos WHERE mesa = ?', (nombre,)).fetchone()
                cuenta = json.loads(fila[0]) if fila else []
                clientes = [dict(c) for c in db.execute('SELECT id, nombre FROM clientes WHERE mesa = ?', (nombre,))]
                mesas.append(dict(nombre=nombre, clientes=clientes, cuenta=cuenta,
                                  total_centimos=sum(round(p['precio'] * 100) for p in cuenta)))
        return dict(productos=productos, mesas=mesas) if incluir_catalogo else dict(mesas=mesas)

    @staticmethod
    def validar_destino(db, mesa, cliente_id):
        if not isinstance(mesa, str) or not db.execute(
                'SELECT 1 FROM mesas_configuracion WHERE nombre = ?', (mesa,)).fetchone():
            raise ValueError('La mesa ya no está disponible.')
        if cliente_id is not None and (type(cliente_id) is not int or not db.execute(
                'SELECT 1 FROM clientes WHERE id = ? AND mesa = ?', (cliente_id, mesa)).fetchone()):
            raise ValueError('El cliente ya no pertenece a esta mesa.')

    def enviar(self, datos, empleado=None):
        if not isinstance(datos, dict):
            raise ValueError('Solicitud inválida.')
        try:
            identificador = str(uuid.UUID(datos.get('id', '')))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Identificador de solicitud inválido.') from None
        mesa, cliente = datos.get('mesa'), datos.get('cliente_id')
        dispositivo, nota, lineas = datos.get('dispositivo', ''), datos.get('nota', ''), datos.get('lineas')
        if not isinstance(dispositivo, str) or len(dispositivo.strip()) > 60:
            raise ValueError('Escribe el nombre de este dispositivo (máximo 60 caracteres).')
        if not isinstance(nota, str) or len(nota) > 300:
            raise ValueError('La nota admite hasta 300 caracteres.')
        if not isinstance(lineas, list) or not 1 <= len(lineas) <= 100:
            raise ValueError('Selecciona al menos un producto.')
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            anterior = db.execute('SELECT id, estado FROM solicitudes_table WHERE id = ?', (identificador,)).fetchone()
            if anterior:
                return dict(anterior)
            self.validar_destino(db, mesa, cliente)
            if db.execute("SELECT COUNT(*) FROM solicitudes_table WHERE estado = 'pendiente'").fetchone()[0] >= 300:
                raise ValueError('La bandeja está llena. Espera a que el cajero revise las solicitudes.')
            productos = []
            for linea in lineas:
                if not isinstance(linea, dict) or type(linea.get('producto_id')) is not int or type(linea.get('cantidad')) is not int:
                    raise ValueError('Producto o cantidad inválidos.')
                cantidad = linea['cantidad']
                if not 1 <= cantidad <= 99 or len(productos) + cantidad > 200:
                    raise ValueError('Máximo 99 unidades por línea y 200 por solicitud.')
                fila = db.execute('SELECT nombre, categoria, precio_centimos FROM productos WHERE id = ? AND activo = 1',
                                  (linea['producto_id'],)).fetchone()
                if not fila:
                    raise ValueError('Un producto ya no está disponible. Actualiza el menú.')
                productos.extend([dict(producto_id=linea['producto_id'], nombre=fila[0],
                                       categoria=fila[1], precio=fila[2] / 100)] * cantidad)
            db.execute('''INSERT INTO solicitudes_table
                (id, dispositivo, mesa, cliente_id, productos, nota, fecha, emisor_id, emisor)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (identificador, dispositivo.strip(), mesa, cliente,
                json.dumps(productos, ensure_ascii=False), nota.strip(), datetime.now().isoformat(timespec='seconds'),
                empleado['id'] if empleado else None, empleado['usuario'] if empleado else None))
        return dict(id=identificador, estado='pendiente')

    def listar(self):
        with self.conexion() as db:
            return [dict(r) for r in db.execute("SELECT * FROM solicitudes_table WHERE estado = 'pendiente' ORDER BY fecha, rowid")]

    def estado(self, identificador):
        with self.conexion() as db:
            fila = db.execute('SELECT id, estado FROM solicitudes_table WHERE id = ?', (identificador,)).fetchone()
            if not fila:
                raise ValueError('Solicitud no encontrada.')
            return dict(fila)

    def resolver(self, identificador, aceptar, sesion, turnos):
        # Se llama exclusivamente desde el hilo de Qt, usando la sesión real.
        turnos.exigir_turno_activo()
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            solicitud = db.execute('SELECT * FROM solicitudes_table WHERE id = ?', (identificador,)).fetchone()
            if not solicitud or solicitud['estado'] != 'pendiente':
                raise ValueError('La solicitud ya fue revisada.')
            cuenta = None
            if aceptar:
                mesa, cliente = solicitud['mesa'], solicitud['cliente_id']
                self.validar_destino(db, mesa, cliente)
                nombre = db.execute('SELECT nombre FROM clientes WHERE id = ?', (cliente,)).fetchone() if cliente is not None else None
                nuevos = json.loads(solicitud['productos'])
                for p in nuevos:
                    actual = db.execute('SELECT nombre, categoria, precio_centimos FROM productos WHERE id = ? AND activo = 1',
                                        (p['producto_id'],)).fetchone()
                    if not actual or tuple(actual) != (p['nombre'], p['categoria'], round(p['precio'] * 100)):
                        raise ValueError('El catálogo cambió. Rechaza esta solicitud y pide enviarla de nuevo.')
                    p.pop('producto_id')
                    p.update(cliente_id=cliente, cliente_nombre=nombre[0] if nombre else '')
                fila = db.execute('SELECT productos FROM pedidos_abiertos WHERE mesa = ?', (mesa,)).fetchone()
                cuenta = (json.loads(fila[0]) if fila else []) + nuevos
                db.execute('''INSERT INTO pedidos_abiertos(mesa, productos) VALUES (?, ?)
                    ON CONFLICT(mesa) DO UPDATE SET productos = excluded.productos''', (mesa, json.dumps(cuenta, ensure_ascii=False)))
            db.execute('''UPDATE solicitudes_table SET estado = ?, responsable_id = ?, resuelta = ? WHERE id = ?''',
                       ('aceptada' if aceptar else 'rechazada', sesion.usuario['id'], datetime.now().isoformat(timespec='seconds'), identificador))
        return solicitud['mesa'], cuenta


class ServidorTable:
    def __init__(self, solicitudes, identificar):
        self.identificar = identificar
        self.solicitudes = solicitudes
        self.http = None

    def iniciar(self, host='0.0.0.0', puerto=8765):
        if self.http:
            return self.http.server_port
        servicio = self.solicitudes
        pagina = Path(__file__).with_name('pedidos_table.html').read_bytes()

        sesiones = {}
        bloqueo = Lock()
        identificar = self.identificar

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(10)

            def log_message(self, *args):
                pass  # No guardar claves ni datos de clientes en registros HTTP.

            def responder(self, codigo, datos, tipo='application/json; charset=utf-8'):
                contenido = datos if isinstance(datos, bytes) else json.dumps(datos, ensure_ascii=False).encode()
                self.send_response(codigo)
                self.send_header('Content-Type', tipo)
                self.send_header('Content-Length', str(len(contenido)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('X-Frame-Options', 'DENY')
                self.end_headers()
                self.wfile.write(contenido)

            def autorizado(self):
                token = self.headers.get('X-Sesion', '')
                with bloqueo:
                    cuenta, caduca, terminal_id = sesiones.get(token, (None, 0, None))
                    if caduca <= monotonic():
                        sesiones.pop(token, None)
                        return False
                    self.empleado = cuenta
                return self.enlace_valido() and self.terminal[0] == terminal_id

            def enlace_valido(self, tipo="mesas"):
                esquema, _, clave = self.headers.get('Authorization', '').partition(' ')
                self.terminal = servicio.terminal(clave) if esquema == 'Bearer' and clave else None
                return self.terminal is not None and self.terminal[2] == tipo

            def do_GET(self):
                ruta = urlsplit(self.path).path
                if ruta == '/cocina':
                    return self.responder(200, PAGINA_COCINA, 'text/html; charset=utf-8')
                if ruta == '/api/cocina':
                    if not self.enlace_valido('cocina'):
                        return self.responder(401, dict(error='Enlace de cocina requerido.'))
                    try:
                        with servicio.conexion() as db:
                            filas = db.execute("SELECT id,fecha,mesa,cliente,plato,preparacion,acompanamiento,extra "
                                              "FROM ordenes_cocina WHERE estado='pendiente' ORDER BY id")
                            ordenes = [dict(f) for f in filas]
                        return self.responder(200, ordenes)
                    except sqlite3.Error:
                        return self.responder(503, dict(error='Cola no disponible.'))
                if ruta == '/':
                    return self.responder(200, pagina, 'text/html; charset=utf-8')
                if not self.autorizado():
                    return self.responder(401, dict(error='Clave incorrecta o conexión reiniciada.'))
                try:
                    if ruta == '/api/cuentas':
                        return self.responder(200, servicio.resumen(False))
                    if ruta == '/api/resumen':
                        return self.responder(200, servicio.resumen())
                    if ruta.startswith('/api/solicitudes/'):
                        return self.responder(200, servicio.estado(ruta.rsplit('/', 1)[-1]))
                    if ruta.startswith('/api/imagen/'):
                        with servicio.conexion() as db:
                            fila = db.execute('SELECT imagen FROM productos WHERE id = ? AND activo = 1', (ruta.rsplit('/', 1)[-1],)).fetchone()
                        if fila and fila[0]:
                            imagen = Path(fila[0])
                            # Solo imágenes gestionadas por el TPV, nunca rutas del cliente.
                            raiz = Path(servicio.ruta).resolve().parent / 'imagenes'
                            if imagen.resolve().parent == raiz and imagen.suffix.lower() == '.png' and imagen.stat().st_size <= 5_000_000:
                                return self.responder(200, imagen.read_bytes(), 'image/png')
                    self.responder(404, dict(error='Recurso no encontrado.'))
                except ValueError as e:
                    self.responder(400, dict(error=str(e)))
                except (sqlite3.Error, OSError):
                    self.responder(503, dict(error='No se pudo leer. Inténtalo de nuevo.'))

            def do_POST(self):
                partes = urlsplit(self.path).path.strip('/').split('/')
                if len(partes) == 4 and partes[:2] == ['api', 'cocina'] and partes[3] == 'lista':
                    if not self.enlace_valido('cocina'):
                        return self.responder(401, dict(error='Enlace de cocina requerido.'))
                    if not partes[2].isascii() or not partes[2].isdigit() or len(partes[2]) > 18:
                        return self.responder(400, dict(error='Orden inválida.'))
                    try:
                        with servicio.conexion() as db:
                            db.execute("UPDATE ordenes_cocina SET estado='lista' WHERE id=? AND estado='pendiente'",
                                       (int(partes[2]),))
                        return self.responder(200, {})
                    except sqlite3.Error:
                        return self.responder(503, dict(error='No se pudo actualizar la orden.'))
                login = self.path == '/api/login'
                if not self.enlace_valido() or (not login and not self.autorizado()):
                    return self.responder(401, dict(error='Inicia sesión con tu cuenta.'))
                if self.path == '/api/logout':
                    with bloqueo:
                        sesiones.pop(self.headers.get('X-Sesion'), None)
                    return self.responder(200, {})
                if not login and self.path != '/api/solicitudes':
                    return self.responder(404, dict(error='Recurso no encontrado.'))
                try:
                    longitud = int(self.headers.get('Content-Length', '0'))
                    if not 0 < longitud <= 24000:
                        raise ValueError('Solicitud demasiado grande o vacía.')
                    if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                        raise ValueError('Se requiere JSON.')
                    datos = json.loads(self.rfile.read(longitud))
                    if login:
                        if not isinstance(datos, dict):
                            raise ValueError('Credenciales inválidas.')
                        usuario, password = datos.get('usuario'), datos.get('password')
                        if not all(isinstance(v, str) and 0 < len(v) <= 128 for v in (usuario, password)):
                            raise ValueError('Introduce tu usuario y contraseña.')
                        empleado = identificar(usuario, password)
                        if not empleado:
                            return self.responder(401, dict(error='Usuario o contraseña incorrectos.'))
                        token = secrets.token_urlsafe(32)
                        with bloqueo:
                            sesiones[token] = empleado, monotonic() + 8 * 3600, self.terminal[0]
                        return self.responder(200, dict(token=token, usuario=empleado['usuario']))
                    if isinstance(datos, dict):
                        datos['dispositivo'] = self.terminal[1]
                    self.responder(200, servicio.enviar(datos, self.empleado))
                except (ValueError, UnicodeDecodeError) as e:
                    self.responder(400, dict(error=str(e)))
                except sqlite3.Error:
                    self.responder(503, dict(error='No se pudo guardar. Reintenta el envío.'))

        self.http = ThreadingHTTPServer((host, puerto), Handler)
        Thread(target=self.http.serve_forever, daemon=True).start()
        return self.http.server_port

    def detener(self):
        if self.http:
            self.http.shutdown()
            self.http.server_close()
            self.http = None

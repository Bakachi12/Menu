"""PedidosTable: solicitudes LAN; solo el TPV puede aceptarlas o rechazarlas.

Sin dependencia de Qt: cada operación usa su propia conexión SQLite. Los hilos
HTTP nunca escriben cuentas, ventas ni inventario.
"""
from pedidos_cocina import PAGINA as PAGINA_COCINA
from cocina import preparar_cocina, platos_cocina, cambiar_disponibilidad, validar_aumentos, sincronizar_comandas, seccion_inicial, acompanamientos, opciones, COCINA
from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread, Lock
from time import monotonic
from urllib.parse import parse_qs, urlsplit
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

    def catalogo(self, db):
        columnas = {r[1] for r in db.execute('PRAGMA table_info(productos)')}
        seccion = 'seccion' if 'seccion' in columnas else "'' AS seccion"
        preparaciones = 'preparaciones' if 'preparaciones' in columnas else "'' AS preparaciones"
        lleva = 'lleva_acompanamiento' if 'lleva_acompanamiento' in columnas else '1 AS lleva_acompanamiento'
        cantidad = 'cantidad_acompanamientos' if 'cantidad_acompanamientos' in columnas else '1 AS cantidad_acompanamientos'
        filas = db.execute(f"SELECT id,nombre,precio_centimos,categoria,{seccion},{preparaciones},{lleva},{cantidad} FROM productos WHERE activo=1 ORDER BY id")
        agotados = {r[0] for r in db.execute('SELECT producto_id FROM platos_agotados')}
        productos = []
        for fila in filas:
            p = dict(fila)
            p['seccion'] = p['seccion'] or seccion_inicial(p['nombre'], p['categoria'])
            from cocina import preparaciones_con_recargo
            p['recargos_preparacion'] = preparaciones_con_recargo(p['preparaciones'] or '')
            p['preparaciones'] = opciones(p['preparaciones'] or '')
            if not p['preparaciones'] and 'hamburguesa' in p['nombre'].casefold():
                p['preparaciones'] = ['Completa', 'Sin vegetales']
            p['disponible'] = p['id'] not in agotados
            productos.append(p)
        return productos

    def producto_solicitado(self, db, identificador, seleccion):
        catalogo = self.catalogo(db)
        p = next((p for p in catalogo if p['id'] == identificador), None)
        if not p or not p['disponible']:
            raise ValueError('Un producto ya no está disponible. Actualiza el menú.')
        nuevo = dict(producto_id=identificador, nombre=p['nombre'], categoria=p['categoria'], precio=p['precio_centimos'] / 100)
        if p['seccion'] == COCINA:
            if not isinstance(seleccion, dict):
                raise ValueError('Selecciona la preparación y el acompañamiento del plato.')
            preparacion, lado, extra = (seleccion.get(k, '') for k in ('preparacion', 'acompanamiento', 'extra'))
            from cocina import seleccion_preparaciones
            elegidas = seleccion_preparaciones(preparacion, p['preparaciones'])
            lados = seleccion_preparaciones(lado, acompanamientos(catalogo))
            if (not isinstance(extra, str) or (p['preparaciones'] and not elegidas)
                    or (not lados or len(lados) > p['cantidad_acompanamientos'] if p['lleva_acompanamiento'] else bool(lados or extra))
                    or (extra and extra not in lados)):
                raise ValueError('La preparación o el acompañamiento ya no están disponibles.')
            recargos = dict(db.execute('SELECT nombre,centimos FROM recargos_acompanamiento'))
            cargo = recargos.get(extra, 0) if extra else 0
            lado = ' · '.join(lados)
            if extra and cargo <= 0:
                raise ValueError('La porción extra ya no está disponible.')
            cargo += sum(p['recargos_preparacion'].get(v, 0) for v in elegidas)
            preparacion = ' · '.join(elegidas)
            nuevo.update(preparacion=preparacion, acompanamiento=lado, extra=extra, recargo_centimos=cargo)
            nuevo['precio'] = (p['precio_centimos'] + cargo) / 100
        return nuevo

    def resumen(self, incluir_catalogo=True):
        with self.conexion() as db:
            productos = self.catalogo(db) if incluir_catalogo else []
            mesas = []
            for (nombre,) in db.execute('SELECT nombre FROM mesas_configuracion ORDER BY id'):
                fila = db.execute('SELECT productos FROM pedidos_abiertos WHERE mesa = ?', (nombre,)).fetchone()
                cuenta = json.loads(fila[0]) if fila else []
                clientes = [dict(c) for c in db.execute('SELECT id, nombre FROM clientes WHERE mesa = ?', (nombre,))]
                mesas.append(dict(nombre=nombre, clientes=clientes, cuenta=cuenta,
                                  total_centimos=sum(round(p['precio'] * 100) for p in cuenta)))
            recargos = dict(db.execute('SELECT nombre,centimos FROM recargos_acompanamiento')) if incluir_catalogo else {}
        return dict(productos=productos, mesas=mesas, acompanamientos=acompanamientos(productos), recargos=recargos) if incluir_catalogo else dict(mesas=mesas)

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
                nuevo = self.producto_solicitado(db, linea['producto_id'], linea.get('seleccion'))
                for _ in range(cantidad):
                    unidad = dict(nuevo)
                    if 'acompanamiento' in nuevo:
                        unidad['unidad_cocina'] = uuid.uuid4().hex
                    productos.append(unidad)
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

    def resolver_directas(self,sesion,turnos):
        usuario=sesion.usuario
        if not usuario or usuario.get('tipo')!='venta_libre':return []
        incorporadas=[]
        for solicitud in self.listar():
            if solicitud['emisor_id']!=usuario['id']:continue
            try:
                incorporadas.append(self.resolver(solicitud['id'],True,sesion,turnos,automatico=True))
            except PermissionError:
                break
            except ValueError:
                # A stale destination/catalogue cannot silently change a bill.
                try:self.resolver(solicitud['id'],False,sesion,turnos,automatico=True)
                except (ValueError,PermissionError):pass
        return incorporadas

    def resolver(self, identificador, aceptar, sesion, turnos, *, automatico=False):
        # Se llama exclusivamente desde el hilo de Qt, usando la sesión real.
        turnos.exigir_turno_activo()
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            solicitud = db.execute('SELECT * FROM solicitudes_table WHERE id = ?', (identificador,)).fetchone()
            if not solicitud or solicitud['estado'] != 'pendiente':
                raise ValueError('La solicitud ya fue revisada.')
            if automatico:
                usuario=sesion.usuario
                perfil=sesion.perfil(usuario['id']) if usuario and hasattr(sesion,'perfil') else usuario
                if (not usuario or usuario.get('tipo')!='venta_libre' or not perfil
                        or perfil.get('tipo')!='venta_libre' or solicitud['emisor_id']!=usuario['id']):
                    raise PermissionError('El envío directo requiere el mismo usuario de Venta libre en PC y tablet.')
            cuenta = None
            if aceptar:
                mesa, cliente = solicitud['mesa'], solicitud['cliente_id']
                self.validar_destino(db, mesa, cliente)
                nombre = db.execute('SELECT nombre FROM clientes WHERE id = ?', (cliente,)).fetchone() if cliente is not None else None
                nuevos = json.loads(solicitud['productos'])
                for p in nuevos:
                    actual = self.producto_solicitado(db, p['producto_id'], p if 'acompanamiento' in p else None)
                    if any(p.get(k) != v for k, v in actual.items()):
                        raise ValueError('El catálogo cambió. Rechaza esta solicitud y pide enviarla de nuevo.')
                    p.pop('producto_id')
                    p.update(cliente_id=cliente, cliente_nombre=nombre[0] if nombre else '')
                validar_aumentos(db, [], nuevos)
                fila = db.execute('SELECT productos FROM pedidos_abiertos WHERE mesa = ?', (mesa,)).fetchone()
                anteriores = json.loads(fila[0]) if fila else []
                cuenta = anteriores + nuevos
                sincronizar_comandas(db, mesa, anteriores, cuenta)
                db.execute('''INSERT INTO pedidos_abiertos(mesa, productos) VALUES (?, ?)
                    ON CONFLICT(mesa) DO UPDATE SET productos = excluded.productos''', (mesa, json.dumps(cuenta, ensure_ascii=False)))
            db.execute('''UPDATE solicitudes_table SET estado = ?, responsable_id = ?, resuelta = ? WHERE id = ?''',
                       ('aceptada' if aceptar else 'rechazada', sesion.usuario['id'], datetime.now().isoformat(timespec='seconds'), identificador))
        return solicitud['mesa'], cuenta


class ServidorTable:
    def __init__(self, solicitudes, identificar, envio_directo=None):
        self.envio_directo=envio_directo
        self.identificar = identificar
        self.solicitudes = solicitudes
        self.http = None

    def iniciar(self, host='0.0.0.0', puerto=8765):
        if self.http:
            return self.http.server_port
        servicio = self.solicitudes
        envio_directo=self.envio_directo
        pagina = Path(__file__).with_name('pedidos_table.html').read_bytes()
        fondo = Path(__file__).with_name('fondo_bar.png').read_bytes()

        sesiones = {}
        bloqueo = Lock()
        identificar = self.identificar
        perfil = getattr(getattr(identificar, '__self__', None), 'perfil', None)

        def permite_terminal(cuenta, tipo):
            rol = cuenta.get('rol', 'admin') if cuenta else None
            return rol in (('admin','cocinero') if tipo == 'cocina' else ('admin','mesas','mesero'))

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

            def autorizado(self, tipo="mesas"):
                token = self.headers.get('X-Sesion', '')
                with bloqueo:
                    cuenta, caduca, terminal_id = sesiones.get(token, (None, 0, None))
                    if caduca <= monotonic():
                        sesiones.pop(token, None)
                        return False
                    if perfil:
                        cuenta = perfil(cuenta['id'])
                    if not permite_terminal(cuenta, tipo):
                        sesiones.pop(token, None)
                        return False
                    self.empleado = cuenta
                return self.enlace_valido(tipo) and self.terminal[0] == terminal_id

            def enlace_valido(self, tipo="mesas"):
                esquema, _, clave = self.headers.get('Authorization', '').partition(' ')
                self.terminal = servicio.terminal(clave) if esquema == 'Bearer' and clave else None
                return self.terminal is not None and self.terminal[2] == tipo

            def do_GET(self):
                ruta = urlsplit(self.path).path
                if ruta == '/fondo_bar.png':
                    return self.responder(200, fondo, 'image/png')
                if ruta == '/cocina':
                    return self.responder(200, PAGINA_COCINA, 'text/html; charset=utf-8')
                if ruta in ('/api/cocina', '/api/cocina/listas', '/api/cocina/disponibilidad'):
                    if not self.autorizado('cocina'):
                        return self.responder(401, dict(error='Vincula esta terminal e inicia sesión en cocina.'))
                    try:
                        with servicio.conexion() as db:
                            if ruta.endswith('/disponibilidad'):
                                return self.responder(200, platos_cocina(db))
                            consulta = ("SELECT id,fecha,mesa,cliente,plato,preparacion,acompanamiento,extra "
                                        "FROM ordenes_cocina WHERE estado=?")
                            if ruta.endswith('/listas'):
                                antes = parse_qs(urlsplit(self.path).query).get('antes', [None])[0]
                                parametros = ['lista']
                                if antes is not None:
                                    if not antes.isascii() or not antes.isdigit() or len(antes) > 18:
                                        return self.responder(400, dict(error='Página de órdenes inválida.'))
                                    consulta += " AND id < ?"
                                    parametros.append(int(antes))
                                filas = db.execute(consulta + " ORDER BY id DESC LIMIT 51", parametros)
                                listas = [dict(f) for f in filas]
                                return self.responder(200, dict(ordenes=listas[:50], hay_mas=len(listas) > 50))
                            ordenes = [dict(f) for f in db.execute(consulta + " ORDER BY id", ('pendiente',))]
                        return self.responder(200, ordenes)
                    except sqlite3.Error:
                        return self.responder(503, dict(error='Cola no disponible.'))
                if ruta == '/api/vinculo':
                    if not self.enlace_valido():
                        return self.responder(401, dict(error='El vínculo no es válido o fue retirado. Genera un nuevo enlace de PedidosTable en la caja.', vinculo_invalido=True))
                    return self.responder(200, dict(vinculado=True))
                if ruta == '/':
                    return self.responder(200, pagina, 'text/html; charset=utf-8')
                if not self.autorizado():
                    return self.responder(401, dict(error='Inicia sesión de nuevo o revisa el vínculo con la caja.', vinculo_invalido=not self.enlace_valido()))
                try:
                    if ruta == '/api/cuentas':
                        resultado=servicio.resumen(False)
                        resultado['envio_directo']=bool(envio_directo and envio_directo(self.empleado))
                        return self.responder(200,resultado)
                    if ruta == '/api/resumen':
                        resultado=servicio.resumen()
                        resultado['envio_directo']=bool(envio_directo and envio_directo(self.empleado))
                        return self.responder(200,resultado)
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
                if len(partes) == 5 and partes[:3] == ['api', 'cocina', 'disponibilidad']:
                    if not self.autorizado('cocina'):
                        return self.responder(401, dict(error='Inicia sesión en cocina.'))
                    try:
                        if not partes[3].isascii() or not partes[3].isdigit() or len(partes[3]) > 18 or partes[4] not in ('disponible', 'agotado'):
                            raise ValueError('Cambio de disponibilidad inválido.')
                        with servicio.conexion() as db:
                            cambiar_disponibilidad(db, int(partes[3]), partes[4] == 'disponible')
                        return self.responder(200, {})
                    except ValueError as e:
                        return self.responder(400, dict(error=str(e)))
                    except sqlite3.Error:
                        return self.responder(503, dict(error='No se pudo guardar la disponibilidad.'))
                if len(partes) == 4 and partes[:2] == ['api', 'cocina'] and partes[3] in ('lista', 'rellamar'):
                    if not self.autorizado('cocina'):
                        return self.responder(401, dict(error='Vincula esta terminal e inicia sesión en cocina.'))
                    if not partes[2].isascii() or not partes[2].isdigit() or len(partes[2]) > 18:
                        return self.responder(400, dict(error='Orden inválida.'))
                    try:
                        with servicio.conexion() as db:
                            origen, destino = ('pendiente', 'lista') if partes[3] == 'lista' else ('lista', 'pendiente')
                            db.execute("UPDATE ordenes_cocina SET estado=? WHERE id=? AND estado=?",
                                       (destino, int(partes[2]), origen))
                            fila = db.execute("SELECT estado FROM ordenes_cocina WHERE id=?", (int(partes[2]),)).fetchone()
                            if not fila or fila[0] != destino:
                                return self.responder(409, dict(error='Esta orden ya no está disponible.'))
                        return self.responder(200, {})
                    except sqlite3.Error:
                        return self.responder(503, dict(error='No se pudo actualizar la orden.'))
                tipo = 'cocina' if self.path in ('/api/cocina/login', '/api/cocina/logout') else 'mesas'
                login = self.path in ('/api/login', '/api/cocina/login')
                if not self.enlace_valido(tipo):
                    return self.responder(401, dict(error='Vínculo incorrecto o retirado. Vuelve a vincular con la caja.', vinculo_invalido=True))
                if not login and not self.autorizado(tipo):
                    return self.responder(401, dict(error='Inicia sesión con tu cuenta.'))
                if self.path in ('/api/logout', '/api/cocina/logout'):
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
                        if not permite_terminal(empleado, tipo):
                            return self.responder(403, dict(error='Tu rol no tiene permiso para esta terminal.'))
                        token = secrets.token_urlsafe(32)
                        with bloqueo:
                            sesiones[token] = empleado, monotonic() + 8 * 3600, self.terminal[0]
                        return self.responder(200, dict(token=token, usuario=empleado['usuario']))
                    if isinstance(datos, dict):
                        datos['dispositivo'] = self.terminal[1]
                    resultado=servicio.enviar(datos,self.empleado)
                    resultado['envio_directo']=bool(envio_directo and envio_directo(self.empleado))
                    self.responder(200,resultado)
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

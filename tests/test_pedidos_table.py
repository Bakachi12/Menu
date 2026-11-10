"""Pruebas con base temporal; no requieren Qt ni datos del negocio."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pedidos_table import SolicitudesTable, ServidorTable


class Sesion:
    usuario = dict(id=7, rol='admin')

    def __init__(self, ruta):
        self.ruta = ruta

    @contextmanager
    def conexion(self):
        db = sqlite3.connect(self.ruta)
        try:
            with db:
                yield db
        finally:
            db.close()


class Turnos:
    def exigir_turno_activo(self):
        pass


class TestPedidosTable(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ruta = Path(self.temp.name) / 'ventas.db'
        self.sesion = Sesion(self.ruta)
        self.turnos = Turnos()
        with self.sesion.conexion() as db:
            db.executescript('''
                CREATE TABLE productos(id INTEGER PRIMARY KEY, nombre TEXT, categoria TEXT,
                    precio_centimos INTEGER, activo INTEGER, imagen TEXT);
                INSERT INTO productos VALUES(1, 'Café', 'Bebidas', 250, 1, NULL);
                INSERT INTO productos VALUES(2, 'Té', 'Bebidas', 175, 0, NULL);
                CREATE TABLE mesas_configuracion(id INTEGER PRIMARY KEY, nombre TEXT);
                INSERT INTO mesas_configuracion VALUES(1, 'Mesa 01');
                CREATE TABLE clientes(id INTEGER PRIMARY KEY, nombre TEXT, mesa TEXT);
                INSERT INTO clientes VALUES(9, 'Alberto', 'Mesa 01');
                CREATE TABLE pedidos_abiertos(mesa TEXT PRIMARY KEY, productos TEXT);
                CREATE TABLE ventas(id INTEGER PRIMARY KEY, fecha TEXT, mesa TEXT,
                    cliente TEXT, productos TEXT, total REAL, turno_id INTEGER);
            ''')
        self.servicio = SolicitudesTable(self.ruta)

    def datos(self, **cambios):
        return dict(dict(id=str(uuid4()), mesa='Mesa 01', cliente_id=9,
                         dispositivo='Tablet terraza', nota='Sin azúcar',
                         lineas=[dict(producto_id=1, cantidad=2)]), **cambios)

    def test_enviar_no_cambia_cuenta_y_ignora_precio_cliente(self):
        datos = self.datos(precio=0.01)
        self.servicio.enviar(datos)
        with self.sesion.conexion() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM pedidos_abiertos').fetchone()[0], 0)
        productos = json.loads(self.servicio.listar()[0]['productos'])
        self.assertEqual([p['precio'] for p in productos], [2.5, 2.5])

    def test_reintento_concurrente_es_una_solicitud(self):
        datos = self.datos()
        with ThreadPoolExecutor(max_workers=4) as pool:
            resultados = list(pool.map(lambda _: self.servicio.enviar(datos), range(8)))
        self.assertEqual(len({r['id'] for r in resultados}), 1)
        self.assertEqual(len(self.servicio.listar()), 1)

    def test_aceptacion_conserva_cuenta_y_no_duplica(self):
        viejo = dict(nombre='Té', precio=1.75, cliente_id=None)
        with self.sesion.conexion() as db:
            db.execute('INSERT INTO pedidos_abiertos VALUES (?, ?)', ('Mesa 01', json.dumps([viejo])))
        id_ = self.servicio.enviar(self.datos())['id']
        mesa, cuenta = self.servicio.resolver(id_, True, self.sesion, self.turnos)
        self.assertEqual(mesa, 'Mesa 01')
        self.assertEqual(len(cuenta), 3)
        self.assertEqual(cuenta[0], viejo)
        self.assertEqual(cuenta[1]['cliente_nombre'], 'Alberto')
        self.assertEqual(self.servicio.estado(id_)['estado'], 'aceptada')
        with self.assertRaises(ValueError):
            self.servicio.resolver(id_, True, self.sesion, self.turnos)

    def test_rechazar_no_cambia_cuenta(self):
        id_ = self.servicio.enviar(self.datos())['id']
        self.assertEqual(self.servicio.resolver(id_, False, self.sesion, self.turnos), ('Mesa 01', None))
        self.assertEqual(self.servicio.estado(id_)['estado'], 'rechazada')
        self.assertEqual(self.servicio.resumen()['mesas'][0]['cuenta'], [])

    def test_exige_turno(self):
        id_ = self.servicio.enviar(self.datos())['id']
        class SinTurno:
            def exigir_turno_activo(self):
                raise PermissionError('Sin turno')
        for aceptar in (True, False):
            with self.assertRaises(PermissionError):
                self.servicio.resolver(id_, aceptar, self.sesion, SinTurno())
        self.assertEqual(self.servicio.estado(id_)['estado'], 'pendiente')

    def test_revalida_cliente_y_precio_al_aceptar(self):
        id_ = self.servicio.enviar(self.datos())['id']
        with self.sesion.conexion() as db:
            db.execute('UPDATE clientes SET mesa = NULL')
        with self.assertRaises(ValueError):
            self.servicio.resolver(id_, True, self.sesion, self.turnos)
        with self.sesion.conexion() as db:
            db.execute("UPDATE clientes SET mesa = 'Mesa 01'")
            db.execute('UPDATE productos SET precio_centimos = 300 WHERE id = 1')
        with self.assertRaises(ValueError):
            self.servicio.resolver(id_, True, self.sesion, self.turnos)
        self.assertEqual(self.servicio.estado(id_)['estado'], 'pendiente')

    def test_error_revierte_aceptacion_completa(self):
        id_ = self.servicio.enviar(self.datos())['id']
        with self.sesion.conexion() as db:
            db.execute("""CREATE TRIGGER fallo BEFORE UPDATE ON solicitudes_table
                BEGIN SELECT RAISE(ABORT, 'Fallo de prueba'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.servicio.resolver(id_, True, self.sesion, self.turnos)
        self.assertEqual(self.servicio.resumen()['mesas'][0]['cuenta'], [])
        self.assertEqual(self.servicio.estado(id_)['estado'], 'pendiente')

    def test_rechaza_productos_y_cantidades_invalidas(self):
        for cantidad in (0, -1, True, 1.5, 100):
            with self.subTest(cantidad=cantidad), self.assertRaises(ValueError):
                self.servicio.enviar(self.datos(lineas=[dict(producto_id=1, cantidad=cantidad)]))
        with self.assertRaises(ValueError):
            self.servicio.enviar(self.datos(lineas=[dict(producto_id=2, cantidad=1)]))
        with self.assertRaises(ValueError):
            self.servicio.enviar(self.datos(mesa='Mesa inexistente'))
        self.assertEqual(self.servicio.listar(), [])

    def test_cobro_rechaza_solicitud_pendiente(self):
        # Importar solo la capa de cobro, sin crear una QApplication.
        mocks = {'PySide6.QtCore': SimpleNamespace(QStandardPaths=None),
                 'clientes': SimpleNamespace(centimos=lambda p: round(p['precio'] * 100), nombre_operacion=lambda m: m)}
        spec = importlib.util.spec_from_file_location('datos_cobro_test', Path(__file__).resolve().parents[1] / 'datos.py')
        datos = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, mocks):
            spec.loader.exec_module(datos)
        id_ = self.servicio.enviar(self.datos())['id']
        datos.registrar_venta(self.sesion, 'Mesa 01', 'Alberto', [dict(nombre='Café', precio=2.5)])
        self.assertEqual(self.servicio.estado(id_)['estado'], 'rechazada')
        with self.assertRaises(ValueError):
            self.servicio.resolver(id_, True, self.sesion, self.turnos)
        self.assertEqual(self.servicio.resumen()['mesas'][0]['cuenta'], [])

    def test_http_autenticacion_envio_estado_y_rotacion(self):
        servidor = ServidorTable(self.servicio, lambda u, p: dict(id=4, usuario=u) if (u,p)==('ana','prueba') else None)
        puerto = servidor.iniciar(host='127.0.0.1', puerto=0)
        self.addCleanup(servidor.detener)
        url = f'http://127.0.0.1:{puerto}'
        with urlopen(url) as r:
            self.assertIn(b'PedidosTable', r.read())
        with self.assertRaises(HTTPError) as error:
            urlopen(url + '/api/resumen')
        self.assertEqual(error.exception.code, 401)
        clave = servidor.clave
        headers = {'Authorization': 'Bearer ' + clave, 'Content-Type': 'application/json'}
        with self.assertRaises(HTTPError):
            urlopen(Request(url + '/api/resumen', headers=headers))
        def login(password):
            return urlopen(Request(url+'/api/login', headers=headers,
                            data=json.dumps(dict(usuario='ana',password=password)).encode()))
        with self.assertRaises(HTTPError):
            login('incorrecta')
        with login('prueba') as respuesta:
            headers['X-Sesion'] = json.load(respuesta)['token']
        req = Request(url + '/api/solicitudes', data=json.dumps(self.datos()).encode(),
                      headers=headers)
        with urlopen(req) as r:
            resultado = json.load(r)
        self.assertEqual(resultado['estado'], 'pendiente')
        req = Request(url + '/api/solicitudes/' + resultado['id'], headers=headers)
        with urlopen(req) as r:
            self.assertEqual(json.load(r)['estado'], 'pendiente')
        self.assertEqual(self.servicio.listar()[0]['emisor'], 'ana')
        with urlopen(Request(url+'/api/logout', headers=headers, data=b'{}')):
            pass
        with self.assertRaises(HTTPError):
            urlopen(Request(url+'/api/resumen', headers=headers))
        servidor.detener()
        servidor.iniciar(host='127.0.0.1', puerto=0)
        self.assertNotEqual(clave, servidor.clave)


if __name__ == '__main__':
    unittest.main()

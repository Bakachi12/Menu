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
        datos.inicializar_catalogo(self.sesion, [])
        datos.registrar_venta(self.sesion, 'Mesa 01', 'Alberto', [dict(nombre='Café', precio=2.5)], metodo_pago='Clave')
        self.assertEqual(self.servicio.estado(id_)['estado'], 'rechazada')
        with self.assertRaises(ValueError):
            self.servicio.resolver(id_, True, self.sesion, self.turnos)
        self.assertEqual(self.servicio.resumen()['mesas'][0]['cuenta'], [])

    def preparar_platos(self):
        with self.servicio.conexion() as db:
            db.execute("ALTER TABLE productos ADD COLUMN seccion TEXT NOT NULL DEFAULT 'Bebidas'")
            db.execute("ALTER TABLE productos ADD COLUMN preparaciones TEXT NOT NULL DEFAULT ''")
            db.execute("INSERT INTO productos VALUES(3,'Hamburguesa','Comidas',650,1,NULL,'Cocina','')")
            db.execute("INSERT INTO productos VALUES(4,'Yuca','Guarniciones',250,1,NULL,'Acompañamiento','')")
            db.execute("INSERT INTO recargos_acompanamiento VALUES('Yuca',125)")
        return dict(preparacion='Sin vegetales', acompanamiento='Yuca', extra='Yuca')

    def test_personalizacion_llega_a_caja_y_cocina_sin_duplicar(self):
        seleccion = self.preparar_platos()
        datos = self.datos(lineas=[dict(producto_id=3, cantidad=2, seleccion=seleccion, precio=0.01)])
        identificador = self.servicio.enviar(datos)['id']
        self.servicio.enviar(datos)
        productos = json.loads(self.servicio.listar()[0]['productos'])
        self.assertEqual([p['precio'] for p in productos], [7.75, 7.75])
        self.assertEqual(len({p['unidad_cocina'] for p in productos}), 2)
        with self.servicio.conexion() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ordenes_cocina').fetchone()[0], 0)
        _, cuenta = self.servicio.resolver(identificador, True, self.sesion, self.turnos)
        self.assertEqual(cuenta[0]['preparacion'], 'Sin vegetales')
        self.assertEqual(cuenta[0]['recargo_centimos'], 125)
        with self.servicio.conexion() as db:
            filas = db.execute('SELECT preparacion,acompanamiento,extra FROM ordenes_cocina').fetchall()
            self.assertEqual([tuple(f) for f in filas], [('Sin vegetales', 'Yuca', 'Yuca')] * 2)
        with self.assertRaises(ValueError):
            self.servicio.resolver(identificador, True, self.sesion, self.turnos)

    def test_platos_rechazan_opciones_falsas_y_cambios_de_recargo(self):
        seleccion = self.preparar_platos()
        for invalida in (None, dict(seleccion, preparacion='Inventada'), dict(seleccion, acompanamiento='Inexistente'), dict(seleccion, extra='Papas')):
            with self.subTest(invalida=invalida), self.assertRaises(ValueError):
                self.servicio.enviar(self.datos(lineas=[dict(producto_id=3, cantidad=1, seleccion=invalida)]))
        identificador = self.servicio.enviar(self.datos(lineas=[dict(producto_id=3, cantidad=1, seleccion=seleccion)]))['id']
        with self.servicio.conexion() as db:
            db.execute("UPDATE recargos_acompanamiento SET centimos=150 WHERE nombre='Yuca'")
        with self.assertRaises(ValueError):
            self.servicio.resolver(identificador, True, self.sesion, self.turnos)
        self.assertEqual(self.servicio.estado(identificador)['estado'], 'pendiente')
        with self.servicio.conexion() as db:
            db.execute('INSERT INTO platos_agotados VALUES(3)')
        self.assertFalse(next(p for p in self.servicio.resumen()['productos'] if p['id'] == 3)['disponible'])
        with self.assertRaises(ValueError):
            self.servicio.enviar(self.datos(lineas=[dict(producto_id=3, cantidad=1, seleccion=seleccion)]))

    def test_vincular_antes_de_login_y_revocar(self):
        servidor = ServidorTable(self.servicio, lambda u, p: None)
        puerto = servidor.iniciar(host='127.0.0.1', puerto=0)
        self.addCleanup(servidor.detener)
        url = f'http://127.0.0.1:{puerto}'
        def consultar(clave, ruta='/api/vinculo'):
            return urlopen(Request(url + ruta, headers={'Authorization': 'Bearer ' + clave}))
        with self.assertRaises(HTTPError) as error:
            consultar('incorrecta')
        self.assertTrue(json.load(error.exception)['vinculo_invalido'])
        cocina = self.servicio.vincular('Cocina', 'cocina')
        with self.assertRaises(HTTPError):
            consultar(cocina)
        clave = self.servicio.vincular('Tablet')
        with consultar(clave) as respuesta:
            self.assertEqual(json.load(respuesta), {'vinculado': True})
        with self.assertRaises(HTTPError):
            consultar(clave, '/api/resumen')
        self.servicio.revocar(self.servicio.terminal(clave)[0])
        with self.assertRaises(HTTPError) as error:
            consultar(clave)
        self.assertEqual(error.exception.code, 401)
        self.assertTrue(json.load(error.exception)['vinculo_invalido'])

    def test_http_autenticacion_envio_estado_y_rotacion(self):
        servidor = ServidorTable(self.servicio, lambda u, p: dict(id=4, usuario=u) if (u,p)==('ana','prueba') else None)
        puerto = servidor.iniciar(host='127.0.0.1', puerto=0)
        self.addCleanup(servidor.detener)
        url = f'http://127.0.0.1:{puerto}'
        with urlopen(url) as r:
            self.assertIn(b'PedidosTable', r.read())
        with urlopen(url + '/fondo_bar.png') as r:
            self.assertEqual(r.headers['Content-Type'], 'image/png')
            self.assertEqual(r.read(8), b'\x89PNG\r\n\x1a\n')
        with self.assertRaises(HTTPError) as error:
            urlopen(url + '/api/resumen')
        self.assertEqual(error.exception.code, 401)
        clave = self.servicio.vincular('Terraza')
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
        url = f"http://127.0.0.1:{servidor.iniciar(host='127.0.0.1', puerto=0)}"
        with login('prueba') as respuesta:
            headers['X-Sesion'] = json.load(respuesta)['token']
        with urlopen(Request(url+'/api/cuentas', headers=headers)) as respuesta:
            self.assertNotIn('productos', json.load(respuesta))
        otra = self.servicio.vincular('')
        self.servicio.revocar(self.servicio.terminal(clave)[0])
        self.assertIsNotNone(self.servicio.terminal(otra))
        with self.assertRaises(HTTPError):
            urlopen(Request(url+'/api/cuentas', headers=headers))



    def test_venta_libre_same_user_is_added_automatically_once(self):
        self.sesion.usuario=dict(id=7,rol='mesas',tipo='venta_libre')
        datos=self.datos()
        id_=self.servicio.enviar(datos,dict(id=7,usuario='alberto'))['id']
        incorporadas=self.servicio.resolver_directas(self.sesion,self.turnos)
        self.assertEqual(len(incorporadas),1)
        self.assertEqual(len(incorporadas[0][1]),2)
        self.assertEqual(self.servicio.estado(id_)['estado'],'aceptada')
        self.servicio.enviar(datos,dict(id=7,usuario='alberto'))
        self.assertEqual(self.servicio.resolver_directas(self.sesion,self.turnos),[])

    def test_other_user_and_normal_profiles_still_need_approval(self):
        self.sesion.usuario=dict(id=7,rol='mesas',tipo='venta_libre')
        id_=self.servicio.enviar(self.datos(emisor_id=7),dict(id=8,usuario='otro'))['id']
        self.assertEqual(self.servicio.resolver_directas(self.sesion,self.turnos),[])
        self.assertEqual(self.servicio.estado(id_)['estado'],'pendiente')
        self.sesion.usuario=dict(id=8,rol='mesas',tipo='normal')
        self.assertEqual(self.servicio.resolver_directas(self.sesion,self.turnos),[])

    def test_auto_send_checks_inventory_and_rejects_changed_prices(self):
        self.sesion.usuario=dict(id=7,rol='mesas',tipo='venta_libre')
        id_=self.servicio.enviar(self.datos(),dict(id=7,usuario='alberto'))['id']
        class Bloqueado:
            def exigir_turno_activo(self):raise PermissionError('Inventario sin verificar')
        self.assertEqual(self.servicio.resolver_directas(self.sesion,Bloqueado()),[])
        self.assertEqual(self.servicio.estado(id_)['estado'],'pendiente')
        with self.servicio.conexion() as db:db.execute('UPDATE productos SET precio_centimos=300 WHERE id=1')
        self.assertEqual(self.servicio.resolver_directas(self.sesion,self.turnos),[])
        self.assertEqual(self.servicio.estado(id_)['estado'],'rechazada')
        with self.servicio.conexion() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM pedidos_abiertos').fetchone()[0],0)

    def test_http_direct_mode_follows_current_pc_account(self):
        empleado=dict(id=7,usuario='alberto',rol='mesas',tipo='venta_libre')
        self.sesion.usuario=empleado.copy()
        servidor=ServidorTable(self.servicio,lambda u,p:empleado,lambda e:self.sesion.usuario['id']==e['id'])
        puerto=servidor.iniciar(host='127.0.0.1',puerto=0);self.addCleanup(servidor.detener)
        url=f'http://127.0.0.1:{puerto}'
        clave=self.servicio.vincular('Tablet')
        headers={'Authorization':'Bearer '+clave,'Content-Type':'application/json'}
        with urlopen(Request(url+'/api/login',headers=headers,data=json.dumps(dict(usuario='alberto',password='prueba')).encode())) as r:headers['X-Sesion']=json.load(r)['token']
        with urlopen(Request(url+'/api/resumen',headers=headers)) as r:self.assertTrue(json.load(r)['envio_directo'])
        self.sesion.usuario=dict(id=8)
        with urlopen(Request(url+'/api/cuentas',headers=headers)) as r:self.assertFalse(json.load(r)['envio_directo'])


if __name__ == '__main__':
    unittest.main()

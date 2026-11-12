import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cocina import sincronizar_comandas, validar_aumentos
from pedidos_table import ServidorTable, SolicitudesTable


class ColaCocina(unittest.TestCase):
    def setUp(self):
        carpeta = TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        self.servicio = SolicitudesTable(Path(carpeta.name) / 'ventas.db')
        self.yuca = dict(unidad_cocina='a', nombre='Camarones', preparacion='Al ajillo',
                         acompanamiento='Yuca', extra='Yuca', recargo_centimos=125)
        self.papas = dict(self.yuca, unidad_cocina='b', acompanamiento='Papas fritas', extra='')

    def test_html_descargable_coincide_con_la_terminal(self):
        from pedidos_cocina import PAGINA
        self.assertEqual(PAGINA.decode(), (Path(__file__).resolve().parents[1] / "PedidosCocina.html").read_text(encoding="utf-8"))

    def test_rollback_reintento_resta_y_bebidas(self):
        cuenta = [self.yuca, self.papas, dict(nombre='Café')]
        with self.assertRaises(sqlite3.IntegrityError), self.servicio.conexion() as db:
            sincronizar_comandas(db, 'Mesa 01', [], cuenta)
            db.execute("INSERT INTO recargos_acompanamiento VALUES ('Yuca', -1)")
        with self.servicio.conexion() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ordenes_cocina').fetchone()[0], 0)
            sincronizar_comandas(db, 'Mesa 01', [], cuenta)
            sincronizar_comandas(db, 'Mesa 01', cuenta, cuenta)
            sincronizar_comandas(db, 'Mesa 01', cuenta, [self.papas])
            filas = db.execute('SELECT unidad, estado FROM ordenes_cocina ORDER BY id')
            self.assertEqual([tuple(f) for f in filas], [('a', 'retirada'), ('b', 'pendiente')])

    def test_cola_http_en_orden_y_terminal_revocada(self):
        with self.servicio.conexion() as db:
            sincronizar_comandas(db, 'Mesa 01', [], [self.yuca, self.papas])
        def identificar(usuario, password):
            return {'usuario': usuario} if (usuario, password) == ('turno', 'prueba') else None

        servidor = ServidorTable(self.servicio, identificar)
        puerto = servidor.iniciar('127.0.0.1', 0)
        self.addCleanup(servidor.detener)
        clave = self.servicio.vincular('Pantalla', 'cocina')

        sesion = ''

        def consultar(ruta, metodo='GET', token=clave, datos=None):
            peticion = Request(f'http://127.0.0.1:{puerto}'+ruta,
                               headers={'Authorization': 'Bearer '+token, 'X-Sesion': sesion,
                                        'Content-Type': 'application/json'}, method=metodo,
                               data=json.dumps(datos).encode() if datos else None)
            with urlopen(peticion, timeout=3) as respuesta:
                return json.load(respuesta)

        def denegada(ruta, metodo='GET', **opciones):
            with self.assertRaises(HTTPError) as error:
                consultar(ruta, metodo, **opciones)
            self.assertEqual(error.exception.code, 401)

        perfil = dict(usuario='turno', password='prueba')
        denegada('/api/cocina/listas')
        denegada('/api/cocina/1/rellamar', 'POST')
        denegada('/api/cocina')
        denegada('/api/cocina/1/lista', 'POST')
        denegada('/api/cocina/login', 'POST', datos=dict(usuario='turno', password='incorrecta'))
        denegada('/api/login', 'POST', datos=perfil)
        sesion = consultar('/api/cocina/login', 'POST', datos=perfil)['token']
        denegada('/api/cocina', token=self.servicio.vincular('Otra cocina', 'cocina'))
        consultar('/api/cocina/logout', 'POST')
        denegada('/api/cocina')
        sesion = consultar('/api/cocina/login', 'POST', datos=perfil)['token']
        with self.servicio.conexion() as db:
            db.executescript("""CREATE TABLE productos(id INTEGER PRIMARY KEY, nombre TEXT, categoria TEXT, seccion TEXT, activo INTEGER);
                INSERT INTO productos VALUES(4, 'Camarones', 'General', NULL, 1), (5, 'Café','Bebidas',NULL,1);""")
        ruta = '/api/cocina/disponibilidad'
        denegada(ruta+'/4/agotado', 'POST', token=self.servicio.vincular('Mesero'))
        self.assertEqual([p['id'] for p in consultar(ruta)], [4])
        consultar(ruta+'/4/agotado', 'POST')
        self.assertFalse(consultar(ruta)[0]['disponible'])
        with self.servicio.conexion() as db:
            validar_aumentos(db, [self.yuca], [self.yuca])
            with self.assertRaisesRegex(ValueError, 'No disponible'):
                validar_aumentos(db, [self.yuca], [self.yuca, self.yuca])
        consultar(ruta+'/4/disponible', 'POST')
        self.assertTrue(consultar(ruta)[0]['disponible'])
        cola = consultar('/api/cocina')
        self.assertEqual([p['extra'] for p in cola], ['Yuca', ''])
        for _ in range(2):
            consultar(f"/api/cocina/{cola[0]['id']}/lista", 'POST')
        self.assertEqual(consultar('/api/cocina'), cola[1:])
        historial = consultar('/api/cocina/listas')
        self.assertEqual(historial, dict(ordenes=cola[:1], hay_mas=False))
        for _ in range(2):
            consultar(f"/api/cocina/{cola[0]['id']}/rellamar", 'POST')
        self.assertEqual(consultar('/api/cocina'), cola)
        self.assertEqual(consultar('/api/cocina/listas')['ordenes'], [])
        consultar(f"/api/cocina/{cola[0]['id']}/lista", 'POST')
        with self.servicio.conexion() as db:
            sincronizar_comandas(db, 'Mesa 01', [self.yuca, self.papas], [self.papas])
        with self.assertRaises(HTTPError) as error:
            consultar(f"/api/cocina/{cola[0]['id']}/rellamar", 'POST')
        self.assertEqual(error.exception.code, 409)
        mesas = self.servicio.vincular('Mesas')
        with self.assertRaises(HTTPError) as error:
            consultar('/api/cocina', token=mesas)
        self.assertEqual(error.exception.code, 401)
        self.servicio.revocar(self.servicio.terminal(clave)[0])
        with self.assertRaises(HTTPError) as error:
            consultar('/api/cocina')
        self.assertEqual(error.exception.code, 401)

import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cocina import sincronizar_comandas
from pedidos_table import ServidorTable, SolicitudesTable


class ColaCocina(unittest.TestCase):
    def setUp(self):
        carpeta = TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        self.servicio = SolicitudesTable(Path(carpeta.name) / 'ventas.db')
        self.yuca = dict(unidad_cocina='a', nombre='Camarones', preparacion='Al ajillo',
                         acompanamiento='Yuca', extra='Yuca', recargo_centimos=125)
        self.papas = dict(self.yuca, unidad_cocina='b', acompanamiento='Papas fritas', extra='')

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
        servidor = ServidorTable(self.servicio, lambda *_: None)
        puerto = servidor.iniciar('127.0.0.1', 0)
        self.addCleanup(servidor.detener)
        clave = self.servicio.vincular('Pantalla', 'cocina')

        def consultar(ruta, metodo='GET', token=clave):
            peticion = Request(f'http://127.0.0.1:{puerto}'+ruta,
                               headers={'Authorization': 'Bearer '+token}, method=metodo)
            with urlopen(peticion, timeout=3) as respuesta:
                return json.load(respuesta)

        cola = consultar('/api/cocina')
        self.assertEqual([p['extra'] for p in cola], ['Yuca', ''])
        for _ in range(2):
            consultar(f"/api/cocina/{cola[0]['id']}/lista", 'POST')
        self.assertEqual(consultar('/api/cocina'), cola[1:])
        mesas = self.servicio.vincular('Mesas')
        with self.assertRaises(HTTPError) as error:
            consultar('/api/cocina', token=mesas)
        self.assertEqual(error.exception.code, 401)
        self.servicio.revocar(self.servicio.terminal(clave)[0])
        with self.assertRaises(HTTPError) as error:
            consultar('/api/cocina')
        self.assertEqual(error.exception.code, 401)

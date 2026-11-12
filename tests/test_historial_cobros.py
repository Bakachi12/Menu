"""Cobros de caja y visibilidad del historial con una base temporal."""
from pathlib import Path
import importlib.util
import sys
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from tempfile import TemporaryDirectory

from test_pedidos_table import Sesion


class HistorialCobros(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.sesion = Sesion(Path(temp.name) / 'ventas.db')
        self.sesion.es_admin = lambda: self.sesion.usuario['rol'] == 'admin'
        spec = importlib.util.spec_from_file_location('cobros', Path(__file__).resolve().parents[1] / 'datos.py')
        self.datos = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'PySide6.QtCore': SimpleNamespace(QStandardPaths=None),
                                      'clientes': SimpleNamespace(centimos=lambda p: round(p['precio']*100), nombre_operacion=str)}):
            spec.loader.exec_module(self.datos)
        with self.sesion.conexion() as db:
            db.executescript("""
                CREATE TABLE ventas(id INTEGER PRIMARY KEY, fecha TEXT, mesa TEXT, cliente TEXT, productos TEXT, total REAL, turno_id INTEGER);
                INSERT INTO ventas VALUES(1,'2026-11-01','Mesa antigua','','[]',3,1);
                INSERT INTO ventas VALUES(2,'2026-11-02','Sin identificar','','[]',2,NULL);
                CREATE TABLE turnos(id INTEGER PRIMARY KEY, usuario_id INTEGER, estado TEXT);
                INSERT INTO turnos VALUES(1,10,'activo'),(2,20,'activo');
                CREATE TABLE pedidos_abiertos(mesa TEXT PRIMARY KEY, productos TEXT);
                CREATE TABLE clientes(mesa TEXT);
                CREATE TABLE turno_inventario(turno_id,producto_id,producto_nombre,producto_categoria,cantidad_apertura,cantidad_vendida);
                INSERT INTO turno_inventario VALUES(1,1,'Café','General',10,0),(2,1,'Café','General',10,0);
                CREATE TABLE movimientos_inventario(producto_id,producto_nombre,producto_categoria,tipo,cantidad,usuario_id,turno_id,detalle);
            """)
        self.datos.inicializar_catalogo(self.sesion, [])

    def cobrar(self, usuario, turno, metodo):
        self.sesion.usuario = dict(id=usuario, rol='mesas')
        self.datos.registrar_venta(self.sesion,'Mesa 01','Ana',[dict(nombre='Café', precio=2.5)],turno,metodo_pago=metodo)

    def test_cajeros_solo_ven_sus_cuentas_incluso_despues_del_turno(self):
        for metodo in self.datos.METODOS_PAGO:
            self.cobrar(10,1,metodo)
        self.cobrar(20,2,'Visa')
        self.assertEqual(len(self.datos.historial_cobros(self.sesion)),1)
        with self.sesion.conexion() as db:
            db.execute("UPDATE turnos SET estado='cerrado'")
            self.assertEqual([r[0] for r in db.execute('SELECT detalle FROM movimientos_inventario WHERE usuario_id=10')],
                             ['Cobro · '+m for m in self.datos.METODOS_PAGO])
        self.sesion.usuario = dict(id=10, rol='mesas')
        filas = self.datos.historial_cobros(self.sesion)
        self.assertEqual([r[-1] for r in filas],['Efectivo','Yappy','Visa','Clave','Sin registrar'])
        self.sesion.usuario = dict(id=1, rol='admin')
        self.assertEqual(len(self.datos.historial_cobros(self.sesion)),7)
        self.sesion.usuario = None
        with self.assertRaises(PermissionError):
            self.datos.historial_cobros(self.sesion)

    def test_metodo_invalido_no_cobra(self):
        with self.assertRaises(ValueError):
            self.cobrar(10,1,'Otro')
        with self.sesion.conexion() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ventas').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM movimientos_inventario').fetchone()[0],0)

    def test_platos_cobrados_sin_stock_en_turno_y_venta_libre(self):
        self.sesion.exigir_admin = lambda: None
        self.datos.inicializar_catalogo(self.sesion, [dict(nombre='Hamburguesa', precio=6.5)])
        plato = dict(nombre='Hamburguesa', categoria='General', precio=6.5)
        bebida = dict(nombre='Café', categoria='General', precio=2.5)
        self.sesion.usuario = dict(id=10, rol='mesas')
        self.datos.registrar_venta(self.sesion, 'Mesa 01', '', [plato, bebida, plato], 1, metodo_pago='Visa')
        self.sesion.usuario['tipo'] = 'venta_libre'
        self.sesion.inventario_libre_verificado = True
        self.datos.registrar_venta(self.sesion, 'Venta rápida', '', [plato], metodo_pago='Efectivo')
        self.assertEqual(self.datos.cantidades_cocina_hoy(self.sesion), [('Hamburguesa', 3)])
        with self.sesion.conexion() as db:
            self.assertEqual(db.execute("SELECT producto_nombre,cantidad FROM movimientos_inventario").fetchall(), [('Café', 1)])
            self.assertEqual(db.execute("SELECT total FROM ventas ORDER BY id DESC LIMIT 2").fetchall(), [(6.5,), (15.5,)])
            self.assertFalse(db.execute("SELECT 1 FROM productos_inventario_bar WHERE nombre='Hamburguesa'").fetchall())

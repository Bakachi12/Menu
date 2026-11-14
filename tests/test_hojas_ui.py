import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QPushButton,QTableWidget
from inventario import PaginaHojaInventarios,_DetalleHojaInventario

class HojasInventarioUITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_date_filter_includes_end_date_and_orders_free_and_assigned_sheets(self):
        def fila(id,nombre,fecha):return dict(turno_id=id,cajero=nombre,asignacion_fecha=fecha,cierre_fecha=None,estado='activo')
        class Gestion:
            def hoja_inventarios(self):return [fila(99,'Antiguo','2026-11-12 12:00:00'),fila(1,'Intermedio','2026-11-13 00:00:00'),fila(-1,'Reciente libre','2026-11-14T23:59:59')]
        pagina=PaginaHojaInventarios(Gestion());pagina.actualizar()
        def nombres():
            return [pagina.lista_tarjetas.itemAt(i).widget().findChild(QPushButton).text().splitlines()[0] for i in range(pagina.lista_tarjetas.count()-1)]
        self.assertEqual(nombres(),['Cajero  ·  Reciente libre','Cajero  ·  Intermedio','Cajero  ·  Antiguo'])
        pagina.fecha_desde.setDate(QDate(2026,11,13));pagina.fecha_hasta.setDate(QDate(2026,11,14));pagina.aplicar_fechas()
        self.assertEqual(nombres(),['Cajero  ·  Reciente libre','Cajero  ·  Intermedio'])
        pagina.fecha_desde.setDate(QDate(2026,11,15));pagina.aplicar_fechas()
        self.assertIn('no puede',pagina.estado.text())
        pagina.quitar_fechas();self.assertEqual(len(nombres()),3)
        pagina.deleteLater();self.app.processEvents()

    def test_payment_breakdown_and_product_total_are_inside_grid(self):
        w=QMainWindow();w.setCentralWidget(QWidget());w.resize(1280,800)
        turno=dict(turno_id=1,cajero='CAPU1',asignacion_fecha='2026-11-13',cierre_fecha='2026-11-13',estado='cerrado')
        filas=[dict(turno,producto='Cristal · Bebidas',recibida=93,agregada=0,vendida=19,dinero_centimos=1900,entregada=74,faltante=0,sobrante=0)]
        detalle=_DetalleHojaInventario(w,turno,filas,dict(importes=dict(Efectivo=200,Yappy=1700,Clave=0,Visa=0),total_centimos=1900,ambiguas=0))
        tabla=detalle.findChild(QTableWidget,'CuadriculaHojaInventario')
        self.assertEqual(tabla.item(tabla.rowCount()-1,0).text(),'TOTAL VENDIDO')
        self.assertEqual(tabla.item(tabla.rowCount()-1,3).text(),'19')
        self.assertEqual(tabla.item(tabla.rowCount()-1,4).text(),'B/. 19.00')
        self.assertEqual([tabla.item(i,3).text() for i in range(1,5)],['Efectivo','Yappy','Clave','Visa'])
        detalle.close();w.deleteLater();self.app.processEvents()

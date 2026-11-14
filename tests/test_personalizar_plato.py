"""Prueba táctil del asistente de platos, sin abrir datos del negocio."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QStackedWidget
from dialogos import DialogoIntegrado
from vista_pedidos import personalizar_plato

class PersonalizarPlatoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.ventana = QMainWindow()
        self.central = QWidget()
        self.central.setStyleSheet('background: #204438;')
        self.ventana.setCentralWidget(self.central)
        self.ventana.resize(1200, 800)
        self.ventana.show()
        self.errores = []

    def tearDown(self):
        self.ventana.close()
        self.app.processEvents()

    def ejecutar(self, producto, accion, lados=None):
        def probar():
            dialogo = next(d for d in self.ventana.findChildren(DialogoIntegrado) if d.isVisible())
            try:
                self.assertFalse(dialogo.isWindow())
                self.assertLess(dialogo._tarjeta_integrada.width(), self.ventana.width())
                self.assertFalse(self.central.isEnabled())
                accion(dialogo)
            except BaseException as error:
                self.errores.append(error)
                dialogo.reject()
        QTimer.singleShot(30, probar)
        resultado = personalizar_plato(self.central, producto, lados or ['Papas', 'Yuca'], {'Papas': 150})
        if self.errores:
            raise self.errores[0]
        self.assertTrue(self.central.isEnabled())
        return resultado

    def boton(self, dialogo, texto):
        return next(b for b in dialogo.findChildren(QPushButton) if b.text() == texto)

    def test_preparacion_acompanamiento_extra_y_atras(self):
        def elegir(d):
            paginas = d.findChild(QStackedWidget)
            siguiente = d.findChild(QPushButton, 'ContinuarPlato')
            self.assertFalse(siguiente.isEnabled())
            self.boton(d, 'Sin vegetales').click()
            self.assertTrue(self.boton(d, 'Sin vegetales').isChecked())
            siguiente.click()
            self.assertEqual(paginas.currentIndex(), 1)
            self.assertFalse(siguiente.isEnabled())
            self.boton(d, 'Papas').click()
            self.boton(d, 'Porción extra (+B/.1.50)').click()
            self.boton(d, 'Yuca').click()
            self.assertFalse(self.boton(d, 'Papas').isChecked())
            self.assertFalse(self.boton(d, 'Porción extra no disponible').isChecked())
            self.boton(d, 'Papas').click()
            self.boton(d, 'Porción extra (+B/.1.50)').click()
            self.boton(d, 'Atrás').click()
            self.assertTrue(self.boton(d, 'Sin vegetales').isChecked())
            siguiente.click()
            self.ventana.resize(800, 600)
            self.app.processEvents()
            self.assertEqual(d._tarjeta_integrada.height(), 552)
            siguiente.click()
        r = self.ejecutar(dict(nombre='Hamburguesa', precio=6.5, preparaciones=''), elegir)
        self.assertEqual(r, dict(preparacion='Sin vegetales', acompanamiento='Papas', extra='Papas', recargo_centimos=150))

    def test_preparaciones_configuradas(self):
        def elegir(d):
            self.boton(d, 'Al ajillo').click()
            d.findChild(QPushButton, 'ContinuarPlato').click()
            self.boton(d, 'Yuca').click()
            d.findChild(QPushButton, 'ContinuarPlato').click()
        r = self.ejecutar(dict(nombre='Camarones', precio=10, preparaciones='Al ajillo, Fritos'), elegir)
        self.assertEqual(r['preparacion'], 'Al ajillo')

    def test_confirmaciones_admin_integradas(self):
        from dialogos import MensajesIntegrados
        def elegir():
            d = next(d for d in self.ventana.findChildren(DialogoIntegrado) if d.isVisible())
            self.assertFalse(d.isWindow())
            self.boton(d, 'No').click()
        QTimer.singleShot(30, elegir)
        resultado = MensajesIntegrados.question(self.ventana, 'Retirar acceso', '¿Continuar?')
        self.assertEqual(resultado, MensajesIntegrados.StandardButton.No)
        self.assertTrue(self.central.isEnabled())

    def test_selector_imagen_integrado(self):
        from dialogos import ArchivosIntegrados
        from PySide6.QtWidgets import QFileDialog
        def cancelar():
            d = next(d for d in self.ventana.findChildren(DialogoIntegrado) if d.isVisible())
            selector = d.findChild(QFileDialog)
            self.assertFalse(selector.isWindow())
            selector.reject()
        QTimer.singleShot(30, cancelar)
        self.assertEqual(ArchivosIntegrados.getOpenFileName(self.ventana, 'Imagen'), ('', ''))
        self.assertTrue(self.central.isEnabled())

    def test_revision_pedido_movil_integrada(self):
        from test_pedidos_table import TestPedidosTable
        from pedidos_table_ui import PaginaPedidosTable
        from PySide6.QtCore import QSettings
        from unittest.mock import patch
        fixture = TestPedidosTable()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.sesion.identificar = lambda u, p: None
        settings = QSettings(str(Path(fixture.temp.name) / 'ajustes.ini'), QSettings.Format.IniFormat)
        with patch('pedidos_table_ui.QSettings', wraps=QSettings) as fabrica:
            fabrica.return_value = settings
            fabrica.Status = QSettings.Status
            pagina = PaginaPedidosTable(fixture.sesion, fixture.turnos, lambda m, c: None, QPushButton(), self.ventana)
        pagina.temporizador.stop()
        pagina.reintento_conexion.stop()
        self.addCleanup(pagina.servidor.detener)
        identificador = pagina.solicitudes.enviar(fixture.datos())['id']
        pagina._mostrar_pedido(pagina.solicitudes.listar()[0])
        self.assertFalse(pagina.dialogo.isWindow())
        self.assertTrue(pagina.cubierta_pedido.isVisible())
        self.assertFalse(self.central.isEnabled())
        self.ventana.resize(900, 650)
        self.app.processEvents()
        self.assertEqual(pagina.cubierta_pedido.size(), self.ventana.size())
        pagina._resolver_identificador(identificador, False, desde_dialogo=True)
        self.assertTrue(self.central.isEnabled())
        self.assertFalse(pagina.cubierta_pedido.isVisible())
        self.assertEqual(pagina.solicitudes.estado(identificador)['estado'], 'rechazada')
        texto = pagina._lineas_productos([dict(nombre='Hamburguesa', categoria='Comidas', preparacion='Sin vegetales', acompanamiento='Yuca', extra='Yuca')])[0]
        self.assertIn('Sin vegetales', texto)
        self.assertIn('Extra: Yuca', texto)

    def test_sin_preparaciones_y_cancelar(self):
        def cancelar(d):
            self.assertEqual(d.findChild(QStackedWidget).count(), 1)
            next(b for b in d._cubierta_integrada.findChildren(QPushButton) if b.text() == 'Cancelar').click()
        self.assertIsNone(self.ejecutar(dict(nombre='Arroz', precio=2.5), cancelar))

if __name__ == '__main__':
    unittest.main()

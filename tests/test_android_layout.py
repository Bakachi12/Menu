"""Responsive layouts using the real Qt Designer forms at phone/tablet sizes."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QStackedWidget,QLabel,QSplitter,QListWidget,QPushButton
from PySide6.QtCore import Qt
from vista_pedidos import cargar_pantalla
from interfaz_adaptable import InterfazAdaptable,medidas_dialogo

class AndroidLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.env=patch.dict(os.environ,{'MENU_ANDROID_TEST':'1'});self.env.start()
        root=Path(__file__).resolve().parents[1]
        self.w=cargar_pantalla(root,'inicio.ui')
        self.pages=self.w.findChild(QStackedWidget,'PaginasPrincipal')
        inicio=QWidget();layout=QVBoxLayout(inicio);self.pages.addWidget(inicio)
        panel=self.w.findChild(QWidget,'PanelLateral')
        self.adapter=InterfazAdaptable(self.w,self.pages,inicio,layout,panel,QLabel('Pedidos'))
        self.order=cargar_pantalla(root,'pedido.ui');self.pages.addWidget(self.order);self.pages.setCurrentWidget(self.order)
        self.w.show()

    def tearDown(self):
        self.adapter.temporizador.stop();self.w.close();self.w.deleteLater();self.app.processEvents();self.env.stop()

    def resize(self,w,h):
        self.w.resize(w,h);self.app.processEvents();self.adapter.aplicar();self.app.processEvents()
        self.assertLessEqual(self.w.width(),w)
        self.assertLessEqual(self.w.height(),h)

    def test_menu_returns_from_orders_and_reserves_navigation_height(self):
        self.resize(412,915)
        boton=next(b for b in self.adapter.panel.findChildren(QPushButton) if b.text()=='Inicio')
        boton.clicked.connect(lambda: self.pages.setCurrentWidget(self.adapter.inicio))
        boton.show()
        self.adapter.aplicar()
        self.assertGreaterEqual(self.adapter.panel.minimumHeight(),164)
        self.assertTrue(self.adapter.menu.isVisible())
        self.adapter.menu.click()
        self.assertIs(self.pages.currentWidget(),self.adapter.inicio)

    def test_phone_portrait_keeps_products_and_compact_summary(self):
        self.resize(412,915)
        self.assertTrue(self.adapter.en_inicio)
        self.assertEqual(self.order.findChild(QSplitter,'splitter').orientation(),Qt.Orientation.Vertical)
        self.assertTrue(self.order.findChild(QListWidget,'Listapedido').isHidden())
        width,height=medidas_dialogo(self.w,1100,850)
        self.assertLess(width,412);self.assertLessEqual(height,899)

    def test_phone_landscape_and_large_tablet_restore_full_account(self):
        self.resize(915,412)
        self.assertTrue(self.adapter.en_inicio)
        self.assertEqual(self.order.findChild(QSplitter,'splitter').orientation(),Qt.Orientation.Horizontal)
        self.resize(1280,800)
        self.assertFalse(self.adapter.en_inicio)
        self.assertFalse(self.order.findChild(QListWidget,'Listapedido').isHidden())

if __name__=='__main__':unittest.main()

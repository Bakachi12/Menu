import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QPushButton,QScrollArea
from contenido_adaptable import adaptar_contenido
from clientes_ficha import editar_ficha
from dialogos import DialogoIntegrado

class ContenidoAndroidTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_customer_form_fills_landscape_and_keeps_save_visible(self):
        class Gestion:
            def obtener(self,identificador):return dict(nombre='Cliente',correo='',telefono='',notas='',frecuente=False)
        with patch.dict(os.environ,{'MENU_ANDROID_TEST':'1'}):
            ventana=QMainWindow();ventana.setCentralWidget(QWidget());ventana.resize(800,360);ventana.show()
            errores=[]
            def revisar():
                try:
                    self.app.processEvents()
                    tarjeta=ventana.findChild(QWidget,'TarjetaFormulario')
                    self.assertGreaterEqual(tarjeta.width(),780)
                    self.assertLessEqual(tarjeta.height(),344)
                    area=next(a for a in tarjeta.findChildren(QScrollArea) if a.isVisible())
                    self.assertEqual(area.verticalScrollBar().maximum(),0)
                    guardar=next(b for b in tarjeta.findChildren(QPushButton) if b.text()=='Guardar cliente')
                    self.assertTrue(area.viewport().rect().contains(guardar.mapTo(area.viewport(),guardar.rect().bottomRight())))
                except BaseException as error:errores.append(error)
                finally:ventana.findChild(DialogoIntegrado).reject()
            QTimer.singleShot(50,revisar)
            editar_ficha(ventana,Gestion(),1)
            ventana.close();ventana.deleteLater();self.app.processEvents()
            if errores:raise errores[0]

    def test_desktop_controls_keep_their_original_sizes(self):
        ventana=QWidget();layout=QVBoxLayout(ventana);boton=QPushButton('Guardar');boton.setMinimumHeight(68);layout.addWidget(boton)
        estilo='QPushButton {font-size:22px; padding:14px;}';boton.setStyleSheet(estilo)
        with patch('interfaz_adaptable.es_android',return_value=False):adaptar_contenido(ventana,800,360)
        self.assertEqual(boton.minimumHeight(),68)
        self.assertEqual(boton.styleSheet(),estilo)
        ventana.deleteLater();self.app.processEvents()

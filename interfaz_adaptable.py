"""Responsive Qt layouts for phones, tablets and desktop windows."""
import os,sys
from PySide6.QtCore import QObject,QTimer,Qt
from PySide6.QtWidgets import (QApplication,QWidget,QScrollArea,QVBoxLayout,QLayout,
                             QSizePolicy,QSplitter,QListWidget,QLabel,QPushButton)
from shiboken6 import isValid

def es_android():
    return sys.platform=='android' or 'ANDROID_ARGUMENT' in os.environ or os.environ.get('MENU_ANDROID_TEST')=='1'

def medidas_dialogo(ventana,ancho=660,alto=620):
    margen=8 if es_android() else 24
    return min(ancho,max(160,ventana.width()-2*margen)),min(alto,max(160,ventana.height()-2*margen))

def hacer_acceso_desplazable(acceso):
    if not es_android():return
    contenido=QWidget();contenido.setLayout(acceso.distribucion)
    acceso.distribucion.setContentsMargins(12,8,12,8)
    area=QScrollArea();area.setWidgetResizable(True);area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setStyleSheet('QScrollArea { border: none; background: transparent; }')
    area.setWidget(contenido)
    root=QVBoxLayout(acceso);root.setContentsMargins(0,0,0,0);root.addWidget(area)
    acceso.tarjeta.layout().setContentsMargins(16,14,16,14)

class InterfazAdaptable(QObject):
    def __init__(self,ventana,paginas,inicio,layout_inicio,panel,titulo):
        super().__init__(ventana)
        self.ventana,self.paginas,self.inicio=ventana,paginas,inicio
        self.layout_inicio,self.panel=layout_inicio,panel
        self.original=panel.parentWidget().layout();self.indice=self.original.indexOf(panel)
        self.en_inicio=False;self.ultimo=None;self.pedidos={};self.estilos_inicio={}
        self.ventana.centralWidget().layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        titulo.setMinimumWidth(0);titulo.setWordWrap(True)
        titulo.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.temporizador=QTimer(self);self.temporizador.setInterval(250)
        self.temporizador.timeout.connect(self.aplicar)
        QApplication.instance().aboutToQuit.connect(self.temporizador.stop)
        self.aplicar();self.temporizador.start()

    def aplicar(self):
        if not isValid(self.ventana):return
        w,h=self.ventana.width(),self.ventana.height()
        telefono=w<760 or h<500
        if telefono!=self.ultimo:
            self.ultimo=telefono
            for boton in self.inicio.findChildren(QPushButton):
                if boton not in self.estilos_inicio:
                    self.estilos_inicio[boton]=(boton.styleSheet(),boton.text())
                estilo,texto=self.estilos_inicio[boton]
                if telefono:
                    if texto.startswith('Cuentas abiertas'):boton.setText('Cuentas abiertas\nMesas y clientes')
                    elif texto.startswith('Barra\n'):boton.setText('Barra\nCuentas individuales')
                    boton.setStyleSheet(estilo+'QPushButton { font-size: 16px; padding: 10px; min-height: 44px; }')
                else:
                    boton.setStyleSheet(estilo);boton.setText(texto)
            if telefono and not self.en_inicio:
                visible=self.panel.isVisible()
                self.original.removeWidget(self.panel)
                self.panel.setMinimumWidth(0);self.panel.setMaximumWidth(16777215)
                self.layout_inicio.insertWidget(1,self.panel)
                self.panel.setVisible(visible);self.en_inicio=True
            elif not telefono and self.en_inicio:
                visible=self.panel.isVisible();self.layout_inicio.removeWidget(self.panel)
                self.panel.setMinimumWidth(200);self.panel.setMaximumWidth(250)
                self.original.insertWidget(self.indice,self.panel)
                self.panel.setVisible(visible);self.en_inicio=False
            self.ventana.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
            self.paginas.setMinimumSize(0,0)
            for i in range(self.paginas.count()):
                pagina=self.paginas.widget(i)
                pagina.setMinimumSize(0,0)
                pagina.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Ignored)
                if pagina.layout():pagina.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        for splitter in self.ventana.findChildren(QSplitter,'splitter'):
            clave=(telefono,w>h)
            if self.pedidos.get(splitter)==clave:continue
            self.pedidos[splitter]=clave
            cuenta=splitter.widget(1)
            lista=cuenta.findChild(QListWidget,'Listapedido')
            etiqueta=cuenta.findChild(QLabel,'lblMesa')
            cuenta.setMinimumWidth(0 if telefono else 320)
            cuenta.setMaximumHeight(210 if telefono and h>w else 16777215)
            if lista:lista.setVisible(not telefono)
            if etiqueta:etiqueta.setVisible(not telefono)
            splitter.setOrientation(Qt.Orientation.Vertical if telefono and h>w else Qt.Orientation.Horizontal)
            splitter.setSizes([max(200,h-260),200] if telefono and h>w else [max(200,w-230),210] if telefono else [1200,400])

def instalar(ventana,paginas,inicio,layout_inicio,panel,titulo):
    if es_android():
        return InterfazAdaptable(ventana,paginas,inicio,layout_inicio,panel,titulo)

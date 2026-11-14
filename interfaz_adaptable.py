"""Responsive Qt layouts for phones, tablets and desktop windows."""
import os,sys
from PySide6.QtCore import QObject,QTimer,Qt,QSysInfo
from PySide6.QtWidgets import (QApplication,QWidget,QScrollArea,QVBoxLayout,QLayout,
                             QSizePolicy,QSplitter,QListWidget,QLabel,QPushButton,QGridLayout)
from shiboken6 import isValid

def es_android():
    return (sys.platform=='android' or hasattr(sys,'getandroidapilevel')
            or QSysInfo.productType()=='android' or 'ANDROID_ARGUMENT' in os.environ
            or os.environ.get('MENU_ANDROID_TEST')=='1')

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
    def __init__(self,ventana,paginas,inicio,layout_inicio,panel,titulo,cabecera=None):
        super().__init__(ventana)
        self.ventana,self.paginas,self.inicio=ventana,paginas,inicio
        self.layout_inicio,self.panel=layout_inicio,panel
        self.original=panel.parentWidget().layout();self.indice=self.original.indexOf(panel)
        self.navegacion=QWidget()
        self.navegacion.setObjectName('NavegacionMovil')
        self.rejilla=QGridLayout(self.navegacion)
        self.rejilla.setContentsMargins(0,0,0,0);self.rejilla.setSpacing(8)
        self.layout_inicio.insertWidget(1,self.navegacion)
        self.navegacion.hide();self.copias={}
        self.en_inicio=False;self.ultimo=None;self.pedidos={};self.estilos_inicio={}
        self.ventana.centralWidget().layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        titulo.setMinimumWidth(0);titulo.setWordWrap(True)
        titulo.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        # A phone must always expose a way back to the complete navigation.
        self.menu=QPushButton('Menú',ventana)
        self.menu.setObjectName('btnMenuAndroid')
        self.menu.setFixedSize(72,44)
        self.menu.clicked.connect(self.abrir_menu)
        def fila_de(layout):
            if layout.indexOf(titulo)>=0:return layout
            for i in range(layout.count()):
                hijo=layout.itemAt(i).layout()
                if hijo:
                    encontrado=fila_de(hijo)
                    if encontrado:return encontrado
        fila=fila_de(ventana.centralWidget().layout())
        (cabecera or fila or ventana.centralWidget().layout()).insertWidget(0,self.menu)
        self.temporizador=QTimer(self);self.temporizador.setInterval(250)
        self.temporizador.timeout.connect(self.aplicar)
        QApplication.instance().aboutToQuit.connect(self.temporizador.stop)
        self.aplicar();self.temporizador.start()

    def abrir_menu(self):
        for boton in self.panel.findChildren(QPushButton):
            if boton.text()=='Inicio' and boton.isEnabled():
                boton.click()
                return
        self.paginas.setCurrentWidget(self.inicio)

    def aplicar(self):
        if not isValid(self.ventana):return
        w,h=self.ventana.width(),self.ventana.height()
        telefono=w<760 or h<500
        self.menu.setVisible(self.paginas.isEnabled())
        # One scroll surface, rather than a scrollable sidebar inside Inicio.
        self.navegacion.setVisible(telefono)
        if telefono:self.panel.hide()
        visibles=[]
        for original in self.panel.findChildren(QPushButton):
            if original not in self.copias:
                copia=QPushButton(self.navegacion)
                copia.setMinimumWidth(0)
                copia.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
                copia.setFixedHeight(48)
                copia.setStyleSheet('QPushButton {font-size:14px; padding:6px; min-height:0; border:1px solid #23d7f4; background:#11283f; color:#eaf3ff; border-radius:9px;} QPushButton:pressed {background:#1b4263;}')
                copia.clicked.connect(lambda checked=False,b=original:b.click())
                self.copias[original]=copia
            copia=self.copias[original]
            copia.setText(original.text());copia.setEnabled(original.isEnabled())
            copia.setVisible(not original.isHidden())
            if not original.isHidden():visibles.append(copia)
        for i,copia in enumerate(visibles):self.rejilla.addWidget(copia,i//2,i%2)
        self.navegacion.setFixedHeight(((len(visibles)+1)//2)*56)
        if telefono!=self.ultimo:
            self.ultimo=telefono
            for boton in self.inicio.findChildren(QPushButton):
                if boton not in self.estilos_inicio:
                    self.estilos_inicio[boton]=(boton.styleSheet(),boton.text())
                estilo,texto=self.estilos_inicio[boton]
                if telefono:
                    if texto.startswith('Cuentas abiertas'):boton.setText('Cuentas abiertas\nMesas y clientes')
                    elif texto.startswith('Barra\n'):boton.setText('Barra\nCuentas individuales')
                    boton.setStyleSheet(estilo+'QPushButton { font-size: 14px; padding: 6px; min-height: 32px; }')
                else:
                    boton.setStyleSheet(estilo);boton.setText(texto)
            self.en_inicio=telefono
            if not telefono:
                self.panel.setVisible(self.paginas.currentWidget() is self.inicio)
            self.layout_inicio.setContentsMargins(10 if telefono else 28,10 if telefono else 28,10 if telefono else 28,10 if telefono else 28)
            self.layout_inicio.setSpacing(10 if telefono else 18)
            # All outer mobile pages fit the viewport width; vertical scrolling
            # remains available for long forms without sideways panning.
            for area in self.ventana.findChildren(QScrollArea):
                if area.widget() and telefono:
                    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    area.widget().setMinimumWidth(0)
                    area.widget().setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
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

def instalar(ventana,paginas,inicio,layout_inicio,panel,titulo,cabecera=None):
    if es_android():
        return InterfazAdaptable(ventana,paginas,inicio,layout_inicio,panel,titulo,cabecera)

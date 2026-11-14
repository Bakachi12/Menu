"""Shared compact sizing for Android pages and integrated forms."""
import re
from weakref import WeakKeyDictionary
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QPushButton,QLabel,QLineEdit,QComboBox,
    QAbstractSpinBox,QAbstractScrollArea,QScrollArea,QCheckBox,QLayout,QSizePolicy,QScroller)

_estados=WeakKeyDictionary()

def _estilo_compacto(texto):
    texto=re.sub(r'font-size\s*:\s*(\d+(?:\.\d+)?)px',lambda m:f'font-size:{min(float(m[1]),18):g}px',texto)
    texto=re.sub(r'padding\s*:\s*([^;{}]+)',lambda m:'padding:'+re.sub(r'(\d+(?:\.\d+)?)px',lambda n:f'{min(float(n[1]),6):g}px',m[1]),texto)
    return texto

def adaptar_contenido(raiz,ancho=None,alto=None):
    from interfaz_adaptable import es_android
    if not es_android():return
    ventana=raiz.window()
    ancho=ancho or ventana.width();alto=alto or ventana.height()
    compacto=alto<650 or ancho<1000
    widgets=[raiz]+raiz.findChildren(QWidget)
    for widget in widgets:
        if widget.property('ayudaCompacta'):widget.setVisible(not compacto)
        if isinstance(widget,QLineEdit) and isinstance(widget.parentWidget(),QAbstractSpinBox):continue
        if widget.property('vistaPreviaProducto'):
            foto=widget.pixmap()
            widget.setVisible(not compacto or (foto is not None and not foto.isNull()))
        if isinstance(widget,QLabel) and (widget.pixmap() is None or widget.pixmap().isNull()):
            if not widget.text() and not widget.isHidden():widget.setProperty('androidMensajeVacio',True)
            if widget.property('androidMensajeVacio'):widget.setVisible(bool(widget.text()))
        actual=widget.styleSheet()
        estado=_estados.get(widget)
        if estado is None:
            estado=dict(estilo=actual,aplicado=None,minimo=widget.minimumSize(),maximo=widget.maximumSize(),compacto=None)
            _estados[widget]=estado
        elif actual!=estado['aplicado'] and actual!=estado['estilo']:
            estado['estilo']=actual;estado['compacto']=None
        if estado['compacto']==compacto:continue
        estado['compacto']=compacto
        if not compacto:
            widget.setMinimumSize(estado['minimo']);widget.setMaximumSize(estado['maximo'])
            widget.setStyleSheet(estado['estilo']);estado['aplicado']=widget.styleSheet()
            continue
        estilo=_estilo_compacto(estado['estilo'])
        if isinstance(widget,QPushButton) and widget.layout() is None:
            lineas=widget.text().count('\n')+1
            altura=max(36,lineas*16+12)
            widget.setMinimumWidth(0);widget.setFixedHeight(altura)
            estilo+=f'QPushButton {{font-size:14px; min-height:{altura-14}px; max-height:{altura-14}px; padding:6px 8px;}}'
        elif isinstance(widget,(QLineEdit,QComboBox,QAbstractSpinBox)):
            widget.setMinimumWidth(0);widget.setFixedHeight(34)
            estilo+='QLineEdit,QComboBox,QAbstractSpinBox {font-size:14px; min-height:20px; max-height:20px; padding:5px 6px;}'
        elif isinstance(widget,QLabel):
            foto=widget.pixmap()
            if widget.property('vistaPreviaProducto'):
                widget.setFixedHeight(48)
            elif foto is None or foto.isNull():
                fuente=18 if re.search(r'font-size\s*:\s*(?:2[0-9]|[3-9][0-9])',estado['estilo']) else 14
                estilo+=f'QLabel {{font-size:{fuente}px;}}'
                widget.setMinimumWidth(0)
                if widget.minimumHeight()>30:widget.setMinimumHeight(0)
        elif isinstance(widget,QCheckBox):
            widget.setMinimumWidth(0)
            estilo+='QCheckBox {font-size:13px; padding:3px; min-height:24px;}'
        elif isinstance(widget,QAbstractScrollArea):
            QScroller.ungrabGesture(widget.viewport())
            widget.setMinimumHeight(0)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Ignored)
            if isinstance(widget,QScrollArea):
                estilo+='QScrollArea {background:#101b2e; border:none;} QScrollArea > QWidget {background:#101b2e;}'
                widget.viewport().setAutoFillBackground(False)
                if widget.widget():widget.widget().setAutoFillBackground(False)
                widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        elif widget.minimumWidth()>ancho//2 and widget.objectName() not in ('TarjetaFormulario','CubiertaFormulario'):
            widget.setMinimumWidth(0)
        widget.setStyleSheet(estilo);estado['aplicado']=widget.styleSheet()
    if compacto:
        for widget in widgets:
            layout=widget.layout()
            if layout:_compactar_layout(layout)

def _compactar_layout(layout):
    m=layout.contentsMargins()
    layout.setContentsMargins(*(min(8,v) for v in (m.left(),m.top(),m.right(),m.bottom())))
    if layout.spacing()<0 or layout.spacing()>6:layout.setSpacing(6)
    for i in range(layout.count()):
        hijo=layout.itemAt(i).layout()
        if hijo:_compactar_layout(hijo)

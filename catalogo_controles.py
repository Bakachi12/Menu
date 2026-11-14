"""Controles táctiles para clasificar y filtrar productos."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QButtonGroup, QPushButton
from cocina import BEBIDAS, COCINA, ACOMPANAMIENTO


class SelectorCategoria(QWidget):
    cambiado = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grupo = QButtonGroup(self)
        self.botones = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for nombre, valor in [('Bebida', BEBIDAS), ('Plato', COCINA), ('Acompañamiento', ACOMPANAMIENTO)]:
            boton = QPushButton(nombre)
            boton.setCheckable(True)
            boton.setMinimumHeight(52)
            boton.setProperty('selectorProducto', True)
            self.grupo.addButton(boton)
            self.botones[valor] = boton
            layout.addWidget(boton)
            boton.clicked.connect(lambda checked=False, v=valor: self.cambiado.emit(v))
        self.botones[BEBIDAS].setChecked(True)

    def text(self):
        return next(valor for valor, boton in self.botones.items() if boton.isChecked())

    def setText(self, valor):
        if valor in self.botones:
            self.botones[valor].setChecked(True)

    def clear(self):
        # Conservar la categoría permite añadir varios productos seguidos.
        pass


def pertenece_menu(seccion, menu):
    return seccion == menu


ESTILO_SELECTORES = '''
QWidget#PaginaProductos QPushButton[selectorProducto="true"] {
    background: #101e34; color: #bbccc4; border: 1px solid #52685e;
    font-size: 16px; padding: 10px;
}
QWidget#PaginaProductos QPushButton[selectorProducto="true"]:checked {
    background: #28d8f7; color: #071725; border: 2px solid #85f0ff;
}
QWidget#PaginaProductos QListWidget::item { min-height: 48px; padding: 10px 14px; }
QWidget#PaginaProductos QListWidget::item:selected { background: #31594a; color: #85f0ff; }
'''

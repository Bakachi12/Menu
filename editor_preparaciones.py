"""Editor de opciones de preparación, sin separadores escritos a mano."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QDoubleSpinBox
from cocina import opciones, preparaciones_con_recargo
import json


class EditorPreparaciones(QWidget):
    def __init__(self, texto='', parent=None):
        super().__init__(parent)
        self.filas = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        ayuda = QLabel('Agrega cada preparación y su recargo. Ejemplo: Sin vegetales + B/. 0.00 o Extra queso + B/. 0.40. Elige una opción al pedir.')
        ayuda.setWordWrap(True)
        ayuda.setProperty("ayudaCompacta",True)
        layout.addWidget(ayuda)
        self.lista = QVBoxLayout()
        self.lista.setSpacing(8)
        layout.addLayout(self.lista)
        agregar = QPushButton('+ Agregar preparación')
        agregar.clicked.connect(lambda: self.agregar())
        layout.addWidget(agregar)
        for valor, cargo in preparaciones_con_recargo(texto).items():
            self.agregar(valor, enfocar=False, centimos=cargo)

    def agregar(self, valor='', enfocar=True, centimos=0):
        fila = QWidget()
        layout = QHBoxLayout(fila)
        layout.setContentsMargins(0, 0, 0, 0)
        campo = QLineEdit(valor)
        campo.setPlaceholderText('Ejemplo: Al ajillo')
        campo.setAccessibleName('Nombre de la preparación')
        precio = QDoubleSpinBox()
        precio.setRange(0, 99999.99)
        precio.setDecimals(2)
        precio.setSingleStep(0.10)
        precio.setPrefix('+ B/. ')
        precio.setValue(centimos / 100)
        precio.setAccessibleName('Recargo de la preparación; cero significa sin recargo')
        quitar = QPushButton('Quitar')
        layout.addWidget(campo, 1)
        layout.addWidget(precio)
        layout.addWidget(quitar)
        self.lista.addWidget(fila)
        self.filas.append((fila, campo, precio))
        quitar.clicked.connect(lambda: self.quitar(fila))
        if enfocar:
            campo.setFocus()

    def quitar(self, fila):
        self.filas = [(widget, campo, precio) for widget, campo, precio in self.filas if widget is not fila]
        self.lista.removeWidget(fila)
        fila.hide()
        fila.deleteLater()

    def text(self):
        valores = {}
        for _, campo, precio in self.filas:
            nombre = campo.text().strip()
            if nombre:
                valores[nombre] = round(precio.value() * 100)
        return json.dumps([dict(nombre=n, centimos=c) for n, c in valores.items()], ensure_ascii=False)

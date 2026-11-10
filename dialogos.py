"""Cuadros integrados en la ventana del restaurante."""
from PySide6.QtCore import QEvent, QEventLoop, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)
from shiboken6 import isValid


class EditorNombreMesa(QWidget):
    def __init__(self, ventana):
        super().__init__(ventana)
        self.ventana = ventana
        self.bucle = QEventLoop(self)
        self.aceptado = False
        self.setObjectName('EditorNombreMesa')
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet('''
            QWidget#TarjetaNombreMesa { background: #111D2F; border: 1px solid #465064; border-radius: 20px; }
            QLabel { color: #C1CDDF; background: transparent; border: none; font-size: 14px; }
            QLineEdit { background: #0B1525; color: #F4F2ED; border: 1px solid #34445E;
                border-radius: 9px; padding: 13px; font-size: 17px; }
            QLineEdit:focus { border: 1px solid #D6AE62; }
            QPushButton { background: #D6AE62; color: #101725; border: none;
                border-radius: 9px; padding: 14px; font-size: 16px; }
            QPushButton:hover { background: #F2C66D; }
            QPushButton#CancelarNombre { background: #233249; color: #E2E8F0; }
            QPushButton#CancelarNombre:hover { background: #34465F; }
        ''')
        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(24, 24, 24, 24)
        exterior.addStretch()
        tarjeta = QWidget()
        tarjeta.setObjectName('TarjetaNombreMesa')
        tarjeta.setMaximumWidth(460)
        sombra = QGraphicsDropShadowEffect(tarjeta)
        sombra.setBlurRadius(40)
        sombra.setOffset(0, 12)
        sombra.setColor(QColor(0, 0, 0, 120))
        tarjeta.setGraphicsEffect(sombra)
        interior = QVBoxLayout(tarjeta)
        interior.setContentsMargins(28, 28, 28, 28)
        interior.setSpacing(14)
        self.mesa = QLabel()
        self.mesa.setWordWrap(True)
        self.mesa.setTextFormat(Qt.TextFormat.PlainText)
        self.mesa.setStyleSheet('color: #D6AE62; font-size: 13px;')
        interior.addWidget(self.mesa)
        titulo = QLabel('Nombre de la mesa')
        self.titulo = titulo
        titulo.setStyleSheet('color: #F3E1BF; font-size: 25px;')
        titulo.setWordWrap(True)
        interior.addWidget(titulo)
        descripcion = QLabel('Añade el nombre del cliente o una referencia para reconocer este pedido.')
        self.descripcion = descripcion
        descripcion.setWordWrap(True)
        interior.addWidget(descripcion)
        self.campo = QLineEdit()
        self.campo.setPlaceholderText('Ejemplo: Familia Pérez')
        self.campo.returnPressed.connect(self.guardar)
        interior.addWidget(self.campo)
        ayuda = QLabel('Déjalo vacío para quitar el nombre asignado.')
        self.ayuda = ayuda
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet('color: #8FA0B9; font-size: 12px;')
        interior.addWidget(ayuda)
        botones = QHBoxLayout()
        self.cancelar_boton = QPushButton('Cancelar')
        self.cancelar_boton.setObjectName('CancelarNombre')
        self.cancelar_boton.clicked.connect(self.cancelar)
        self.guardar_boton = QPushButton('Guardar nombre')
        self.guardar_boton.clicked.connect(self.guardar)
        botones.addWidget(self.cancelar_boton)
        botones.addWidget(self.guardar_boton)
        interior.addLayout(botones)
        fila = QHBoxLayout()
        fila.addStretch(1)
        fila.addWidget(tarjeta, 10)
        fila.addStretch(1)
        exterior.addLayout(fila)
        exterior.addStretch()
        self.hide()

    def solicitar(self, mesa, nombre_actual):
        self.aceptado = False
        self.mesa.setText(mesa)
        self.campo.setText(nombre_actual)
        contenido = self.ventana.centralWidget()
        habilitado = contenido.isEnabled()
        foco = QApplication.focusWidget()
        estado_anterior = self.ventana.property('dialogoEnCurso')
        self.ventana.setProperty('dialogoEnCurso', True)
        contenido.setEnabled(False)
        self.ventana.installEventFilter(self)
        app = QApplication.instance()
        app.aboutToQuit.connect(self.cancelar)
        self.setGeometry(self.ventana.rect())
        self.show()
        self.raise_()
        self.campo.setFocus()
        self.campo.selectAll()
        try:
            self.bucle.exec()
            return self.campo.text(), self.aceptado
        finally:
            self.hide()
            self.ventana.removeEventFilter(self)
            self.ventana.setProperty('dialogoEnCurso', estado_anterior)
            contenido.setEnabled(habilitado)
            if foco is not None and isValid(foco) and foco.isVisible():
                foco.setFocus()
            app.aboutToQuit.disconnect(self.cancelar)

    def guardar(self):
        self.aceptado = True
        self.bucle.quit()

    def cancelar(self):
        self.aceptado = False
        self.bucle.quit()

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key.Key_Escape:
            self.cancelar()
        evento.accept()

    def eventFilter(self, objeto, evento):
        if objeto is self.ventana:
            if evento.type() == QEvent.Type.Resize:
                self.setGeometry(self.ventana.rect())
                self.raise_()
            elif evento.type() == QEvent.Type.Close:
                self.cancelar()
        return False

    def paintEvent(self, evento):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(3, 8, 17, 195))


class EditorNombreCliente(EditorNombreMesa):
    def __init__(self, ventana, gestion):
        super().__init__(ventana)
        self.gestion = gestion
        self.identificador = None
        self.setObjectName('EditorNombreCliente')
        self.titulo.setText('Agregar cliente')
        self.descripcion.setText('Escribe su nombre. Después toca la mesa donde se sentará.')
        self.campo.setPlaceholderText('Nombre del cliente')
        self.campo.setMaxLength(80)
        self.campo.setMinimumHeight(56)
        self.guardar_boton.setText('Elegir mesa')
        self.guardar_boton.setMinimumHeight(56)
        self.cancelar_boton.setMinimumHeight(56)

    def solicitar_cliente(self):
        self.identificador = None
        self.ayuda.setText('')
        self.ayuda.setStyleSheet('color: #FFAEAE; font-size: 14px;')
        _, aceptado = self.solicitar('CLIENTES', '')
        return self.identificador if aceptado else None

    def guardar(self):
        import sqlite3
        self.guardar_boton.setEnabled(False)
        try:
            self.identificador = self.gestion.crear(self.campo.text(), None)
            super().guardar()
        except (ValueError, PermissionError) as error:
            self.ayuda.setText(str(error))
            self.campo.setFocus()
        except sqlite3.Error:
            self.ayuda.setText('No se pudo guardar el cliente. Inténtalo de nuevo.')
        finally:
            self.guardar_boton.setEnabled(True)

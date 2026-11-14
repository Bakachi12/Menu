"""Cuadros integrados en la ventana del restaurante."""
from PySide6.QtCore import QEvent, QEventLoop, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)
from shiboken6 import isValid
from PySide6.QtWidgets import QDialog, QScrollArea


class FondoFormulario(QWidget):
    def paintEvent(self, evento):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(3, 8, 17, 155))


class DialogoIntegrado(QDialog):
    """Formulario alojado dentro de la ventana principal, sin ventana nativa."""

    def exec(self):
        ventana = self.parentWidget().window()
        compacto = bool(self.property('compacto'))
        cubierta = FondoFormulario(ventana) if compacto else QWidget(ventana)
        cubierta.setObjectName('CubiertaFormulario')
        if not compacto:
            cubierta.setStyleSheet('QWidget#CubiertaFormulario { background: #101e1b; }')
        exterior = QVBoxLayout(cubierta)
        from interfaz_adaptable import es_android, medidas_dialogo
        margen = 8 if es_android() else 24
        exterior.setContentsMargins(margen, margen, margen, margen)
        tarjeta = QWidget()
        tarjeta.setObjectName('TarjetaFormulario')
        tarjeta.setStyleSheet('QWidget#TarjetaFormulario { background: #101b2e; border: 1px solid #287b99; border-radius: 18px; }')
        interior = QVBoxLayout(tarjeta)
        interior.setContentsMargins(12, 10, 12, 10) if es_android() else interior.setContentsMargins(22, 18, 22, 18)
        if compacto:
            tarjeta.setFixedSize(*medidas_dialogo(ventana,int(self.property('anchoCompacto') or 660),int(self.property('altoCompacto') or 620)))
            self._tarjeta_integrada = tarjeta
            sombra = QGraphicsDropShadowEffect(tarjeta)
            sombra.setBlurRadius(32)
            sombra.setOffset(0, 8)
            tarjeta.setGraphicsEffect(sombra)
            fila = QHBoxLayout()
            fila.addStretch()
            fila.addWidget(tarjeta)
            fila.addStretch()
            exterior.addStretch()
            exterior.addLayout(fila)
            exterior.addStretch()
        else:
            exterior.addWidget(tarjeta)
        cabecera = QHBoxLayout()
        titulo = QLabel(self.windowTitle())
        titulo.setTextFormat(Qt.TextFormat.PlainText)
        titulo.setStyleSheet('color: #23d7f4; font-size: 24px;')
        titulo.setWordWrap(True)
        cabecera.addWidget(titulo, 1)
        volver = QPushButton('Cancelar' if compacto else 'Volver')
        volver.setMinimumHeight(48)
        volver.setStyleSheet('QPushButton { background: #11283f; color: #eaf3ff; border: 1px solid #287b99; border-radius: 10px; padding: 10px 16px; font-size: 16px; }')
        volver.clicked.connect(self.reject)
        cabecera.addWidget(volver)
        interior.addLayout(cabecera)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        interior.addWidget(area)
        self.setParent(cubierta, Qt.WindowType.Widget)
        area.setWidget(self)
        bucle = QEventLoop()
        self.finished.connect(bucle.quit)
        app = QApplication.instance()
        app.aboutToQuit.connect(self.reject)
        contenido = ventana.centralWidget()
        habilitado = contenido.isEnabled()
        foco = QApplication.focusWidget()
        anterior = ventana.property('dialogoEnCurso')
        ventana.setProperty('dialogoEnCurso', True)
        contenido.setEnabled(False)
        self._ventana_integrada = ventana
        self._cubierta_integrada = cubierta
        ventana.installEventFilter(self)
        cubierta.setGeometry(ventana.rect())
        from contenido_adaptable import adaptar_contenido
        adaptar_contenido(cubierta,ventana.width(),ventana.height())
        self.setMinimumSize(0,0)
        cubierta.show()
        cubierta.raise_()
        self.show()
        self.setFocus()
        try:
            bucle.exec()
            return self.result()
        finally:
            ventana.removeEventFilter(self)
            ventana.setProperty('dialogoEnCurso', anterior)
            contenido.setEnabled(habilitado)
            cubierta.hide()
            if foco is not None and isValid(foco) and foco.isVisible():
                foco.setFocus()
            self.finished.disconnect(bucle.quit)
            app.aboutToQuit.disconnect(self.reject)
            area.takeWidget()
            self.setParent(ventana, Qt.WindowType.Widget)
            cubierta.deleteLater()

    def eventFilter(self, objeto, evento):
        if objeto is getattr(self, '_ventana_integrada', None):
            if evento.type() == QEvent.Type.Resize:
                self._cubierta_integrada.setGeometry(objeto.rect())
                if self.property('compacto'):
                    from interfaz_adaptable import medidas_dialogo
                    self._tarjeta_integrada.setFixedSize(*medidas_dialogo(objeto,int(self.property('anchoCompacto') or 660),int(self.property('altoCompacto') or 620)))
            elif evento.type() == QEvent.Type.Close:
                self.reject()
        return super().eventFilter(objeto, evento)


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
            QLineEdit { background: #0B1525; color: #eaf3ff; border: 1px solid #20354f;
                border-radius: 9px; padding: 13px; font-size: 17px; }
            QLineEdit:focus { border: 1px solid #23d7f4; }
            QPushButton { background: #23d7f4; color: #0b1425; border: none;
                border-radius: 9px; padding: 14px; font-size: 16px; }
            QPushButton:hover { background: #85eaff; }
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
        self.mesa.setStyleSheet('color: #23d7f4; font-size: 13px;')
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


class MensajesIntegrados:
    """Avisos y confirmaciones de la aplicación dentro de su ventana."""
    from PySide6.QtWidgets import QMessageBox as _Nativo
    StandardButton = _Nativo.StandardButton

    @classmethod
    def _mostrar(cls, parent, titulo, texto, botones=None, predeterminado=None):
        if parent is None or not hasattr(parent.window(), 'centralWidget'):
            return cls._Nativo.warning(parent, titulo, texto) if botones is None else cls._Nativo.question(parent, titulo, texto, botones)
        d = DialogoIntegrado(parent)
        d.setProperty('compacto', True)
        d.setWindowTitle(titulo)
        d.setStyleSheet('QWidget { background: #101b2e; color: #eaf3ff; } QPushButton { min-height: 48px; padding: 10px; background: #29473c; border: 1px solid #23d7f4; border-radius: 10px; }')
        layout = QVBoxLayout(d)
        mensaje = QLabel(texto)
        mensaje.setTextFormat(Qt.TextFormat.PlainText)
        mensaje.setWordWrap(True)
        layout.addWidget(mensaje)
        layout.addStretch()
        fila = QHBoxLayout()
        resultado = [cls.StandardButton.Cancel if botones else cls.StandardButton.Ok]
        elecciones = [(cls.StandardButton.Yes, 'Sí, continuar'), (cls.StandardButton.No, 'No'),
                      (cls.StandardButton.Ok, 'Aceptar'), (cls.StandardButton.Cancel, 'Cancelar')]
        botones = botones or cls.StandardButton.Ok
        for codigo, etiqueta in elecciones:
            if botones & codigo:
                boton = QPushButton(etiqueta)
                def elegir(checked=False, valor=codigo):
                    resultado[0] = valor
                    d.accept()
                boton.clicked.connect(elegir)
                fila.addWidget(boton)
        layout.addLayout(fila)
        d.exec()
        return resultado[0]

    @classmethod
    def warning(cls, parent, titulo, texto, *args):
        return cls._mostrar(parent, titulo, texto, *args)

    critical = warning
    information = warning

    @classmethod
    def question(cls, parent, titulo, texto, botones=None, predeterminado=None):
        return cls._mostrar(parent, titulo, texto, botones or (cls.StandardButton.Yes | cls.StandardButton.No), predeterminado)


class ArchivosIntegrados:
    @staticmethod
    def getOpenFileName(parent, titulo, directorio='', filtro=''):
        from PySide6.QtWidgets import QFileDialog
        d = DialogoIntegrado(parent)
        d.setWindowTitle(titulo)
        layout = QVBoxLayout(d)
        selector = QFileDialog(d, titulo, directorio, filtro)
        selector.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        selector.setFileMode(QFileDialog.FileMode.ExistingFile)
        selector.setWindowFlags(Qt.WindowType.Widget)
        layout.addWidget(selector)
        selector.accepted.connect(d.accept)
        selector.rejected.connect(d.reject)
        if d.exec() == QDialog.DialogCode.Accepted:
            archivos = selector.selectedFiles()
            return (archivos[0] if archivos else '', selector.selectedNameFilter())
        return '', ''

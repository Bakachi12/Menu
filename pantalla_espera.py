"""Pantalla de reposo del TPV; conserva la página y el pedido abiertos."""
from PySide6.QtCore import QDateTime, QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QKeySequence, QLinearGradient, QPainter, QPen, QShortcut
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from shiboken6 import isValid


class FondoEspera(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fondo = QLinearGradient(0, 0, self.width(), self.height())
        fondo.setColorAt(0, QColor("#080F1D"))
        fondo.setColorAt(0.6, QColor("#152237"))
        fondo.setColorAt(1, QColor("#0B1020"))
        painter.fillRect(self.rect(), fondo)
        painter.setPen(QPen(QColor(228, 189, 118, 22), 1))
        radio = max(self.width(), self.height()) // 2
        for extra in (0, 35, 70):
            painter.drawEllipse(self.width() - radio, -radio, (radio + extra) * 2, (radio + extra) * 2)
        painter.setPen(QPen(QColor(228, 189, 118, 65), 1))
        painter.drawRoundedRect(self.rect().adjusted(12, 12, -13, -13), 16, 16)


class PantallaEspera(FondoEspera):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("PantallaEspera")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QLabel { background: transparent; border: none; color: #F4F2ED; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        self.marca = self.etiqueta("R E S T A U R A N T E   &   B A R", 14, "#E4BD76")
        layout.addWidget(self.marca)
        layout.addStretch(2)
        layout.addWidget(self.etiqueta("U N A   P A U S A", 12, "#A8B4C8"))
        self.reloj = self.etiqueta("", 84, "#F4F2ED")
        layout.addWidget(self.reloj)
        self.fecha = self.etiqueta("", 16, "#A8B4C8")
        layout.addWidget(self.fecha)
        layout.addSpacing(18)
        separador = QWidget(self)
        separador.setFixedSize(100, 1)
        separador.setStyleSheet("background-color: #E4BD76;")
        layout.addWidget(separador, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(12)
        layout.addWidget(self.etiqueta("Todo listo para continuar", 24, "#F4F2ED"))
        layout.addWidget(self.etiqueta("Tus pedidos siguen donde los dejaste", 14, "#A8B4C8"))
        layout.addStretch(2)
        layout.addWidget(self.etiqueta("Toca la pantalla o pulsa una tecla", 15, "#E4BD76"))
        layout.addWidget(self.etiqueta("MODO DE ESPERA", 10, "#71819B"))
        self.actualizador = QTimer(self)
        self.actualizador.setInterval(1000)
        self.actualizador.timeout.connect(self.actualizar_reloj)
        self.hide()

    def etiqueta(self, texto, tamano, color):
        label = QLabel(texto, self)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        label.setStyleSheet(f"font-family: 'Segoe UI'; font-size: {tamano}px; color: {color}; font-weight: 300;")
        return label

    def actualizar_reloj(self):
        ahora = QDateTime.currentDateTime()
        dias = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
        meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
        fecha = ahora.date()
        self.reloj.setText(ahora.toString("HH:mm"))
        self.fecha.setText(f"{dias[fecha.dayOfWeek()-1].capitalize()}, {fecha.day()} de {meses[fecha.month()-1]}")

    def showEvent(self, event):
        self.actualizar_reloj()
        self.actualizador.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.actualizador.stop()
        super().hideEvent(event)

    def resizeEvent(self, event):
        tamano = max(40, min(84, self.height() // 8))
        self.reloj.setStyleSheet(f"font-family: 'Segoe UI'; font-size: {tamano}px; color: #F4F2ED; font-weight: 300;")
        super().resizeEvent(event)



class ControlEspera(QObject):
    """Dos minutos sin actividad; Ctrl+L permite entrar manualmente."""
    def __init__(self, ventana, segundos=120):
        super().__init__(ventana)
        self.ventana = ventana
        self.capa = PantallaEspera(ventana)
        self.foco_anterior = None
        self.tecla_despertar = None
        self.posicion_cursor = QCursor.pos()
        self.temporizador = QTimer(self)
        self.temporizador.setSingleShot(True)
        self.temporizador.setInterval(segundos * 1000)
        self.temporizador.timeout.connect(self.mostrar)
        self.raton = QTimer(self)
        self.raton.setInterval(250)
        self.raton.timeout.connect(self.comprobar_raton)
        self.raton.start()
        self.atajo = QShortcut(QKeySequence("Ctrl+L"), ventana)
        self.atajo.activated.connect(self.mostrar)
        QApplication.instance().installEventFilter(self)
        self.temporizador.start()

    def comprobar_raton(self):
        posicion = QCursor.pos()
        if posicion != self.posicion_cursor:
            self.posicion_cursor = posicion
            if (not self.capa.isVisible() and self.ventana.isActiveWindow()
                    and self.ventana.rect().contains(self.ventana.mapFromGlobal(posicion))):
                self.temporizador.start()

    def mostrar(self):
        if self.ventana.property('accesoEnCurso') or self.ventana.property('dialogoEnCurso'):
            self.temporizador.start()
            return
        # Nunca interrumpir un cobro, confirmación, selector o menú abierto.
        if (not self.ventana.isVisible() or self.ventana.isMinimized()
                or QApplication.activeModalWidget() or QApplication.activePopupWidget()):
            self.temporizador.start()
            return
        if self.capa.isVisible():
            return
        self.temporizador.stop()
        self.foco_anterior = QApplication.focusWidget()
        self.capa.setGeometry(self.ventana.rect())
        self.capa.show()
        self.capa.raise_()
        self.capa.setFocus()

    def continuar(self):
        self.capa.hide()
        if self.foco_anterior is not None:
            try:
                if self.foco_anterior.isVisible():
                    self.foco_anterior.setFocus()
            except RuntimeError:
                pass  # El widget pudo cerrarse mientras estaba en espera.
        self.temporizador.start()

    def eventFilter(self, objeto, evento):
        if not isValid(self.ventana):
            return False
        tipo = evento.type()
        if objeto is self.ventana and tipo == QEvent.Type.Resize:
            self.capa.setGeometry(self.ventana.rect())
        if not isinstance(objeto, QWidget) or not (objeto is self.ventana or self.ventana.isAncestorOf(objeto)):
            return False
        if self.capa.isVisible():
            if tipo == QEvent.Type.ShortcutOverride:
                evento.accept()
                return True
            # Despertar al soltar evita que el clic active un botón oculto.
            if tipo in (QEvent.Type.MouseButtonRelease, QEvent.Type.TouchEnd):
                self.continuar()
                return True
            if tipo == QEvent.Type.KeyPress:
                if not evento.isAutoRepeat():
                    self.tecla_despertar = evento.key()
                return True
            if tipo == QEvent.Type.KeyRelease:
                if not evento.isAutoRepeat() and evento.key() == self.tecla_despertar:
                    self.tecla_despertar = None
                    self.continuar()
                return True
            if tipo in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick,
                        QEvent.Type.Wheel, QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate):
                return True
        elif tipo in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove,
                      QEvent.Type.KeyPress, QEvent.Type.Wheel, QEvent.Type.TouchBegin,
                      QEvent.Type.TouchUpdate):
            self.temporizador.start()
        return False

"""Desplazamiento uniforme: dedo con inercia y arrastre con ratón."""
from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QAbstractScrollArea, QAbstractSlider,
    QComboBox, QLineEdit, QScroller, QScrollerProperties, QWidget,
)
from shiboken6 import isValid
from interfaz_adaptable import es_android


class DesplazamientoGlobal(QObject):
    def __init__(self, ventana):
        super().__init__(ventana)
        self.ventana = ventana
        self.area = None
        self.origen = None
        self.arrastrando = False
        self.reenviando = False
        self.origen_tactil = None
        self.deslizo_tactil = False
        for area in ventana.findChildren(QAbstractScrollArea):
            self.configurar(area)
        app = QApplication.instance()
        app.installEventFilter(self)
        app.aboutToQuit.connect(self.desactivar)

    def configurar(self, area):
        if area.property('arrastrePreparado'):
            return
        area.setProperty('arrastrePreparado', True)
        if isinstance(area, QAbstractItemView):
            area.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            area.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        superficie = area.viewport()
        # Android synthesizes mouse input for QWidget children. Let our single
        # drag handler own that sequence, including gestures starting on buttons.
        if not es_android():
            QScroller.grabGesture(superficie, QScroller.ScrollerGestureType.TouchGesture)
        desplazador = QScroller.scroller(superficie)
        propiedades = desplazador.scrollerProperties()
        propiedades.setScrollMetric(QScrollerProperties.ScrollMetric.VerticalOvershootPolicy,
                                   QScrollerProperties.OvershootPolicy.OvershootAlwaysOff)
        propiedades.setScrollMetric(QScrollerProperties.ScrollMetric.HorizontalOvershootPolicy,
                                   QScrollerProperties.OvershootPolicy.OvershootAlwaysOff)
        desplazador.setScrollerProperties(propiedades)
        desplazador.stateChanged.connect(self.estado_tactil)

    def estado_tactil(self, estado):
        if estado == QScroller.State.Dragging:
            self.deslizo_tactil = True
            if self.origen_tactil is not None and isValid(self.origen_tactil):
                self.cancelar_pulsacion(self.origen_tactil)

    def area_arrastrable(self, objeto):
        """Elegir el panel más cercano; respetar los campos y barras editables."""
        actual = objeto
        while isinstance(actual, QWidget) and actual is not self.ventana:
            if isinstance(actual, (QLineEdit, QComboBox, QAbstractSlider)):
                return None
            if isinstance(actual, QAbstractScrollArea):
                vertical = actual.verticalScrollBar()
                horizontal = actual.horizontalScrollBar()
                if vertical.maximum() > vertical.minimum() or horizontal.maximum() > horizontal.minimum():
                    return actual
            actual = actual.parentWidget()
        return None

    def limpiar(self):
        self.area = None
        self.origen = None
        self.arrastrando = False

    def desactivar(self):
        self.limpiar()
        QApplication.instance().removeEventFilter(self)

    def cancelar_pulsacion(self, objeto=None):
        # Qt también usa una liberación fuera del widget al reconocer un gesto.
        # Así el botón vuelve a su estado normal sin disparar clicked().
        destino = objeto if objeto is not None else self.origen
        if destino is not None and isValid(destino):
            fuera = QPoint(-10000, -10000)
            evento = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(fuera),
                                QPointF(destino.mapToGlobal(fuera)),
                                Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
                                Qt.KeyboardModifier.NoModifier)
            self.reenviando = True
            try:
                QApplication.sendEvent(destino, evento)
            finally:
                self.reenviando = False

    def eventFilter(self, objeto, evento):
        if self.reenviando or not isValid(self.ventana):
            return False
        tipo = evento.type()
        if tipo == QEvent.Type.Show and isinstance(objeto, QAbstractScrollArea):
            if self.ventana.isAncestorOf(objeto):
                self.configurar(objeto)
        if objeto is self.ventana and tipo in (QEvent.Type.WindowDeactivate, QEvent.Type.Close):
            if self.arrastrando:
                self.cancelar_pulsacion()
            self.limpiar()
        if tipo not in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease):
            return False
        # El gesto táctil nativo administra sus propios eventos sintetizados.
        if not es_android() and evento.source() != Qt.MouseEventSource.MouseEventNotSynthesized:
            if tipo == QEvent.Type.MouseButtonPress:
                self.origen_tactil = objeto
                self.deslizo_tactil = False
            elif tipo == QEvent.Type.MouseButtonRelease and self.deslizo_tactil:
                self.origen_tactil = None
                return True
            return False
        if tipo == QEvent.Type.MouseButtonPress:
            # Un clic en el fondo de QScrollArea se propaga a sus padres.
            # Conservar el destino original durante esa misma pulsación.
            if self.area is not None and isValid(self.area) and evento.globalPosition().toPoint() == self.inicio:
                return False
            self.limpiar()
            if (evento.button() != Qt.MouseButton.LeftButton or not isinstance(objeto, QWidget)
                    or not self.ventana.isAncestorOf(objeto) or not objeto.isEnabled()):
                return False
            self.area = self.area_arrastrable(objeto)
            if self.area is not None:
                self.origen = objeto
                self.inicio = evento.globalPosition().toPoint()
                self.inicio_vertical = self.area.verticalScrollBar().value()
                self.inicio_horizontal = self.area.horizontalScrollBar().value()
            return False
        if self.area is None or not isValid(self.area):
            self.limpiar()
            return False
        if tipo == QEvent.Type.MouseMove:
            if not evento.buttons() & Qt.MouseButton.LeftButton:
                self.limpiar()
                return False
            distancia = evento.globalPosition().toPoint() - self.inicio
            vertical = self.area.verticalScrollBar()
            horizontal = self.area.horizontalScrollBar()
            recorrido = max(abs(distancia.y()) if vertical.maximum() > vertical.minimum() else 0,
                            abs(distancia.x()) if horizontal.maximum() > horizontal.minimum() else 0)
            if not self.arrastrando and recorrido < QApplication.startDragDistance():
                return False
            if not self.arrastrando:
                self.arrastrando = True
                self.cancelar_pulsacion()
            vertical.setValue(self.inicio_vertical - distancia.y())
            horizontal.setValue(self.inicio_horizontal - distancia.x())
            return True
        if tipo == QEvent.Type.MouseButtonRelease and evento.button() == Qt.MouseButton.LeftButton:
            consumir = self.arrastrando
            self.limpiar()
            return consumir
        return False

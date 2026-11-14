"""Pantalla integrada para el personal de cocina."""
import sqlite3
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem
from cocina import platos_cocina, cambiar_disponibilidad
from estilos import FORMULARIOS


class PaginaCocina(QWidget):
    def __init__(self, sesion, salir):
        super().__init__()
        self.sesion = sesion
        self.disponibilidad = False
        self.setStyleSheet(FORMULARIOS + """
            QListWidget { background: #0b172b; color: #eaf3ff; border: 1px solid #285775; border-radius: 14px; font-size: 21px; }
            QListWidget::item { background: #11253d; border: 1px solid #285775; border-left: 4px solid #fa4cc7; border-radius: 10px; padding: 18px; margin: 5px; min-height: 85px; }
            QListWidget::item:selected { background: #193f5a; color: #9befff; border-color: #28d9f5; }
            QPushButton { background: #142c46; color: #9befff; border: 1px solid #28d9f5; border-radius: 12px; padding: 14px; font-size: 19px; min-height: 40px; }
            QPushButton:hover { background: #213956; border-color: #fa4cc7; }
        """)
        layout = QVBoxLayout(self)
        fila = QHBoxLayout()
        fila.addWidget(QLabel('Órdenes de cocina'), 1)
        self.modo = QPushButton('Disponibilidad de platos')
        self.modo.clicked.connect(self.cambiar_modo)
        fila.addWidget(self.modo)
        cerrar = QPushButton('Cerrar sesión')
        cerrar.clicked.connect(salir)
        fila.addWidget(cerrar)
        layout.addLayout(fila)
        self.lista = QListWidget()
        self.lista.setWordWrap(True)
        layout.addWidget(self.lista, 1)
        self.accion = QPushButton('Marcar orden lista')
        self.accion.setMinimumHeight(56)
        self.accion.clicked.connect(self.aplicar)
        layout.addWidget(self.accion)
        self.estado = QLabel()
        self.estado.setWordWrap(True)
        layout.addWidget(self.estado)
        self.temporizador = QTimer(self)
        self.temporizador.setInterval(2000)
        self.temporizador.timeout.connect(self.actualizar)
        self.temporizador.start()

    def autorizado(self):
        return bool(self.sesion.usuario and self.sesion.usuario.get('rol') in ('admin', 'cocinero'))

    def cambiar_modo(self):
        self.disponibilidad = not self.disponibilidad
        self.modo.setText('Volver a órdenes' if self.disponibilidad else 'Disponibilidad de platos')
        self.accion.setText('Cambiar disponibilidad' if self.disponibilidad else 'Marcar orden lista')
        self.actualizar()

    def actualizar(self):
        if not self.autorizado():
            self.lista.clear()
            return
        if not self.isVisible():
            return
        anterior = self.lista.currentItem()
        identificador = anterior.data(Qt.ItemDataRole.UserRole) if anterior else None
        self.lista.clear()
        try:
            with self.sesion.conexion() as db:
                if self.disponibilidad:
                    filas = [(p['id'], p['nombre'] + (' · Disponible' if p['disponible'] else ' · Agotado')) for p in platos_cocina(db)]
                else:
                    filas = [(i, f'#{i} · {mesa} · {cliente or "Cuenta general"}\n{plato}\n' +
                              ' · '.join(v for v in (preparacion, lado, 'Extra: ' + extra if extra else '') if v))
                             for i, mesa, cliente, plato, preparacion, lado, extra in db.execute(
                                 "SELECT id,mesa,cliente,plato,preparacion,acompanamiento,extra FROM ordenes_cocina WHERE estado='pendiente' ORDER BY id")]
            for i, texto in filas:
                item = QListWidgetItem(texto)
                item.setData(Qt.ItemDataRole.UserRole, i)
                self.lista.addItem(item)
                if i == identificador:
                    self.lista.setCurrentItem(item)
            self.estado.setText('Selecciona un plato.' if self.disponibilidad else f'{len(filas)} órdenes pendientes')
        except sqlite3.Error as error:
            self.estado.setText(f'No se pudo cargar cocina: {error}')

    def aplicar(self):
        if not self.autorizado():
            self.estado.setText('Solo Cocina o Admin pueden realizar esta acción.')
            return
        item = self.lista.currentItem()
        if item is None:
            self.estado.setText('Selecciona una orden o un plato.')
            return
        i = item.data(Qt.ItemDataRole.UserRole)
        try:
            with self.sesion.conexion() as db:
                if self.disponibilidad:
                    plato = next((p for p in platos_cocina(db) if p['id'] == i), None)
                    if plato is None:
                        raise ValueError('El plato ya no está disponible.')
                    cambiar_disponibilidad(db, i, not plato['disponible'])
                else:
                    db.execute("UPDATE ordenes_cocina SET estado='lista' WHERE id=? AND estado='pendiente'", (i,))
            self.actualizar()
        except (ValueError, sqlite3.Error) as error:
            self.estado.setText(str(error))

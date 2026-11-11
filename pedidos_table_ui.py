"""Controles del servidor y bandeja de solicitudes dentro del TPV."""
from collections import Counter
import json
import socket
import sqlite3
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QLineEdit, QComboBox, QMessageBox, QListWidget, QListWidgetItem)
from pedidos_table import SolicitudesTable, ServidorTable
from estilos import FORMULARIOS


class PaginaPedidosTable(QWidget):
    def __init__(self, sesion, turnos, al_aceptar, boton):
        super().__init__()
        self.sesion, self.turnos = sesion, turnos
        self.al_aceptar, self.boton = al_aceptar, boton
        self.solicitudes = SolicitudesTable(sesion.ruta)
        self.servidor = ServidorTable(self.solicitudes, sesion.identificar)
        self.setStyleSheet(FORMULARIOS)
        layout = QVBoxLayout(self)
        titulo = QLabel('Pedidos pendientes')
        titulo.setStyleSheet('color: #F2C66D; font-size: 24px;')
        layout.addWidget(titulo)
        self.configurar = QPushButton('Configuración')
        self.configurar.setCheckable(True)
        layout.addWidget(self.configurar)
        self.panel = QWidget()
        opciones = QVBoxLayout(self.panel)
        layout.addWidget(self.panel)
        self.panel.hide()
        self.configurar.toggled.connect(self.panel.setVisible)
        self.clave_nueva = ''
        self.ayuda = QLabel('Conecta los dispositivos del personal al mismo Wi-Fi de esta PC. '
                            'Cada solicitud necesita la aprobación de un cajero con turno activo. '
                            'Las notas se muestran aquí para que el cajero las atienda.')
        self.ayuda.setWordWrap(True)
        opciones.addWidget(self.ayuda)
        self.ip = QLineEdit()
        self.ip.setPlaceholderText('IP local de esta PC, ejemplo: 192.168.1.20')
        try:
            direcciones = socket.gethostbyname_ex(socket.gethostname())[2]
            self.ip.setText(next((ip for ip in direcciones if not ip.startswith('127.')), ''))
        except OSError:
            pass
        opciones.addWidget(self.ip)
        self.activar = QPushButton('Activar conexión móvil')
        self.activar.setMinimumHeight(54)
        self.activar.clicked.connect(self.cambiar_servidor)
        opciones.addWidget(self.activar)
        self.enlace = QLineEdit()
        self.enlace.setReadOnly(True)
        self.enlace.setPlaceholderText('Admin activa la conexión para obtener el enlace.')
        opciones.addWidget(self.enlace)
        self.ip.textChanged.connect(self.actualizar_enlace)
        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText('Nombre opcional, por ejemplo Tablet terraza')
        opciones.addWidget(self.nombre)
        crear = QPushButton('Generar enlace para un dispositivo')
        crear.clicked.connect(self.generar)
        opciones.addWidget(crear)
        self.terminales = QComboBox()
        opciones.addWidget(self.terminales)
        revocar = QPushButton('Retirar acceso al dispositivo seleccionado')
        revocar.clicked.connect(self.revocar)
        opciones.addWidget(revocar)
        self.cargar_terminales()
        self.lista = QListWidget()
        self.lista.setWordWrap(True)
        self.lista.setSpacing(10)
        layout.addWidget(self.lista, 1)
        fila = QHBoxLayout()
        self.aceptar, self.rechazar = QPushButton('Aceptar y añadir a la cuenta'), QPushButton('Rechazar')
        for boton_accion, aceptar in ((self.aceptar, True), (self.rechazar, False)):
            boton_accion.setMinimumHeight(60)
            boton_accion.clicked.connect(lambda checked=False, a=aceptar: self.resolver(a))
            fila.addWidget(boton_accion)
        layout.addLayout(fila)
        self.mensaje = QLabel('')
        self.mensaje.setWordWrap(True)
        self.mensaje.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.mensaje)
        self.temporizador = QTimer(self)
        self.temporizador.setInterval(2500)
        self.temporizador.timeout.connect(self.actualizar)
        self.temporizador.start()

    def cargar_terminales(self):
        self.terminales.clear()
        for identificador, nombre in self.solicitudes.terminales():
            self.terminales.addItem(f'{nombre} (#{identificador})', identificador)

    def generar(self):
        self.sesion.exigir_admin()
        if not self.servidor.http:
            self.mensaje.setText('Activa primero la conexión móvil.')
            return
        self.clave_nueva = self.solicitudes.vincular(self.nombre.text())
        self.nombre.clear()
        self.actualizar_enlace()
        self.cargar_terminales()

    def revocar(self):
        self.sesion.exigir_admin()
        identificador = self.terminales.currentData()
        if identificador is None:
            return
        if QMessageBox.question(self, 'Retirar acceso', self.terminales.currentText() + ' perderá acceso. ¿Continuar?') != QMessageBox.StandardButton.Yes:
            return
        self.solicitudes.revocar(identificador)
        self.clave_nueva = ''
        self.actualizar_enlace()
        self.cargar_terminales()

    def actualizar_enlace(self):
        if self.servidor.http and self.clave_nueva:
            self.enlace.setText(f'http://{self.ip.text().strip()}:{self.servidor.http.server_port}/#{self.clave_nueva}')
        else:
            self.enlace.clear()

    def cambiar_servidor(self):
        try:
            self.sesion.exigir_admin()
            if self.servidor.http:
                self.servidor.detener()
                self.activar.setText('Activar conexión móvil')
            else:
                self.servidor.iniciar()
                self.activar.setText('Desactivar conexión móvil')
            self.actualizar_enlace()
            self.mensaje.setText('Comparte el enlace solo con el personal. Usa una red privada de confianza; '
                                 'no abras el puerto al Internet. Los dispositivos vinculados conservan su acceso.')
        except (PermissionError, OSError) as e:
            self.mensaje.setText(f'No se pudo cambiar la conexión: {e}')

    def actualizar(self):
        admin = self.sesion.es_admin()
        self.configurar.setVisible(admin)
        if not admin:
            self.configurar.setChecked(False)
        if not self.sesion.usuario:
            self.lista.clear()
            return
        try:
            pendientes = self.solicitudes.listar()
            self.boton.setText(f'PedidosTable ({len(pendientes)})')
            if not self.isVisible():
                return
            seleccion = self.lista.currentItem()
            identificador = seleccion.data(Qt.ItemDataRole.UserRole) if seleccion else None
            self.lista.clear()
            for solicitud in pendientes:
                productos = json.loads(solicitud['productos'])
                cantidades = Counter((p['nombre'], p['categoria']) for p in productos)
                detalle = ', '.join(f'{cantidad} × {nombre}' for (nombre, categoria), cantidad in cantidades.items())
                cliente = self._nombre_cliente(solicitud['cliente_id'])
                texto = (f"{solicitud['mesa']} · {cliente} · {solicitud['dispositivo']} · {solicitud['emisor'] or 'Sin usuario registrado'}\n"
                         f"{detalle}\nB/.{sum(round(p['precio'] * 100) for p in productos) / 100:.2f}"
                         f" · {solicitud['fecha']}\n{solicitud['nota']}")
                item = QListWidgetItem(texto)
                item.setData(Qt.ItemDataRole.UserRole, solicitud['id'])
                self.lista.addItem(item)
                if solicitud['id'] == identificador:
                    self.lista.setCurrentItem(item)
            if not pendientes:
                self.mensaje.setText('No hay solicitudes pendientes.')
        except sqlite3.Error:
            self.mensaje.setText('No se pudo actualizar la bandeja. Se reintentará automáticamente.')

    def _nombre_cliente(self, cliente):
        with self.solicitudes.conexion() as db:
            fila = db.execute('SELECT nombre FROM clientes WHERE id = ?', (cliente,)).fetchone()
        return fila[0] if fila else 'Cuenta general'

    def resolver(self, aceptar):
        item = self.lista.currentItem()
        if not item:
            self.mensaje.setText('Selecciona una solicitud.')
            return
        try:
            mesa, cuenta = self.solicitudes.resolver(item.data(Qt.ItemDataRole.UserRole), aceptar, self.sesion, self.turnos)
            if aceptar:
                self.al_aceptar(mesa, cuenta)
            self.actualizar()
            self.mensaje.setText('Solicitud añadida a la cuenta.' if aceptar else 'Solicitud rechazada.')
        except (PermissionError, ValueError, sqlite3.Error) as e:
            self.mensaje.setText(str(e))

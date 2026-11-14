"""Controles del servidor y bandeja de solicitudes dentro del TPV."""
from collections import Counter
from shiboken6 import isValid
import json
import socket
import sqlite3
from PySide6.QtCore import QPoint, QSettings, QTimer, Qt, QEvent
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)
from dialogos import MensajesIntegrados as QMessageBox, FondoFormulario
from pedidos_table import SolicitudesTable, ServidorTable
from estilos import FORMULARIOS


class DialogoPedidoMovil(QDialog):
    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect().adjusted(1, 1, -1, -1)
        ruta = QPainterPath()
        ruta.addRoundedRect(area, 22, 22)
        degradado = QLinearGradient(area.topLeft(), area.bottomRight())
        degradado.setColorAt(0, QColor(17, 28, 44, 225))
        degradado.setColorAt(0.55, QColor(27, 42, 64, 230))
        degradado.setColorAt(1, QColor(16, 25, 41, 225))
        pintor.fillPath(ruta, degradado)
        pintor.setPen(QPen(QColor('#20d9f5'), 2))
        pintor.drawPath(ruta)

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key.Key_Escape:
            evento.accept()
            return
        super().keyPressEvent(evento)


class PaginaPedidosTable(QWidget):
    def __init__(self, sesion, turnos, al_aceptar, boton, ventana):
        super().__init__()
        self.sesion, self.turnos = sesion, turnos
        self.al_aceptar, self.boton = al_aceptar, boton
        self.ventana = ventana
        self._cerrando = False
        self.solicitudes = SolicitudesTable(sesion.ruta)
        self.servidor = ServidorTable(self.solicitudes, sesion.identificar, self.envio_directo)
        self.ajustes_conexion = QSettings("Bakachi12", "Menu")
        self.solicitud_actual = None
        self.setStyleSheet(FORMULARIOS)
        self._crear_dialogo_pedido()
        QApplication.instance().aboutToQuit.connect(self.detener_interfaz)
        ventana.destroyed.connect(self.detener_interfaz)
        layout = QVBoxLayout(self)
        titulo = QLabel('Pedidos pendientes')
        titulo.setStyleSheet('color: #79eaff; font-size: 24px;')
        layout.addWidget(titulo)
        self.panel = QWidget(self)
        self.panel.setStyleSheet(FORMULARIOS)
        opciones = QVBoxLayout(self.panel)
        opciones.addWidget(QLabel('Conexión de terminales móviles'))
        self.tipo_enlace = 'mesas'
        self.clave_nueva = ''
        self.ayuda = QLabel('Conecta los dispositivos del personal al mismo Wi-Fi de esta PC. '
                            'Los pedidos requieren aprobación, salvo los enviados por el mismo usuario de Venta libre conectado en esta PC. '
                            'Los pedidos nuevos aparecen en una ventana central para aceptar o rechazar.')
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
        crear.clicked.connect(lambda: self.generar("mesas"))
        opciones.addWidget(crear)
        cocina = QPushButton("Generar enlace de PedidosCocina")
        cocina.clicked.connect(lambda: self.generar("cocina"))
        opciones.addWidget(cocina)
        self.terminales = QComboBox()
        opciones.addWidget(self.terminales)
        revocar = QPushButton('Retirar acceso al dispositivo seleccionado')
        revocar.clicked.connect(self.revocar)
        opciones.addWidget(revocar)
        self.estado_configuracion = QLabel()
        self.estado_configuracion.setWordWrap(True)
        self.estado_configuracion.setTextFormat(Qt.TextFormat.PlainText)
        opciones.addWidget(self.estado_configuracion)
        from configuracion_visual import organizar_conexion
        organizar_conexion(self.panel, self.activar, self.ip, self.nombre, self.enlace,
                           crear, cocina, self.terminales, revocar, self.estado_configuracion)
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
        self.reintento_conexion = QTimer(self)
        self.reintento_conexion.setInterval(5000)
        self.reintento_conexion.timeout.connect(self._restaurar_conexion)
        self.ajustes_conexion.sync()
        if self.ajustes_conexion.status() != QSettings.Status.NoError:
            self.estado_configuracion.setText(
                "No se pudo leer la preferencia de conexión móvil."
            )
        elif self.ajustes_conexion.value("conexion_movil/activa", False, type=bool):
            self._restaurar_conexion()

    def _restaurar_conexion(self):
        if not self.ajustes_conexion.value("conexion_movil/activa", False, type=bool):
            self.reintento_conexion.stop()
            return
        try:
            self.servidor.iniciar()
        except OSError as error:
            self.estado_configuracion.setText(
                f"No se pudo restaurar la conexión móvil; se volverá a intentar "
                f"en 5 segundos: {error}"
            )
            if not self.reintento_conexion.isActive():
                self.reintento_conexion.start()
        else:
            self.reintento_conexion.stop()
            self.activar.setText("Desactivar conexión móvil")
            self.estado_configuracion.setText(
                "Conexión móvil restaurada automáticamente."
            )

    def _guardar_preferencia_conexion(self, activa):
        self.ajustes_conexion.setValue("conexion_movil/activa", activa)
        self.ajustes_conexion.sync()
        if self.ajustes_conexion.status() != QSettings.Status.NoError:
            self.estado_configuracion.setText(
                "La conexión cambió, pero no se pudo guardar la preferencia "
                "para el próximo inicio."
            )

    def _crear_dialogo_pedido(self):
        self.cubierta_pedido = FondoFormulario(self.ventana)
        self.cubierta_pedido.hide()
        self.dialogo = DialogoPedidoMovil(self.cubierta_pedido)
        self.dialogo.setWindowFlags(Qt.WindowType.Widget)
        self.ventana.installEventFilter(self)
        self.dialogo.setObjectName('DialogoPedidoMovil')
        self.dialogo.setWindowTitle('Pedido móvil nuevo')
        self.dialogo.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.dialogo.setStyleSheet("""
            QDialog#DialogoPedidoMovil {
                background: transparent;
                border: none;
            }
            QFrame#TarjetaPedidoMovil {
                background: rgba(25, 39, 59, 235);
                border: 1px solid #435773;
                border-radius: 16px;
            }
            QLabel {
                background: transparent;
                border: none;
                color: #E5ECF5;
                font-size: 18px;
            }
            QLabel#TituloPedidoMovil {
                color: #79eaff;
                font-size: 26px;
                font-weight: bold;
            }
            QLabel#DestinoPedidoMovil {
                color: #FFF4DC;
                font-size: 31px;
                font-weight: bold;
            }
            QLabel#TotalPedidoMovil {
                color: #79eaff;
                font-size: 34px;
                font-weight: bold;
            }
            QLabel#ProductosPedidoMovil {
                color: #eaf3ff;
                font-size: 20px;
            }
            QLabel#EstadoPedidoMovil {
                color: #FFCF88;
                font-size: 16px;
            }
            QPushButton {
                min-height: 66px;
                border: 2px solid #51657F;
                border-radius: 13px;
                padding: 8px 18px;
                background: #263951;
                color: #eaf3ff;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover { background: #354C68; }
            QPushButton#AceptarPedidoMovil {
                background: #E8B95E;
                border-color: #FFD88F;
                color: #152033;
                font-size: 22px;
            }
            QPushButton#AceptarPedidoMovil:hover { background: #79eaff; }
            QPushButton#RechazarPedidoMovil {
                background: #512E3A;
                border-color: #86505A;
            }
            QPushButton#RechazarPedidoMovil:hover { background: #693B48; }
        """)
        exterior = QVBoxLayout(self.dialogo)
        exterior.setContentsMargins(30, 26, 30, 26)
        exterior.setSpacing(14)

        titulo = QLabel('NUEVO PEDIDO DE TERMINAL MÓVIL')
        titulo.setObjectName('TituloPedidoMovil')
        exterior.addWidget(titulo)

        tarjeta = QFrame()
        tarjeta.setObjectName('TarjetaPedidoMovil')
        contenido = QVBoxLayout(tarjeta)
        contenido.setContentsMargins(22, 18, 22, 18)
        contenido.setSpacing(10)

        self.destino_pedido = QLabel()
        self.destino_pedido.setObjectName('DestinoPedidoMovil')
        self.destino_pedido.setWordWrap(True)
        self.destino_pedido.setTextFormat(Qt.TextFormat.PlainText)
        contenido.addWidget(self.destino_pedido)

        self.cliente_pedido = QLabel()
        self.cliente_pedido.setWordWrap(True)
        self.cliente_pedido.setTextFormat(Qt.TextFormat.PlainText)
        contenido.addWidget(self.cliente_pedido)

        self.dispositivo_pedido = QLabel()
        self.dispositivo_pedido.setWordWrap(True)
        self.dispositivo_pedido.setTextFormat(Qt.TextFormat.PlainText)
        contenido.addWidget(self.dispositivo_pedido)

        self.productos_pedido = QLabel()
        self.productos_pedido.setObjectName('ProductosPedidoMovil')
        self.productos_pedido.setWordWrap(True)
        self.productos_pedido.setTextFormat(Qt.TextFormat.PlainText)
        self.productos_pedido.setAlignment(Qt.AlignmentFlag.AlignTop)
        area_productos = QScrollArea()
        area_productos.setWidgetResizable(True)
        area_productos.setFrameShape(QFrame.Shape.NoFrame)
        area_productos.setStyleSheet(
            'QScrollArea { background: transparent; }'
            'QScrollArea > QWidget > QWidget { background: transparent; }'
        )
        area_productos.setWidget(self.productos_pedido)
        contenido.addWidget(area_productos, 1)

        self.nota_pedido = QLabel()
        self.nota_pedido.setWordWrap(True)
        self.nota_pedido.setTextFormat(Qt.TextFormat.PlainText)
        contenido.addWidget(self.nota_pedido)

        exterior.addWidget(tarjeta, 1)
        self.total_pedido = QLabel()
        self.total_pedido.setObjectName('TotalPedidoMovil')
        self.total_pedido.setAlignment(Qt.AlignmentFlag.AlignRight)
        exterior.addWidget(self.total_pedido)

        self.estado_pedido = QLabel()
        self.estado_pedido.setObjectName('EstadoPedidoMovil')
        self.estado_pedido.setWordWrap(True)
        self.estado_pedido.setTextFormat(Qt.TextFormat.PlainText)
        exterior.addWidget(self.estado_pedido)

        acciones = QHBoxLayout()
        acciones.setSpacing(14)
        self.btn_rechazar_pedido = QPushButton('Rechazar pedido')
        self.btn_rechazar_pedido.setObjectName('RechazarPedidoMovil')
        self.btn_aceptar_pedido = QPushButton('Aceptar y añadir a la cuenta')
        self.btn_aceptar_pedido.setObjectName('AceptarPedidoMovil')
        self.btn_rechazar_pedido.clicked.connect(
            lambda checked=False: self._resolver_pedido_actual(False)
        )
        self.btn_aceptar_pedido.clicked.connect(
            lambda checked=False: self._resolver_pedido_actual(True)
        )
        acciones.addWidget(self.btn_rechazar_pedido)
        acciones.addWidget(self.btn_aceptar_pedido, 1)
        exterior.addLayout(acciones)

        self.dialogo.resize(820, 700)
        self.dialogo.hide()

    def _mostrar_pedido(self, solicitud):
        productos = json.loads(solicitud['productos'])
        lineas = self._lineas_productos(productos)
        total = sum(round(producto['precio'] * 100) for producto in productos) / 100
        self.destino_pedido.setText(f"Destino: {solicitud['mesa']}")
        self.cliente_pedido.setText(
            f"Cliente: {self._nombre_cliente(solicitud['cliente_id'])}"
        )
        emisor = solicitud['emisor'] or 'Sin usuario registrado'
        self.dispositivo_pedido.setText(
            f"Enviado desde: {solicitud['dispositivo']} · {emisor} · "
            f"{solicitud['fecha']}"
        )
        self.productos_pedido.setText('\n'.join(lineas))
        nota = solicitud['nota'].strip()
        self.nota_pedido.setText(f"Nota: {nota}" if nota else 'Sin notas')
        self.total_pedido.setText(f'Total del pedido: B/.{total:.2f}')
        self.estado_pedido.clear()
        self.solicitud_actual = solicitud['id']

        self._central_habilitado = self.ventana.centralWidget().isEnabled()
        self._dialogo_anterior = self.ventana.property('dialogoEnCurso')
        self.ventana.setProperty('dialogoEnCurso', True)
        self.ventana.centralWidget().setEnabled(False)
        self._ajustar_pedido()
        self.cubierta_pedido.show()
        self.cubierta_pedido.raise_()
        self.dialogo.show()
        self.dialogo.raise_()
        self.btn_aceptar_pedido.setFocus()

    @staticmethod
    def _lineas_productos(productos):
        cantidades = Counter((p['nombre'], p['categoria'], p.get('preparacion', ''),
                              p.get('acompanamiento', ''), p.get('extra', '')) for p in productos)
        return [f'{cantidad} × {nombre} · {categoria}' +
                (' · ' + ' · '.join(v for v in (preparacion, lado, 'Extra: ' + extra if extra else '') if v)
                 if any((preparacion, lado, extra)) else '')
                for (nombre, categoria, preparacion, lado, extra), cantidad in cantidades.items()]

    def _ajustar_pedido(self):
        self.cubierta_pedido.setGeometry(self.ventana.rect())
        ancho = min(820, max(240, self.ventana.width() - 32))
        alto = min(700, max(240, self.ventana.height() - 32))
        self.dialogo.setGeometry((self.ventana.width() - ancho) // 2,
                                (self.ventana.height() - alto) // 2, ancho, alto)

    def detener_interfaz(self, *_):
        if self._cerrando:
            return
        self._cerrando = True
        if isValid(self.ventana) and isValid(self):
            self.ventana.removeEventFilter(self)
        for nombre in ('temporizador', 'reintento_conexion'):
            temporizador = getattr(self, nombre, None)
            if temporizador is not None and isValid(temporizador):
                temporizador.stop()

    def eventFilter(self, objeto, evento):
        if (self._cerrando or QApplication.closingDown() or not isValid(self)
                or not isValid(self.ventana) or not isValid(objeto)):
            return False
        if objeto is self.ventana and evento.type() == QEvent.Type.Resize:
            if isValid(self.cubierta_pedido) and isValid(self.dialogo):
                self._ajustar_pedido()
        return False

    def _mostrar_siguiente_pedido(self, pendientes):
        if self.solicitud_actual or not pendientes or self.dialogo.isVisible():
            return
        if not self.ventana.isVisible() or self.ventana.isMinimized():
            return
        if QApplication.activeModalWidget() is not None or self.ventana.property('dialogoEnCurso'):
            return
        try:
            self.turnos.exigir_turno_activo()
        except PermissionError:
            return
        self._mostrar_pedido(pendientes[0])

    def _resolver_pedido_actual(self, aceptar):
        if self.solicitud_actual is None:
            return
        self._resolver_identificador(
            self.solicitud_actual, aceptar, desde_dialogo=True
        )

    def cargar_terminales(self):
        self.terminales.clear()
        for identificador, nombre in self.solicitudes.terminales():
            self.terminales.addItem(f'{nombre} (#{identificador})', identificador)

    def generar(self, tipo):
        self.sesion.exigir_admin()
        if not self.servidor.http:
            self.estado_configuracion.setText('Activa primero la conexión móvil.')
            return
        self.tipo_enlace = tipo
        nombre = self.nombre.text() or ("PedidosCocina" if tipo == "cocina" else "")
        self.clave_nueva = self.solicitudes.vincular(nombre, tipo)
        self.nombre.clear()
        self.actualizar_enlace()
        self.cargar_terminales()

    def revocar(self):
        self.sesion.exigir_admin()
        identificador = self.terminales.currentData()
        if identificador is None:
            return
        if QMessageBox.question(self.ventana, 'Retirar acceso', self.terminales.currentText() + ' perderá acceso. ¿Continuar?') != QMessageBox.StandardButton.Yes:
            return
        self.solicitudes.revocar(identificador)
        self.clave_nueva = ''
        self.actualizar_enlace()
        self.cargar_terminales()

    def actualizar_enlace(self):
        if self.servidor.http and self.clave_nueva:
            ruta = '/cocina' if self.tipo_enlace == 'cocina' else '/'
            self.enlace.setText(f'http://{self.ip.text().strip()}:{self.servidor.http.server_port}{ruta}#{self.clave_nueva}')
        else:
            self.enlace.clear()

    def cambiar_servidor(self):
        try:
            self.sesion.exigir_admin()
            if self.servidor.http:
                self.servidor.detener()
                self.reintento_conexion.stop()
                self.activar.setText('Activar conexión móvil')
                self._guardar_preferencia_conexion(False)
            else:
                self.servidor.iniciar()
                self.reintento_conexion.stop()
                self.activar.setText('Desactivar conexión móvil')
                self._guardar_preferencia_conexion(True)
            self.actualizar_enlace()
            if self.ajustes_conexion.status() == QSettings.Status.NoError:
                self.estado_configuracion.setText(
                    'Comparte el enlace solo con el personal. Usa una red privada de confianza; '
                    'no abras el puerto al Internet. Los dispositivos vinculados conservan su acceso.'
                )
        except (PermissionError, OSError) as e:
            self.estado_configuracion.setText(f'No se pudo cambiar la conexión: {e}')

    def envio_directo(self,empleado):
        usuario=self.sesion.usuario
        return bool(usuario and empleado and usuario.get('tipo')=='venta_libre'
                    and empleado.get('tipo')=='venta_libre' and usuario['id']==empleado['id']
                    and self.sesion.inventario_libre_verificado)

    def actualizar(self):
        if not self.sesion.usuario:
            self.lista.clear()
            return
        try:
            for mesa,cuenta in self.solicitudes.resolver_directas(self.sesion,self.turnos):
                self.al_aceptar(mesa,cuenta)
            pendientes = self.solicitudes.listar()
            self.boton.setText(f'PedidosTable ({len(pendientes)})')
            self._mostrar_siguiente_pedido(pendientes)
            if not self.isVisible():
                return
            seleccion = self.lista.currentItem()
            identificador = seleccion.data(Qt.ItemDataRole.UserRole) if seleccion else None
            self.lista.clear()
            for solicitud in pendientes:
                productos = json.loads(solicitud['productos'])
                detalle = ', '.join(self._lineas_productos(productos))
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
        self._resolver_identificador(item.data(Qt.ItemDataRole.UserRole), aceptar)

    def _resolver_identificador(self, identificador, aceptar, desde_dialogo=False):
        try:
            mesa, cuenta = self.solicitudes.resolver(
                identificador, aceptar, self.sesion, self.turnos
            )
            if aceptar:
                self.al_aceptar(mesa, cuenta)
            if desde_dialogo:
                self.solicitud_actual = None
                self.dialogo.hide()
                self.cubierta_pedido.hide()
                self.ventana.centralWidget().setEnabled(self._central_habilitado)
                self.ventana.setProperty('dialogoEnCurso', self._dialogo_anterior)
            self.mensaje.setText(
                'Solicitud añadida a la cuenta.' if aceptar
                else 'Solicitud rechazada.'
            )
            self.actualizar()
            if desde_dialogo:
                QTimer.singleShot(0, self.actualizar)
        except (PermissionError, ValueError, sqlite3.Error) as e:
            self.mensaje.setText(str(e))
            if desde_dialogo:
                self.estado_pedido.setText(str(e))

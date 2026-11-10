"""Usuarios locales y permisos del TPV, almacenados junto a los datos de ventas."""
from contextlib import contextmanager
import hashlib
import hmac
import secrets
import sqlite3
import unicodedata

from PySide6.QtCore import Qt, QEvent, QEventLoop, QTimer, QDateTime, QLocale
from PySide6.QtGui import QColor
from pantalla_espera import FondoEspera
from PySide6.QtWidgets import (
    QApplication, QSizePolicy, QGraphicsDropShadowEffect, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPushButton, QVBoxLayout, QWidget,
)

ESTILO = """
QDialog, QWidget#Usuarios { background: #0B1020; color: #F4F2ED; }
QLabel { color: #DCE4F0; background: transparent; font-size: 15px; }
QLineEdit, QListWidget { background: #172235; color: #F4F2ED;
    border: 1px solid #34445E; border-radius: 8px; padding: 10px; font-size: 16px; }
QPushButton { background: #D6AE62; color: #101725; border: none;
    border-radius: 8px; padding: 14px; font-size: 16px; font-weight: 600; }
QPushButton:hover { background: #F2C66D; }
QPushButton:disabled { background: #34445E; color: #A8B4C8; }
"""


class SesionUsuarios:
    ITERACIONES = 600_000

    def __init__(self, ruta):
        self.ruta = str(ruta)
        self.usuario = None
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
                clave_nombre TEXT NOT NULL UNIQUE,
                sal BLOB NOT NULL, resumen BLOB NOT NULL,
                iteraciones INTEGER NOT NULL,
                rol TEXT NOT NULL CHECK(rol IN ('admin', 'mesas'))
            )''')
            if db.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0] == 0:
                self._insertar(db, 'Admin', 'Admin', 'admin')

    @contextmanager
    def conexion(self):
        db = sqlite3.connect(self.ruta)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def clave(nombre):
        return unicodedata.normalize('NFKC', nombre).strip().casefold()

    def _insertar(self, db, nombre, password, rol):
        sal = secrets.token_bytes(16)
        resumen = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), sal, self.ITERACIONES)
        db.execute('''INSERT INTO usuarios
            (nombre, clave_nombre, sal, resumen, iteraciones, rol)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (nombre.strip(), self.clave(nombre), sal, resumen, self.ITERACIONES, rol))

    def iniciar(self, nombre, password):
        self.usuario = None
        with self.conexion() as db:
            fila = db.execute('''SELECT id, nombre, rol, sal, resumen, iteraciones
                FROM usuarios WHERE clave_nombre = ?''', (self.clave(nombre),)).fetchone()
        # También calcular para nombres desconocidos, sin indicar qué dato falló.
        sal, esperado, vueltas = fila[3:] if fila else (b'\0' * 16, b'\0' * 32, self.ITERACIONES)
        obtenido = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), sal, vueltas)
        if fila and hmac.compare_digest(obtenido, esperado):
            self.usuario = dict(id=fila[0], nombre=fila[1], rol=fila[2])
            return True
        return False

    def cerrar(self):
        self.usuario = None

    def es_admin(self):
        return self.usuario is not None and self.usuario['rol'] == 'admin'

    def exigir_admin(self):
        if not self.es_admin():
            raise PermissionError('Esta opción solo está disponible para Admin.')

    def crear(self, nombre, password):
        self.exigir_admin()
        if not self.clave(nombre) or len(nombre.strip()) > 50:
            raise ValueError('Escribe un usuario de entre 1 y 50 caracteres.')
        if not password.strip() or len(password) > 128:
            raise ValueError('Escribe una contraseña de entre 1 y 128 caracteres.')
        try:
            with self.conexion() as db:
                self._insertar(db, nombre, password, 'mesas')
        except sqlite3.IntegrityError as error:
            raise ValueError('Ya existe un usuario con ese nombre.') from error

    def listar(self):
        self.exigir_admin()
        with self.conexion() as db:
            return db.execute('SELECT nombre, rol FROM usuarios ORDER BY rol, nombre').fetchall()


class DialogoAcceso(FondoEspera):
    """Acceso integrado en la ventana principal, sobre el fondo de espera."""
    def __init__(self, sesion, parent):
        super().__init__(parent)
        self.sesion = sesion
        self.ventana = parent
        self._resultado = QDialog.DialogCode.Rejected
        self._bucle = QEventLoop(self)
        self.setObjectName('AccesoIntegrado')
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(ESTILO + '''
            QWidget#TarjetaAcceso { background: #111D2F; border: 1px solid #3C4653; border-radius: 20px; }
            QWidget#TarjetaAcceso QLineEdit { background: #0B1525; border: 1px solid #34445E;
                border-radius: 9px; padding: 12px; font-size: 16px; }
            QWidget#TarjetaAcceso QLineEdit:focus { border: 1px solid #D6AE62; }
        ''')
        self.distribucion = QVBoxLayout(self)
        self.distribucion.setContentsMargins(30, 24, 30, 24)
        self.distribucion.setSpacing(8)
        marca = QLabel('R E S T A U R A N T E   &   B A R')
        marca.setAlignment(Qt.AlignmentFlag.AlignCenter)
        marca.setStyleSheet('color: #D6AE62; font-size: 12px;')
        self.distribucion.addWidget(marca)
        self.distribucion.addStretch(1)
        self.reloj = QLabel()
        self.reloj.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reloj.setStyleSheet("color: #EEF2F8; font-family: 'Segoe UI'; font-size: 46px; font-weight: 300;")
        self.distribucion.addWidget(self.reloj)
        self.fecha = QLabel()
        self.fecha.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fecha.setStyleSheet('color: #93A3BA; font-size: 13px;')
        self.distribucion.addWidget(self.fecha)
        self.distribucion.addSpacing(12)
        self.tarjeta = QWidget()
        self.tarjeta.setObjectName('TarjetaAcceso')
        self.tarjeta.setMaximumWidth(430)
        self.tarjeta.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sombra = QGraphicsDropShadowEffect(self.tarjeta)
        sombra.setBlurRadius(38)
        sombra.setOffset(0, 12)
        sombra.setColor(QColor(0, 0, 0, 90))
        self.tarjeta.setGraphicsEffect(sombra)
        layout = QVBoxLayout(self.tarjeta)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)
        titulo = QLabel('Bienvenido de nuevo')
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titulo.setStyleSheet('color: #F3E1BF; font-size: 25px; font-weight: 500;')
        layout.addWidget(titulo)
        ayuda = QLabel('Inicia sesión para continuar')
        ayuda.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ayuda.setStyleSheet('color: #99A9C1; font-size: 13px;')
        layout.addWidget(ayuda)
        layout.addSpacing(8)
        self.nombre = QLineEdit()
        self.nombre.setObjectName('usuarioAcceso')
        self.nombre.setPlaceholderText('Tu usuario')
        self.nombre.setMaxLength(50)
        self.password = QLineEdit()
        self.password.setObjectName('passwordAcceso')
        self.password.setPlaceholderText('Tu contraseña')
        self.password.setMaxLength(128)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        for titulo_campo, campo in (('Usuario', self.nombre), ('Contraseña', self.password)):
            etiqueta = QLabel(titulo_campo)
            etiqueta.setStyleSheet('color: #C0CBDA; font-size: 13px;')
            layout.addWidget(etiqueta)
            campo.setMinimumHeight(46)
            layout.addWidget(campo)
        self.error = QLabel('')
        self.error.setWordWrap(True)
        self.error.setMinimumHeight(18)
        self.error.setStyleSheet('color: #FFAEAE; font-size: 12px;')
        layout.addWidget(self.error)
        self.entrar = QPushButton('Entrar al restaurante')
        self.entrar.setMinimumHeight(48)
        self.entrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.entrar.clicked.connect(self.validar)
        self.nombre.returnPressed.connect(self.password.setFocus)
        self.password.returnPressed.connect(self.validar)
        layout.addWidget(self.entrar)
        fila = QHBoxLayout()
        fila.addStretch(1)
        fila.addWidget(self.tarjeta, 8)
        fila.addStretch(1)
        self.distribucion.addLayout(fila)
        self.distribucion.addStretch(1)
        pie = QLabel('TU ESPACIO DE TRABAJO, LISTO PARA TI')
        pie.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pie.setStyleSheet('color: #71819B; font-size: 10px;')
        self.distribucion.addWidget(pie)
        self.reloj_timer = QTimer(self)
        self.reloj_timer.setInterval(1000)
        self.reloj_timer.timeout.connect(self.actualizar_reloj)
        self.hide()

    def actualizar_reloj(self):
        ahora = QDateTime.currentDateTime()
        self.reloj.setText(ahora.toString('HH:mm'))
        self.fecha.setText(QLocale(QLocale.Language.Spanish).toString(ahora.date(), 'dddd, d MMMM'))

    def exec(self):
        self._resultado = QDialog.DialogCode.Rejected
        self.nombre.clear()
        self.password.clear()
        self.error.clear()
        contenido = self.ventana.centralWidget()
        habilitado = contenido.isEnabled()
        contenido.setEnabled(False)
        self.ventana.setProperty('accesoEnCurso', True)
        self.ventana.installEventFilter(self)
        app = QApplication.instance()
        app.aboutToQuit.connect(self.reject)
        self.setGeometry(self.ventana.rect())
        self.actualizar_reloj()
        self.reloj_timer.start()
        self.show()
        self.ventana.show()
        self.raise_()
        self.nombre.setFocus()
        try:
            self._bucle.exec()
        finally:
            self.reloj_timer.stop()
            self.password.clear()
            self.hide()
            self.ventana.removeEventFilter(self)
            self.ventana.setProperty('accesoEnCurso', False)
            contenido.setEnabled(habilitado)
            app.aboutToQuit.disconnect(self.reject)
        return self._resultado

    def result(self):
        return self._resultado

    def accept(self):
        self._resultado = QDialog.DialogCode.Accepted
        if self._bucle is not None:
            self._bucle.quit()

    def reject(self):
        self._resultado = QDialog.DialogCode.Rejected
        if self._bucle is not None:
            self._bucle.quit()

    def eventFilter(self, objeto, evento):
        if objeto is self.ventana:
            if evento.type() == QEvent.Type.Resize:
                self.setGeometry(self.ventana.rect())
                self.raise_()
            elif evento.type() == QEvent.Type.Close:
                self.reject()
        return False

    def keyPressEvent(self, evento):
        # Escape no debe dejar a la vista una sesión sin autenticar.
        evento.accept()

    def validar(self):
        self.entrar.setEnabled(False)
        try:
            if self.sesion.iniciar(self.nombre.text(), self.password.text()):
                self.password.clear()
                self.accept()
            else:
                self.error.setText('Usuario o contraseña incorrectos.')
                self.password.clear()
                self.password.setFocus()
        except sqlite3.Error:
            self.error.setText('No se pudo acceder a los usuarios. Inténtalo de nuevo.')
        finally:
            self.entrar.setEnabled(True)


class PaginaUsuarios(QWidget):
    def __init__(self, sesion, volver):
        super().__init__()
        self.sesion = sesion
        self.setObjectName('Usuarios')
        self.setStyleSheet(ESTILO)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        titulo = QLabel('Usuarios y permisos')
        titulo.setStyleSheet('font-size: 25px; color: #F2C66D;')
        layout.addWidget(titulo)
        descripcion = QLabel('Admin tiene acceso completo. Los usuarios nuevos solo pueden usar Mesas, pedidos y cobros.')
        descripcion.setWordWrap(True)
        layout.addWidget(descripcion)
        formulario = QFormLayout()
        self.nombre = QLineEdit()
        self.nombre.setObjectName('nuevoUsuario')
        self.nombre.setMaxLength(50)
        self.password = QLineEdit()
        self.confirmacion = QLineEdit()
        for campo in (self.password, self.confirmacion):
            campo.setMaxLength(128)
            campo.setEchoMode(QLineEdit.EchoMode.Password)
        formulario.addRow('Usuario', self.nombre)
        formulario.addRow('Contraseña', self.password)
        formulario.addRow('Repetir contraseña', self.confirmacion)
        layout.addLayout(formulario)
        self.crear = QPushButton('Crear usuario · Solo Mesas')
        self.crear.clicked.connect(self.guardar)
        layout.addWidget(self.crear)
        self.mensaje = QLabel('')
        self.mensaje.setWordWrap(True)
        layout.addWidget(self.mensaje)
        self.lista = QListWidget()
        layout.addWidget(self.lista, 1)
        boton_volver = QPushButton('Volver a Configuración')
        boton_volver.clicked.connect(volver)
        layout.addWidget(boton_volver)

    def limpiar(self):
        self.nombre.clear()
        self.password.clear()
        self.confirmacion.clear()
        self.mensaje.clear()
        self.lista.clear()

    def actualizar(self):
        self.sesion.exigir_admin()
        self.lista.clear()
        for nombre, rol in self.sesion.listar():
            self.lista.addItem(f'{nombre}  ·  {"Acceso completo" if rol == "admin" else "Solo Mesas"}')

    def guardar(self):
        self.crear.setEnabled(False)
        try:
            self.sesion.exigir_admin()
            if self.password.text() != self.confirmacion.text():
                raise ValueError('Las contraseñas no coinciden.')
            self.sesion.crear(self.nombre.text(), self.password.text())
            self.limpiar()
            self.actualizar()
            self.mensaje.setText('Usuario creado. Tiene permiso para Mesas, pedidos y cobros.')
        except (ValueError, PermissionError) as error:
            self.mensaje.setText(str(error))
        except sqlite3.Error:
            self.mensaje.setText('No se pudo guardar el usuario. Inténtalo de nuevo.')
        finally:
            self.crear.setEnabled(True)

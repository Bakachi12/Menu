"""Usuarios locales y permisos del TPV, almacenados junto a los datos de ventas."""
from contextlib import contextmanager
import hashlib
import hmac
import secrets
import sqlite3
import time
import unicodedata

from PySide6.QtCore import Qt, QEvent, QEventLoop, QTimer, QDateTime, QLocale
from PySide6.QtGui import QColor
from pantalla_espera import FondoEspera
from estilos import FORMULARIOS as ESTILO
from PySide6.QtWidgets import QApplication, QSizePolicy, QGraphicsDropShadowEffect, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget


class SesionUsuarios:
    ITERACIONES = 600_000

    def __init__(self, ruta):
        self.ruta = str(ruta)
        self.usuario = None
        self._autorizaciones_cierre = {}
        self.inventario_libre_verificado = False
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
                usuario TEXT,
                clave_nombre TEXT NOT NULL UNIQUE,
                sal BLOB NOT NULL, resumen BLOB NOT NULL,
                iteraciones INTEGER NOT NULL,
                rol TEXT NOT NULL CHECK(rol IN ('admin', 'mesas')),
                tipo TEXT NOT NULL DEFAULT 'normal'
            )''')
            columnas = {fila[1] for fila in db.execute("PRAGMA table_info(usuarios)")}
            if "usuario" not in columnas:
                db.execute("ALTER TABLE usuarios ADD COLUMN usuario TEXT")
            db.execute("UPDATE usuarios SET usuario = nombre WHERE usuario IS NULL")
            if "tipo" not in columnas:
                db.execute("ALTER TABLE usuarios ADD COLUMN tipo TEXT NOT NULL DEFAULT 'normal'")
            db.execute(
                "UPDATE usuarios SET rol = 'mesas', tipo = 'venta_libre' "
                "WHERE clave_nombre = ?",
                (self.clave('Ventalibre'),),
            )
            if db.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0] == 0:
                self._insertar(db, 'Admin', 'Admin', 'Admin', 'admin')
            if not db.execute('SELECT 1 FROM usuarios WHERE clave_nombre = ?',
                              (self.clave('Ventalibre'),)).fetchone():
                self._insertar(db, 'Venta libre', 'Ventalibre', 'admin', 'mesas', 'venta_libre')

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

    def _insertar(self, db, nombre, usuario, password, rol, tipo='normal'):
        sal = secrets.token_bytes(16)
        resumen = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), sal, self.ITERACIONES)
        db.execute('''INSERT INTO usuarios
            (nombre, usuario, clave_nombre, sal, resumen, iteraciones, rol, tipo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (nombre.strip(), usuario.strip(), self.clave(usuario), sal, resumen,
             self.ITERACIONES, rol, tipo))

    def iniciar(self, usuario, password):
        self.usuario = None
        self._autorizaciones_cierre.clear()
        self.inventario_libre_verificado = False
        self.usuario = self.identificar(usuario, password)
        return self.usuario is not None

    def restaurar(self, usuario_id):
        """Restaura el perfil local guardado para reanudar una sesión en este equipo."""
        self.cerrar()
        if type(usuario_id) is not int or usuario_id <= 0:
            return False
        with self.conexion() as db:
            fila = db.execute(
                'SELECT id, nombre, usuario, rol, tipo FROM usuarios WHERE id = ?',
                (usuario_id,),
            ).fetchone()
        if fila is None:
            return False
        self.usuario = dict(
            id=fila[0], nombre=fila[1], usuario=fila[2], rol=fila[3], tipo=fila[4]
        )
        return True

    def identificar(self, usuario, password):
        """Verifica credenciales sin cambiar la sesión de la caja."""
        with self.conexion() as db:
            fila = db.execute('''SELECT id, nombre, usuario, rol, tipo, sal, resumen, iteraciones
                FROM usuarios WHERE clave_nombre = ?''', (self.clave(usuario),)).fetchone()
        # También calcular para nombres desconocidos, sin indicar qué dato falló.
        sal, esperado, vueltas = fila[5:] if fila else (b'\0' * 16, b'\0' * 32, self.ITERACIONES)
        obtenido = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), sal, vueltas)
        if fila and hmac.compare_digest(obtenido, esperado):
            return dict(id=fila[0], nombre=fila[1], usuario=fila[2], rol=fila[3], tipo=fila[4])
        return None

    def validar_admin(self, password):
        """Comprueba una contraseña de Admin sin cambiar la sesión actual."""
        return self.identificar_admin(password) is not None

    def identificar_admin(self, password):
        """Devuelve el ID del Admin que validó la contraseña, sin cambiar la sesión."""
        with self.conexion() as db:
            filas = db.execute(
                "SELECT id, sal, resumen, iteraciones FROM usuarios WHERE rol = 'admin'"
            ).fetchall()
        administrador_id = None
        for identificador, sal, esperado, vueltas in filas:
            obtenido = hashlib.pbkdf2_hmac(
                'sha256', password.encode('utf-8'), sal, vueltas
            )
            if hmac.compare_digest(obtenido, esperado):
                administrador_id = identificador
        return administrador_id

    def autorizar_asignacion_tras_cierre(self, password, turno_id):
        """Autoriza una asignación manual única tras cerrar el turno indicado."""
        self._autorizaciones_cierre.pop(turno_id, None)
        if not self.usuario:
            return False
        administrador_id = self.identificar_admin(password)
        if administrador_id is None:
            return False
        self._autorizaciones_cierre[turno_id] = (
            self.usuario['id'], time.monotonic() + 1800, administrador_id
        )
        return True

    def responsable_asignacion_tras_cierre(self, turno_id):
        if self.es_admin():
            return self.usuario['id']
        autorizacion = self._autorizaciones_cierre.get(turno_id)
        if (
            not self.usuario
            or autorizacion is None
            or autorizacion[0] != self.usuario['id']
            or autorizacion[1] <= time.monotonic()
        ):
            raise PermissionError(
                "Se necesita autorización reciente de Admin para asignar el siguiente turno."
            )
        return autorizacion[2]

    def puede_asignar_tras_cierre(self, turno_id):
        try:
            self.responsable_asignacion_tras_cierre(turno_id)
        except PermissionError:
            return False
        return True

    def revocar_asignacion_tras_cierre(self, turno_id):
        self._autorizaciones_cierre.pop(turno_id, None)

    def cerrar(self):
        self.usuario = None
        self._autorizaciones_cierre.clear()
        self.inventario_libre_verificado = False

    def es_admin(self):
        return self.usuario is not None and self.usuario['rol'] == 'admin'

    def es_venta_libre(self):
        return self.usuario is not None and self.usuario.get('tipo') == 'venta_libre'

    def exigir_admin(self):
        if not self.es_admin():
            raise PermissionError('Esta opción solo está disponible para Admin.')

    def crear(self, nombre, usuario, password):
        self.exigir_admin()
        nombre = nombre.strip()
        usuario = usuario.strip()
        if not nombre or len(nombre) > 80 or not nombre.isprintable():
            raise ValueError('Escribe un nombre válido de entre 1 y 80 caracteres.')
        if not self.clave(usuario) or len(usuario) > 50 or not usuario.isprintable():
            raise ValueError('Escribe un usuario de entre 1 y 50 caracteres.')
        if not password.strip() or len(password) > 128:
            raise ValueError('Escribe una contraseña de entre 1 y 128 caracteres.')
        try:
            with self.conexion() as db:
                self._insertar(db, nombre, usuario, password, 'mesas')
        except sqlite3.IntegrityError as error:
            raise ValueError('Ya existe una cuenta con ese usuario de acceso.') from error

    def listar(self):
        self.exigir_admin()
        with self.conexion() as db:
            return db.execute(
                'SELECT nombre, usuario, rol, tipo FROM usuarios ORDER BY rol, nombre'
            ).fetchall()

    def actualizar_cuenta(self, usuario, actual, nueva=''):
        """Modificar la cuenta autenticada conservando su identidad y permisos."""
        self.exigir_admin()
        usuario = usuario.strip()
        if not self.clave(usuario) or len(usuario) > 50 or not usuario.isprintable():
            raise ValueError('Escribe un usuario válido de entre 1 y 50 caracteres.')
        if nueva and (not nueva.strip() or len(nueva) > 128):
            raise ValueError('La nueva contraseña debe tener entre 1 y 128 caracteres.')
        try:
            with self.conexion() as db:
                db.execute('BEGIN IMMEDIATE')
                fila = db.execute('SELECT sal, resumen, iteraciones FROM usuarios WHERE id = ? AND rol = ?',
                                  (self.usuario['id'], 'admin')).fetchone()
                if fila is None:
                    raise PermissionError('La cuenta de administrador ya no está disponible.')
                sal, resumen, vueltas = fila
                prueba = hashlib.pbkdf2_hmac('sha256', actual.encode('utf-8'), sal, vueltas)
                if not hmac.compare_digest(prueba, resumen):
                    raise ValueError('La contraseña actual no es correcta.')
                if nueva:
                    sal = secrets.token_bytes(16)
                    vueltas = self.ITERACIONES
                    resumen = hashlib.pbkdf2_hmac('sha256', nueva.encode('utf-8'), sal, vueltas)
                db.execute('''UPDATE usuarios SET usuario = ?, clave_nombre = ?,
                    sal = ?, resumen = ?, iteraciones = ? WHERE id = ?''',
                    (usuario, self.clave(usuario), sal, resumen, vueltas, self.usuario['id']))
        except sqlite3.IntegrityError as error:
            raise ValueError('Ya existe otro usuario con ese nombre.') from error
        self.usuario['usuario'] = usuario


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
            QWidget#TarjetaAcceso { background: rgba(17, 29, 47, 235); border: 1px solid #3C4653; border-radius: 20px; }
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
        self.ventana.showFullScreen()
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
        descripcion = QLabel('Admin tiene acceso completo. Los usuarios nuevos pueden usar Mesas, Clientes, pedidos y cobros.')
        descripcion.setWordWrap(True)
        layout.addWidget(descripcion)
        formulario = QFormLayout()
        self.nombre = QLineEdit()
        self.nombre.setObjectName('nuevoUsuario')
        self.nombre.setMaxLength(50)
        self.nombre.setPlaceholderText('Ejemplo: beto')
        self.password = QLineEdit()
        self.confirmacion = QLineEdit()
        for campo in (self.password, self.confirmacion):
            campo.setMaxLength(128)
            campo.setEchoMode(QLineEdit.EchoMode.Password)
        self.nombre_completo = QLineEdit()
        self.nombre_completo.setObjectName('nuevoNombreCompleto')
        self.nombre_completo.setMaxLength(80)
        self.nombre_completo.setPlaceholderText('Ejemplo: Alberto Mendoza')
        formulario.addRow('Nombre completo', self.nombre_completo)
        formulario.addRow('Usuario para iniciar sesión', self.nombre)
        formulario.addRow('Contraseña', self.password)
        formulario.addRow('Repetir contraseña', self.confirmacion)
        layout.addLayout(formulario)
        self.crear = QPushButton('Crear usuario · Mesas y Clientes')
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
        self.nombre_completo.clear()
        self.password.clear()
        self.confirmacion.clear()
        self.mensaje.clear()
        self.lista.clear()

    def actualizar(self):
        self.sesion.exigir_admin()
        self.lista.clear()
        for nombre, usuario, rol, tipo in self.sesion.listar():
            acceso = "Venta libre · Sin turno" if tipo == "venta_libre" else "Mesas y Clientes"
            self.lista.addItem(
                f'{nombre}  ·  Usuario: {usuario}  ·  '
                f'{"Acceso completo" if rol == "admin" else acceso}'
            )

    def guardar(self):
        self.crear.setEnabled(False)
        try:
            self.sesion.exigir_admin()
            if self.password.text() != self.confirmacion.text():
                raise ValueError('Las contraseñas no coinciden.')
            self.sesion.crear(
                self.nombre_completo.text(), self.nombre.text(), self.password.text()
            )
            self.limpiar()
            self.actualizar()
            self.mensaje.setText('Usuario creado. Tiene permiso para Mesas, Clientes, pedidos y cobros.')
        except (ValueError, PermissionError) as error:
            self.mensaje.setText(str(error))
        except sqlite3.Error:
            self.mensaje.setText('No se pudo guardar el usuario. Inténtalo de nuevo.')
        finally:
            self.crear.setEnabled(True)

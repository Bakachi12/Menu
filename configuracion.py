"""Personalización del restaurante: mesas persistentes y cuenta del dueño."""
import sqlite3
from PySide6.QtCore import Qt

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget, QScrollArea
from estilos import FORMULARIOS as ESTILO


class CatalogoMesas:
    def __init__(self, sesion):
        self.sesion = sesion
        with sesion.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE IF NOT EXISTS mesas_configuracion (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL,
                clave_nombre TEXT NOT NULL UNIQUE
            )''')
            if db.execute('SELECT COUNT(*) FROM mesas_configuracion').fetchone()[0] == 0:
                db.executemany('INSERT INTO mesas_configuracion(nombre, clave_nombre) VALUES (?, ?)',
                               [(f'Mesa {i:02}', f'mesa {i:02}') for i in range(1, 5)])

    def listar(self):
        with self.sesion.conexion() as db:
            return [fila[0] for fila in db.execute('SELECT nombre FROM mesas_configuracion ORDER BY id')]

    def sugerir_nombre(self):
        claves = {self.sesion.clave(nombre) for nombre in self.listar()}
        numero = 1
        while self.sesion.clave(f'Mesa {numero:02}') in claves:
            numero += 1
        return f'Mesa {numero:02}'

    def agregar(self, nombre):
        self.sesion.exigir_admin()
        nombre = nombre.strip()
        if not self.sesion.clave(nombre) or len(nombre) > 40 or not nombre.isprintable():
            raise ValueError('Escribe un nombre de mesa de entre 1 y 40 caracteres.')
        try:
            with self.sesion.conexion() as db:
                db.execute('INSERT INTO mesas_configuracion(nombre, clave_nombre) VALUES (?, ?)',
                           (nombre, self.sesion.clave(nombre)))
        except sqlite3.IntegrityError as error:
            raise ValueError('Ya existe una mesa con ese nombre.') from error
        return nombre


class PaginaMesasConfiguracion(QWidget):
    def __init__(self, catalogo, al_agregar, volver):
        super().__init__()
        self.catalogo = catalogo
        self.al_agregar = al_agregar
        self.setObjectName('ConfigMesas')
        self.setStyleSheet(ESTILO)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        titulo = QLabel('Mesas del restaurante')
        titulo.setStyleSheet('color: #F2C66D; font-size: 25px;')
        layout.addWidget(titulo)
        ayuda = QLabel('Añade mesas para tu salón, terraza o barra. Estarán disponibles para todos los usuarios.')
        ayuda.setWordWrap(True)
        layout.addWidget(ayuda)
        layout.addWidget(QLabel('Nombre de la mesa'))
        self.nombre = QLineEdit()
        self.nombre.setMaxLength(40)
        self.nombre.setPlaceholderText('Ejemplo: Mesa 05 o Terraza 1')
        layout.addWidget(self.nombre)
        self.boton_agregar = QPushButton('Agregar mesa')
        self.boton_agregar.clicked.connect(self.guardar)
        layout.addWidget(self.boton_agregar)
        self.mensaje = QLabel('')
        self.mensaje.setWordWrap(True)
        layout.addWidget(self.mensaje)
        self.lista = QListWidget()
        layout.addWidget(self.lista, 1)
        boton_volver = QPushButton('Volver a Configuración')
        boton_volver.clicked.connect(volver)
        layout.addWidget(boton_volver)

    def actualizar(self):
        self.catalogo.sesion.exigir_admin()
        self.lista.clear()
        self.lista.addItems(self.catalogo.listar())
        self.nombre.setText(self.catalogo.sugerir_nombre())
        self.mensaje.clear()

    def guardar(self):
        self.boton_agregar.setEnabled(False)
        try:
            nombre = self.catalogo.agregar(self.nombre.text())
            self.al_agregar(nombre)
            self.actualizar()
            self.mensaje.setText(f'{nombre} ya está disponible en Mesas.')
        except (ValueError, PermissionError) as error:
            self.mensaje.setText(str(error))
        except sqlite3.Error:
            self.mensaje.setText('No se pudo guardar la mesa. Inténtalo de nuevo.')
        finally:
            self.boton_agregar.setEnabled(True)


class PaginaMiCuenta(QWidget):
    def __init__(self, sesion, al_guardar, volver):
        super().__init__()
        self.sesion = sesion
        self.al_guardar = al_guardar
        self.setObjectName('MiCuenta')
        self.setStyleSheet(ESTILO)
        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')
        contenido = QWidget()
        contenido.setObjectName('ContenidoCuenta')
        contenido.setStyleSheet('QWidget#ContenidoCuenta { background: #101725; }')
        layout = QVBoxLayout(contenido)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        titulo = QLabel('Mi cuenta de administrador')
        titulo.setWordWrap(True)
        titulo.setStyleSheet('color: #F2C66D; font-size: 25px;')
        layout.addWidget(titulo)
        ayuda = QLabel('Personaliza tu usuario y contraseña. Conservarás todos los permisos de administrador.')
        ayuda.setWordWrap(True)
        layout.addWidget(ayuda)
        self.usuario = QLineEdit()
        self.usuario.setMaxLength(50)
        self.actual = QLineEdit()
        self.nueva = QLineEdit()
        self.confirmacion = QLineEdit()
        for campo in (self.actual, self.nueva, self.confirmacion):
            campo.setEchoMode(QLineEdit.EchoMode.Password)
            campo.setMaxLength(128)
        self.nueva.setPlaceholderText('Déjala vacía para conservar la actual')
        formulario = QVBoxLayout()
        for texto, campo in (('Usuario para iniciar sesión', self.usuario),
                             ('Contraseña actual · necesaria para guardar', self.actual),
                             ('Nueva contraseña · opcional', self.nueva),
                             ('Repetir nueva contraseña', self.confirmacion)):
            etiqueta = QLabel(texto)
            etiqueta.setWordWrap(True)
            formulario.addWidget(etiqueta)
            formulario.addWidget(campo)
        layout.addLayout(formulario)
        self.guardar_boton = QPushButton('Guardar mi cuenta')
        self.guardar_boton.clicked.connect(self.guardar)
        layout.addWidget(self.guardar_boton)
        self.mensaje = QLabel('')
        self.mensaje.setWordWrap(True)
        layout.addWidget(self.mensaje)
        layout.addStretch()
        volver_boton = QPushButton('Volver a Configuración')
        volver_boton.clicked.connect(volver)
        layout.addWidget(volver_boton)
        scroll.setWidget(contenido)
        exterior.addWidget(scroll)

    def limpiar(self):
        self.actual.clear()
        self.nueva.clear()
        self.confirmacion.clear()
        self.mensaje.clear()

    def actualizar(self):
        self.sesion.exigir_admin()
        self.limpiar()
        self.usuario.setText(self.sesion.usuario['usuario'])

    def guardar(self):
        self.guardar_boton.setEnabled(False)
        try:
            self.sesion.exigir_admin()
            if self.nueva.text() != self.confirmacion.text():
                raise ValueError('Las contraseñas nuevas no coinciden.')
            self.sesion.actualizar_cuenta(
                self.usuario.text(), self.actual.text(), self.nueva.text()
            )
            self.actualizar()
            self.al_guardar()
            self.mensaje.setText('Cuenta actualizada. Usa estos datos la próxima vez que inicies sesión.')
        except (ValueError, PermissionError) as error:
            self.mensaje.setText(str(error))
        except sqlite3.Error:
            self.mensaje.setText('No se pudo actualizar la cuenta. Inténtalo de nuevo.')
        finally:
            self.guardar_boton.setEnabled(True)

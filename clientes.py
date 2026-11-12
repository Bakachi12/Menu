"""Clientes y pedidos abiertos; las identidades no dependen del nombre visible."""
import json
import sqlite3
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QScroller, QPushButton, QAbstractItemView
from estilos import FORMULARIOS as ESTILO

# Identificador interno no imprimible: nunca coincide con el nombre de una mesa.
VENTA_RAPIDA = '\x1fventa_rapida'


def nombre_operacion(clave):
    return 'Venta rápida' if clave == VENTA_RAPIDA else clave


def centimos(producto):
    return round(producto['precio'] * 100)


def clave_producto(producto):
    return (producto['nombre'], centimos(producto), producto.get('categoria', ''),
            producto.get('preparacion', ''), producto.get('acompanamiento', ''))


class GestionClientes:
    def __init__(self, sesion):
        self.sesion = sesion
        with sesion.conexion() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
                clave_nombre TEXT NOT NULL UNIQUE, mesa TEXT
            )''')
            db.execute('''CREATE TABLE IF NOT EXISTS pedidos_abiertos (
                mesa TEXT PRIMARY KEY, productos TEXT NOT NULL
            )''')

    def autorizado(self):
        if self.sesion.usuario is None:
            raise PermissionError('Inicia sesión para gestionar clientes.')

    def listar(self):
        with self.sesion.conexion() as db:
            return [dict(id=i, nombre=n, mesa=m) for i, n, m in db.execute(
                'SELECT id, nombre, mesa FROM clientes ORDER BY nombre COLLATE NOCASE, id')]

    def de_mesa(self, mesa):
        return [cliente for cliente in self.listar() if cliente['mesa'] == mesa]

    def obtener(self, identificador):
        return next((c for c in self.listar() if c['id'] == identificador), None)

    def validar_mesa(self, db, mesa):
        if mesa is not None and not db.execute(
                'SELECT 1 FROM mesas_configuracion WHERE nombre = ?', (mesa,)).fetchone():
            raise ValueError('Selecciona una mesa disponible en el restaurante.')

    def crear(self, nombre, mesa):
        self.autorizado()
        nombre = nombre.strip()
        if not nombre or len(nombre) > 80 or not nombre.isprintable():
            raise ValueError('Escribe un nombre de cliente de entre 1 y 80 caracteres.')
        try:
            with self.sesion.conexion() as db:
                self.validar_mesa(db, mesa)
                cursor = db.execute('INSERT INTO clientes(nombre, clave_nombre, mesa) VALUES (?, ?, ?)',
                                    (nombre, self.sesion.clave(nombre), mesa))
                return cursor.lastrowid
        except sqlite3.IntegrityError as error:
            raise ValueError('Ese cliente ya está registrado. Selecciónalo en la lista de clientes existentes.') from error

    def asignar(self, identificador, mesa):
        self.autorizado()
        with self.sesion.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            self.validar_mesa(db, mesa)
            fila = db.execute('SELECT mesa FROM clientes WHERE id = ?', (identificador,)).fetchone()
            if fila is None:
                raise ValueError('El cliente ya no está disponible.')
            if fila[0] == mesa:
                return
            for (datos,) in db.execute('SELECT productos FROM pedidos_abiertos'):
                if any(p.get('cliente_id') == identificador for p in json.loads(datos)):
                    raise ValueError('Este cliente tiene productos pendientes. Cobra su mesa antes de cambiarlo.')
            db.execute('UPDATE clientes SET mesa = ? WHERE id = ?', (mesa, identificador))

    def cargar_pedidos(self):
        with self.sesion.conexion() as db:
            return {mesa: json.loads(datos) for mesa, datos in db.execute(
                'SELECT mesa, productos FROM pedidos_abiertos')}

    def guardar_pedido(self, mesa, productos):
        self.autorizado()
        with self.sesion.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            if mesa != VENTA_RAPIDA:
                self.validar_mesa(db, mesa)
            elif any(p.get('cliente_id') is not None for p in productos):
                raise ValueError('La venta rápida no admite clientes de una mesa.')
            for producto in productos:
                cliente = producto.get('cliente_id')
                if cliente is not None and not db.execute(
                        'SELECT 1 FROM clientes WHERE id = ? AND mesa = ?', (cliente, mesa)).fetchone():
                    raise ValueError('El cliente seleccionado ya no está asignado a esta mesa.')
            db.execute('''INSERT INTO pedidos_abiertos(mesa, productos) VALUES (?, ?)
                ON CONFLICT(mesa) DO UPDATE SET productos = excluded.productos''',
                (mesa, json.dumps(productos, ensure_ascii=False)))


class PaginaClientes(QWidget):
    def __init__(self, gestion, pedidos, al_abrir, al_agregar):
        super().__init__()
        self.gestion = gestion
        self.pedidos = pedidos
        self.al_abrir = al_abrir
        self.setObjectName('PaginaClientes')
        self.setStyleSheet(ESTILO + '''
            QLineEdit { font-size: 18px; }
            QListWidget { background: rgba(11, 21, 37, 190); color: #F4F2ED; border: 1px solid #29374C;
                border-radius: 12px; font-size: 18px; padding: 6px; }
            QListWidget::item { padding: 12px 16px; border-bottom: 1px solid #243147; border-radius: 8px; }
            QListWidget::item:selected { background: #293A52; color: #F2C66D; }
            QListWidget::item:hover { background: #1B2A40; }
        ''')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)
        barra = QHBoxLayout()
        barra.setSpacing(12)
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText('Buscar cliente…')
        self.buscar.setMinimumHeight(58)
        self.buscar.textChanged.connect(self.filtrar)
        self.agregar = QPushButton('+  Agregar')
        self.agregar.setMinimumHeight(58)
        self.agregar.setMinimumWidth(150)
        self.agregar.clicked.connect(al_agregar)
        barra.addWidget(self.buscar, 1)
        barra.addWidget(self.agregar)
        layout.addLayout(barra)
        self.lista = QListWidget()
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lista.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista.setSpacing(4)
        self.lista.itemClicked.connect(self.abrir_item)
        QScroller.grabGesture(self.lista.viewport(), QScroller.ScrollerGestureType.TouchGesture)
        layout.addWidget(self.lista, 1)
        self.vacio = QLabel('')
        self.vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vacio.setWordWrap(True)
        self.vacio.setStyleSheet('color: #A8B8CE; font-size: 17px; padding: 16px;')
        layout.addWidget(self.vacio)

    def actualizar(self):
        self.gestion.autorizado()
        self.lista.clear()
        for cliente in self.gestion.listar():
            total = sum(centimos(p) for p in self.pedidos.get(cliente['mesa'], [])
                        if p.get('cliente_id') == cliente['id'])
            detalle = f"{cliente['mesa']}  ·  B/.{total / 100:.2f}" if cliente['mesa'] else 'Toca para elegir mesa'
            item = QListWidgetItem(f"{cliente['nombre']}\n{detalle}")
            item.setData(Qt.ItemDataRole.UserRole, cliente['id'])
            item.setData(Qt.ItemDataRole.UserRole + 1, f"{cliente['nombre']} {cliente['mesa'] or ''}".casefold())
            item.setSizeHint(QSize(0, 92))
            self.lista.addItem(item)
        self.filtrar()

    def abrir_item(self, item):
        self.al_abrir(item.data(Qt.ItemDataRole.UserRole))

    def filtrar(self):
        texto = self.buscar.text().strip().casefold()
        visibles = 0
        for indice in range(self.lista.count()):
            item = self.lista.item(indice)
            coincide = texto in item.data(Qt.ItemDataRole.UserRole + 1)
            item.setHidden(not coincide)
            visibles += coincide
        self.vacio.setText('No hay coincidencias.' if self.lista.count() else 'Todavía no hay clientes. Toca Agregar para registrar el primero.')
        self.vacio.setVisible(visibles == 0)

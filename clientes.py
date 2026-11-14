"""Clientes y pedidos abiertos; las identidades no dependen del nombre visible."""
import json
import sqlite3
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QScroller, QPushButton, QAbstractItemView
from cocina import preparar_cocina, sincronizar_comandas, validar_aumentos
from estilos import FORMULARIOS as ESTILO

# Identificador interno no imprimible: nunca coincide con el nombre de una mesa.
VENTA_RAPIDA = '\x1fventa_rapida'


def cuenta_barra(cliente):
    return f"\x1fbarra:{cliente['id']}:{cliente['nombre']}"


def es_barra(clave):
    return isinstance(clave, str) and clave.startswith('\x1fbarra:')


def nombre_operacion(clave):
    if es_barra(clave):
        return 'Barra · ' + clave.split(':', 2)[-1]
    return 'Venta rápida' if clave == VENTA_RAPIDA else clave


def centimos(producto):
    return round(producto['precio'] * 100)


def clave_producto(producto):
    return (producto['nombre'], centimos(producto), producto.get('categoria', ''),
            producto.get('preparacion', ''), producto.get('acompanamiento', ''),
            producto.get('extra', ''), producto.get('recargo_centimos', 0))


class GestionClientes:
    def __init__(self, sesion):
        self.sesion = sesion
        with sesion.conexion() as db:
            preparar_cocina(db)
            db.execute('''CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
                clave_nombre TEXT NOT NULL UNIQUE, mesa TEXT
            )''')
            columnas={fila[1] for fila in db.execute('PRAGMA table_info(clientes)')}
            for campo,tipo in [('correo',"TEXT NOT NULL DEFAULT ''"),('telefono',"TEXT NOT NULL DEFAULT ''"),('notas',"TEXT NOT NULL DEFAULT ''"),('frecuente','INTEGER NOT NULL DEFAULT 0')]:
                if campo not in columnas:
                    db.execute(f'ALTER TABLE clientes ADD COLUMN {campo} {tipo}')
            db.execute('''CREATE TABLE IF NOT EXISTS pedidos_abiertos (
                mesa TEXT PRIMARY KEY, productos TEXT NOT NULL
            )''')

    def autorizado(self):
        if self.sesion.usuario is None:
            raise PermissionError('Inicia sesión para gestionar clientes.')
        if self.sesion.usuario.get('rol') == 'cocinero':
            raise PermissionError('El rol Cocinero solo puede gestionar cocina.')

    def listar(self):
        with self.sesion.conexion() as db:
            return [dict(id=i, nombre=n, mesa=m, correo=c, telefono=t, notas=o, frecuente=bool(f)) for i, n, m, c, t, o, f in db.execute(
                'SELECT id, nombre, mesa, correo, telefono, notas, frecuente FROM clientes ORDER BY nombre COLLATE NOCASE, id')]

    def editar(self, identificador, nombre, correo='', telefono='', notas='', frecuente=False):
        self.autorizado()
        nombre=nombre.strip();correo=correo.strip();telefono=telefono.strip();notas=notas.strip()
        if not nombre or len(nombre)>80 or not nombre.isprintable():
            raise ValueError('Escribe un nombre válido de hasta 80 caracteres.')
        if correo and ('@' not in correo or '.' not in correo.rsplit('@',1)[-1] or any(c.isspace() for c in correo)):
            raise ValueError('Revisa el correo electrónico.')
        if len(correo)>254 or len(telefono)>80 or len(notas)>2000:
            raise ValueError('Los datos de contacto o las notas son demasiado largos.')
        try:
            with self.sesion.conexion() as db:
                db.execute('BEGIN IMMEDIATE')
                fila=db.execute('SELECT nombre,mesa FROM clientes WHERE id=?',(identificador,)).fetchone()
                if fila is None: raise ValueError('El cliente ya no existe.')
                anterior=fila[1]
                destino=cuenta_barra(dict(id=identificador,nombre=nombre)) if es_barra(anterior) else anterior
                db.execute('UPDATE clientes SET nombre=?,clave_nombre=?,correo=?,telefono=?,notas=?,frecuente=?,mesa=? WHERE id=?',
                           (nombre,self.sesion.clave(nombre),correo,telefono,notas,int(frecuente),destino,identificador))
                for mesa,datos in db.execute('SELECT mesa,productos FROM pedidos_abiertos').fetchall():
                    productos=json.loads(datos)
                    for producto in productos:
                        if producto.get('cliente_id')==identificador: producto['cliente_nombre']=nombre
                    nueva=destino if mesa==anterior and es_barra(anterior) else mesa
                    db.execute('UPDATE pedidos_abiertos SET mesa=?,productos=? WHERE mesa=?',(nueva,json.dumps(productos,ensure_ascii=False),mesa))
                if es_barra(anterior) and anterior!=destino:
                    db.execute('UPDATE ordenes_cocina SET mesa=? WHERE mesa=?',(nombre_operacion(destino),nombre_operacion(anterior)))
        except sqlite3.IntegrityError as error:
            raise ValueError('Ya existe otro cliente con ese nombre.') from error

    def de_mesa(self, mesa):
        return [cliente for cliente in self.listar() if cliente['mesa'] == mesa]

    def obtener(self, identificador):
        return next((c for c in self.listar() if c['id'] == identificador), None)

    def validar_mesa(self, db, mesa):
        if es_barra(mesa):
            cliente = next((dict(id=i, nombre=n) for i,n in db.execute('SELECT id,nombre FROM clientes')
                            if cuenta_barra(dict(id=i,nombre=n)) == mesa), None)
            if cliente is None:
                raise ValueError('La cuenta de barra no corresponde a un cliente registrado.')
            return
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

    def asignar_barra(self, identificador):
        cliente = self.obtener(identificador)
        if cliente is None:
            raise ValueError('El cliente ya no está disponible.')
        destino = cuenta_barra(cliente)
        self.asignar(identificador, destino)
        return destino

    def asignar(self, identificador, mesa):
        self.autorizado()
        if es_barra(mesa):
            cliente = self.obtener(identificador)
            if cliente is None or cuenta_barra(cliente) != mesa:
                raise ValueError('Cada cliente de barra debe tener su propia cuenta.')
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
                if es_barra(mesa) and (cliente is None or cuenta_barra(self.obtener(cliente) or dict(id=0,nombre='')) != mesa):
                    raise ValueError('La cuenta de barra solo admite consumos de su cliente.')
                if cliente is not None and not db.execute(
                        'SELECT 1 FROM clientes WHERE id = ? AND mesa = ?', (cliente, mesa)).fetchone():
                    raise ValueError('El cliente seleccionado ya no está asignado a esta mesa.')
            anterior = db.execute('SELECT productos FROM pedidos_abiertos WHERE mesa=?', (mesa,)).fetchone()
            anteriores = json.loads(anterior[0]) if anterior else []
            validar_aumentos(db, anteriores, productos)
            sincronizar_comandas(db, nombre_operacion(mesa), anteriores, productos)
            db.execute('''INSERT INTO pedidos_abiertos(mesa, productos) VALUES (?, ?)
                ON CONFLICT(mesa) DO UPDATE SET productos = excluded.productos''',
                (mesa, json.dumps(productos, ensure_ascii=False)))


class PaginaClientes(QWidget):
    def __init__(self, gestion, pedidos, al_abrir, al_agregar, al_barra=None, al_mesa=None, al_editar=None):
        super().__init__()
        self.gestion = gestion
        self.pedidos = pedidos
        self.al_abrir = al_abrir
        self.al_barra = al_barra
        self.al_mesa = al_mesa
        self.al_editar = al_editar
        self.setObjectName('PaginaClientes')
        self.setStyleSheet(ESTILO + '''
            QLineEdit { font-size: 18px; }
            QListWidget { background: rgba(11, 21, 37, 190); color: #eaf3ff; border: 1px solid #29374C;
                border-radius: 12px; font-size: 18px; padding: 6px; }
            QListWidget::item { padding: 12px 16px; border-bottom: 1px solid #243147; border-radius: 8px; }
            QListWidget::item:selected { background: #293A52; color: #79eaff; }
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
            detalle = f"{nombre_operacion(cliente['mesa'])}  ·  B/.{total / 100:.2f}" if cliente['mesa'] else 'Elige Barra o Añadir a mesa'
            item = QListWidgetItem(f"{cliente['nombre']}\n{detalle}")
            item.setData(Qt.ItemDataRole.UserRole, cliente['id'])
            item.setData(Qt.ItemDataRole.UserRole + 1, f"{cliente['nombre']} {cliente['mesa'] or ''} {cliente.get('correo','')} {cliente.get('telefono','')}".casefold())
            item.setSizeHint(QSize(0, 92))
            self.lista.addItem(item)
            if self.al_barra is not None and self.al_mesa is not None:
                item.setText("")
                fila = QWidget()
                from interfaz_adaptable import es_android
                pequeno=es_android() and self.window().width()<900
                caja = QVBoxLayout(fila) if pequeno else QHBoxLayout(fila)
                acciones=QHBoxLayout() if pequeno else caja
                if pequeno:item.setSizeHint(QSize(0,180))
                texto = QLabel(f"{cliente['nombre']}\n{detalle}")
                if cliente.get("frecuente"):
                    texto.setText("★ " + texto.text() + " · Cliente frecuente")
                texto.setTextFormat(Qt.TextFormat.PlainText)
                texto.setWordWrap(True)
                caja.addWidget(texto, 1)
                barra = QPushButton('Barra' if pequeno else 'Barra · Cuenta individual')
                mesa = QPushButton('Añadir a mesa')
                for boton in (barra, mesa):
                    boton.setMinimumHeight(54)
                    acciones.addWidget(boton)
                barra.clicked.connect(lambda checked=False, i=cliente['id']: self.al_barra(i))
                mesa.clicked.connect(lambda checked=False, i=cliente['id']: self.al_mesa(i))
                if self.al_editar is not None:
                    editar=QPushButton('Editar')
                    editar.setMinimumHeight(54)
                    acciones.addWidget(editar)
                    editar.clicked.connect(lambda checked=False,i=cliente['id']:self.al_editar(i))
                if pequeno:caja.addLayout(acciones)
                self.lista.setItemWidget(item, fila)
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

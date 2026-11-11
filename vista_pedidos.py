"""Guía de la pantalla de pedidos: construye botones y dibuja las cuentas.

Este módulo solo presenta información. Las funciones al_agregar y al_cambiar
devuelven las acciones a Main.py, donde se validan y guardan los pedidos.
"""
from pathlib import Path
from PySide6.QtCore import QFile, QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QListWidgetItem, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from clientes import centimos, clave_producto
from estilos import BOTON_PRODUCTO

def cargar_pantalla(carpeta, nombre_archivo):
    archivo = QFile(str(carpeta / nombre_archivo))

    if not archivo.open(QFile.ReadOnly):
        raise RuntimeError(f"No se pudo abrir {nombre_archivo}")

    loader = QUiLoader()
    pantalla = loader.load(archivo)
    archivo.close()

    if pantalla is None:
        raise RuntimeError(loader.errorString())

    return pantalla


def crear_fila_producto(nombre, cantidad, subtotal, al_restar, al_sumar):
    fila = QWidget()
    fila.setMinimumHeight(84)

    layout = QHBoxLayout(fila)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.setSpacing(6)

    etiqueta = QLabel(
        f"{cantidad} × {nombre}\nB/.{subtotal:.2f}"
    )
    etiqueta.setMinimumWidth(0)
    etiqueta.setWordWrap(True)

    etiqueta.setStyleSheet("""
        color: white;
        font-size: 13px;
        background: transparent;
    """)

    boton_menos = QPushButton("−")
    boton_mas = QPushButton("+")

    boton_menos.setFixedSize(34, 34)
    boton_mas.setFixedSize(34, 34)

    boton_menos.setStyleSheet("""
        QPushButton {
            background-color: #8B3030;
            color: white;
            border: none;
            border-radius: 7px;
            font-size: 18px;
            font-weight: bold;
        }
    """)

    boton_mas.setStyleSheet("""
        QPushButton {
            background-color: #D4AF37;
            color: black;
            border: none;
            border-radius: 7px;
            font-size: 18px;
            font-weight: bold;
        }
    """)

    layout.addWidget(etiqueta, 1)
    layout.addWidget(boton_menos)
    layout.addWidget(boton_mas)

    boton_menos.clicked.connect(al_restar)
    boton_mas.clicked.connect(al_sumar)

    return fila


def poner_imagen_producto(boton, producto):
    ruta = producto.get("imagen")

    if not ruta or not Path(ruta).is_file():
        return

    imagen = QPixmap(ruta)
    if imagen.isNull():
        return

    boton.setText("")
    boton.setMinimumHeight(200)
    boton.setAccessibleName(
        f"{producto['nombre']}, B/.{producto['precio']:.2f}"
    )

    distribucion = QVBoxLayout(boton)
    distribucion.setContentsMargins(12, 12, 12, 12)
    distribucion.setSpacing(6)

    foto = QLabel()
    foto.setPixmap(
        imagen.scaled(
            150, 100,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
    )

    texto = QLabel(
        f"{producto['nombre']}\nB/.{producto['precio']:.2f}"
    )
    texto.setWordWrap(True)

    for etiqueta in (foto, texto):
        etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        etiqueta.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        etiqueta.setStyleSheet("""
            background: transparent;
            border: none;
            color: #F4F2ED;
            font-size: 18px;
            font-weight: bold;
            padding: 0px;
        """)
        distribucion.addWidget(etiqueta)


class CabeceraCliente(QWidget):
    """Ajusta la altura de la fila al nombre cuando cambia el ancho de la cuenta."""
    def __init__(self, item):
        super().__init__()
        self.item = item

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.layout().activate()
        tarjeta = self.layout().itemAt(0).widget()
        contenido = tarjeta.layout()
        margenes = contenido.contentsMargins()
        contenido.activate()
        nombre = contenido.itemAt(0).widget()
        importe = contenido.itemAt(1).widget()
        alto_tarjeta = (nombre.heightForWidth(max(1, nombre.width())) + importe.sizeHint().height()
                        + margenes.top() + margenes.bottom() + contenido.spacing() + 8)
        altura = max(74, alto_tarjeta + 8)
        tarjeta.setFixedHeight(altura - 8)
        if self.item.sizeHint().height() != altura:
            self.item.setSizeHint(QSize(0, altura))


def dibujar_cuenta(lista_pedido, lbl_total, productos, clientes, cliente_activo, al_cambiar,
                   al_retirar, al_seleccionar):
    lista_pedido.clear()
    grupos = {c['id']: {'nombre': c['nombre'], 'productos': []}
              for c in clientes}
    for producto in productos:
        identificador = producto.get('cliente_id')
        if identificador not in grupos:
            grupos[identificador] = {
                'nombre': producto.get('cliente_nombre') or 'Cuenta general', 'productos': []}
        grupos[identificador]['productos'].append(producto)
    if None not in grupos:
        grupos[None] = {'nombre': 'Cuenta general', 'productos': []}
    total = 0
    for identificador, grupo in grupos.items():
        subtotal_cliente = sum(centimos(p) for p in grupo['productos'])
        total += subtotal_cliente
        item = QListWidgetItem()
        cabecera = CabeceraCliente(item)
        cabecera.setObjectName('CabeceraCliente')
        fila_cabecera = QHBoxLayout(cabecera)
        fila_cabecera.setContentsMargins(4, 4, 4, 4)
        fila_cabecera.setSpacing(8)
        tarjeta = QPushButton()
        tarjeta.setAccessibleName(grupo['nombre'])
        tarjeta.setCheckable(True)
        tarjeta.setChecked(cliente_activo == identificador)
        tarjeta.setMinimumHeight(66)
        tarjeta.setStyleSheet("""
            QPushButton { background: #1C293C; border: 2px solid #34465F; border-radius: 12px; }
            QPushButton:checked { background: #343027; border-color: #E8BA68; }
            QPushButton:focus { border-color: #F6D595; }
        """)
        contenido = QVBoxLayout(tarjeta)
        contenido.setContentsMargins(16, 8, 16, 8)
        contenido.setSpacing(2)
        nombre = QLabel(grupo['nombre'])
        nombre.setWordWrap(True)
        nombre.setMinimumWidth(0)
        nombre.setTextFormat(Qt.TextFormat.PlainText)
        nombre.setStyleSheet('background: transparent; padding: 0; border: none; color: #FAF5EA; font-size: 18px; font-weight: bold;')
        importe = QLabel(f'B/.{subtotal_cliente / 100:.2f}')
        importe.setStyleSheet('background: transparent; padding: 0; border: none; color: #F2C66D; font-size: 15px;')
        importe.setFixedHeight(importe.sizeHint().height())
        for etiqueta in (nombre, importe):
            etiqueta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            contenido.addWidget(etiqueta)
        tarjeta.clicked.connect(lambda checked=False, c=identificador: al_seleccionar(c))
        fila_cabecera.addWidget(tarjeta, 1)
        if identificador is not None and not grupo['productos'] and al_retirar:
            retirar = QPushButton('Retirar')
            retirar.setObjectName('RetirarClienteMesa')
            retirar.setToolTip('Quita al cliente de esta mesa sin borrar su registro ni cobrar')
            retirar.setMinimumSize(88, 52)
            retirar.setStyleSheet('''
                QPushButton#RetirarClienteMesa { background: #303C50; color: #F4F2ED;
                    border: 1px solid #53647D; border-radius: 8px; padding: 8px 12px;
                    font-size: 14px; font-weight: bold; }
                QPushButton#RetirarClienteMesa:hover { background: #46566B; border-color: #D6AE62; }
                QPushButton#RetirarClienteMesa:pressed { background: #D6AE62; color: #101725; }
            ''')
            retirar.clicked.connect(
                lambda checked=False, c=identificador: al_retirar(c)
            )
            fila_cabecera.addWidget(retirar)
        item.setData(Qt.ItemDataRole.UserRole, identificador)
        item.setSizeHint(QSize(0, 74))
        lista_pedido.addItem(item)
        lista_pedido.setItemWidget(item, cabecera)
        cantidades = {}
        for producto in grupo['productos']:
            clave = clave_producto(producto)
            cantidades[clave] = cantidades.get(clave, 0) + 1
        if not cantidades:
            vacio = QListWidgetItem('Sin productos todavía')
            vacio.setSizeHint(QSize(0, 34))
            lista_pedido.addItem(vacio)
        for clave, cantidad in cantidades.items():
            fila = crear_fila_producto(
                clave[0], cantidad, cantidad * clave[1] / 100,
                lambda checked=False, k=clave, c=identificador: al_cambiar(k, -1, c),
                lambda checked=False, k=clave, c=identificador: al_cambiar(k, 1, c),
            )
            elemento = QListWidgetItem()
            elemento.setSizeHint(QSize(0, 88))
            lista_pedido.addItem(elemento)
            lista_pedido.setItemWidget(elemento, fila)
    lbl_total.setText(f'Total mesa: B/.{total / 100:.2f}')


def dibujar_productos(area, productos, al_agregar):
    """Único constructor del catálogo de botones, tanto al abrir como al actualizar."""
    contenedor = area.widget()
    if contenedor is None:
        contenedor = QWidget()
        area.setWidget(contenedor)
    cuadricula = contenedor.layout()
    if cuadricula is None:
        cuadricula = QGridLayout(contenedor)
        cuadricula.setSpacing(12)
        cuadricula.setContentsMargins(15, 15, 15, 15)
    while cuadricula.count():
        boton = cuadricula.takeAt(0).widget()
        if boton is not None:
            boton.hide()
            boton.deleteLater()
    for numero, producto in enumerate(productos):
        boton = QPushButton(f"{producto['nombre']}\nB/.{producto['precio']:.2f}")
        boton.setMinimumSize(190, 130)
        boton.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        boton.setStyleSheet(BOTON_PRODUCTO)
        poner_imagen_producto(boton, producto)
        boton.clicked.connect(lambda checked=False, p=producto: al_agregar(p))
        cuadricula.addWidget(boton, numero // 2, numero % 2)

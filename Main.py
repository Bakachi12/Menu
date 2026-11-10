
import sys
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta
from PySide6.QtWidgets import QComboBox, QHeaderView, QTableWidget, QTableWidgetItem
from PySide6.QtWidgets import (
    QApplication, QGridLayout, QVBoxLayout,
    QStackedWidget, QPushButton, QSizePolicy, QLineEdit,
    QWidget, QLabel, QScrollArea, QListWidget, QHBoxLayout, QListWidgetItem
)

from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QFile, QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QInputDialog
app = QApplication(sys.argv)

# Carpeta donde están los archivos
carpeta = Path(__file__).resolve().parent

# Datos persistentes separados de las pantallas y del ejecutable.
from PySide6.QtCore import QStandardPaths


def preparar_archivo_datos():
    from contextlib import closing
    from uuid import uuid4

    carpeta_datos = Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.GenericDataLocation
    )) / "TPVBar"
    carpeta_datos.mkdir(parents=True, exist_ok=True)
    destino = carpeta_datos / "ventas.db"

    # Una actualización nunca sustituye una base de datos que ya existe.
    if destino.exists():
        return destino

    carpeta_anterior = (Path(sys.executable).resolve().parent
                        if getattr(sys, "frozen", False) else carpeta)
    anterior = carpeta_anterior / "ventas.db"
    if not anterior.exists():
        return destino

    temporal = carpeta_datos / f"migracion-{uuid4().hex}.db"
    try:
        # SQLite backup conserva una copia coherente, incluido el diario WAL.
        with closing(sqlite3.connect(anterior.as_uri() + "?mode=ro", uri=True)) as origen:
            with closing(sqlite3.connect(str(temporal))) as copia:
                origen.backup(copia)
                if copia.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("La copia de la base de datos no pasó la comprobación.")
        # En Windows rename no sobrescribe un destino creado por otro proceso.
        try:
            temporal.rename(destino)
        except FileExistsError:
            pass
    finally:
        if temporal.exists():
            temporal.unlink()

    # La base original se conserva como respaldo.
    return destino


try:
    ruta_base_datos = preparar_archivo_datos()
except (OSError, sqlite3.Error, RuntimeError) as error:
    QMessageBox.critical(
        None, "No se pudieron preparar los datos",
        f"No se abrirá el TPV para evitar usar una base vacía.\n{error}"
    )
    sys.exit(1)


# Cargar la pantalla principal
def cargar_ui(nombre_archivo):
    archivo = QFile(str(carpeta / nombre_archivo))

    if not archivo.open(QFile.ReadOnly):
        raise RuntimeError(f"No se pudo abrir {nombre_archivo}")

    loader = QUiLoader()
    pantalla = loader.load(archivo)
    archivo.close()

    if pantalla is None:
        raise RuntimeError(loader.errorString())

    return pantalla
#---------------------------------------------------------------------------------------------------------------------------------

ventana = cargar_ui("inicio.ui")
ventana.setMinimumSize(0, 0)
pantalla_principal = app.primaryScreen()
if pantalla_principal is None:
    raise RuntimeError("No se encontró una pantalla disponible")

area_disponible = pantalla_principal.availableGeometry()
ventana.resize(
    min(ventana.width(), area_disponible.width()),
    min(ventana.height(), area_disponible.height())
)
# Sistema de navegación
paginas = ventana.findChild(QStackedWidget, "PaginasPrincipal")
pagina_mesas = ventana.findChild(QWidget, "PaginaMesas")
pagina_pedido = ventana.findChild(QWidget, "PaginaPedido")
pagina_cobro = ventana.findChild(QWidget, "PaginaCobro")
pagina_historial = ventana.findChild(QWidget, "PaginaHistorial")
tabla_historial = ventana.findChild(
    QTableWidget, "tablaHistorial"
)
txt_buscar_historial = ventana.findChild(
    QLineEdit, "txtBuscarHistorial"
)
btn_historial_hoy = ventana.findChild(
    QPushButton, "btnHistorialHoy"
)

btn_historial_semana = ventana.findChild(
    QPushButton, "btnHistorialSemana"
)

cmb_mes_historial = ventana.findChild(
    QComboBox, "cmbMesHistorial"
)
cmb_anio_historial = ventana.findChild(
    QComboBox, "cmbAnioHistorial"
)

if any(b is None for b in (
    btn_historial_hoy,
    btn_historial_semana,
    cmb_mes_historial,
    cmb_anio_historial
)):
    raise RuntimeError("No se encontraron los filtros de fecha del historial")
if txt_buscar_historial is None:
    raise RuntimeError("No se encontró txtBuscarHistorial")

if tabla_historial is None:
    raise RuntimeError("No se encontró tablaHistorial")

tabla_historial.setColumnCount(5)
tabla_historial.verticalHeader().setVisible(False)

if pagina_historial is None:
    raise RuntimeError("No se encontró PaginaHistorial")

contenedor_filtros_historial = btn_historial_hoy.parentWidget()
if any(
    boton.parentWidget() is not contenedor_filtros_historial
    for boton in (btn_historial_semana, cmb_mes_historial, cmb_anio_historial)
):
    raise RuntimeError("Los filtros de fecha deben compartir un contenedor")

layout_historial = pagina_historial.layout()
if layout_historial is None:
    layout_historial = QVBoxLayout(pagina_historial)
    layout_historial.setContentsMargins(10, 10, 10, 10)

if layout_historial.indexOf(txt_buscar_historial) == -1:
    layout_historial.insertWidget(0, txt_buscar_historial)

if layout_historial.indexOf(contenedor_filtros_historial) == -1:
    layout_historial.insertWidget(1, contenedor_filtros_historial)

if layout_historial.indexOf(tabla_historial) == -1:
    layout_historial.addWidget(tabla_historial)

txt_buscar_historial.setSizePolicy(
    QSizePolicy.Policy.Expanding,
    QSizePolicy.Policy.Fixed
)
tabla_historial.setSizePolicy(
    QSizePolicy.Policy.Expanding,
    QSizePolicy.Policy.Expanding
)
tabla_historial.horizontalHeader().setSectionResizeMode(
    QHeaderView.ResizeMode.Stretch
)
tabla_historial.setStyleSheet("""
    QTableWidget {
        background-color: #292938;
        alternate-background-color: #343446;
        color: white;
        border: none;
        gridline-color: #414154;
        font-size: 14px;
        selection-background-color: #D4AF37;
        selection-color: #20202B;
    }

    QHeaderView::section {
        background-color: #414154;
        color: #D4AF37;
        padding: 10px;
        border: none;
        font-weight: bold;
    }

    QTableWidget::item {
        padding: 8px;
    }
""")

contenedor_cobro = ventana.findChild(
    QWidget, "ContenedorCobro"
)
layout_cobro = QVBoxLayout(contenedor_cobro)
contenedor_cobro.setMinimumHeight(420)
layout_cobro.setContentsMargins(0, 0, 0, 0)
if paginas is None or pagina_mesas is None or pagina_pedido is None:
    raise RuntimeError("No se encontraron las páginas de navegación")

# Preparar la página de pedidos
layout_pedido = pagina_pedido.layout()

if layout_pedido is None:
    layout_pedido = QVBoxLayout(pagina_pedido)
    layout_pedido.setContentsMargins(0, 0, 0, 0)

# Mostrar las mesas al iniciar
paginas.setCurrentWidget(pagina_mesas)
# Botón para regresar a las mesas

# Navegación desde el menú lateral
btn_menu_mesas = ventana.findChild(QPushButton, "btnMenuMesas")
titulo_pagina = ventana.findChild(QLabel, "label")

if btn_menu_mesas is None:
    raise RuntimeError("No se encontró btnMenuMesas")
if titulo_pagina is None:
    raise RuntimeError("No se encontró el título de la página")

def abrir_mesas():
    titulo_pagina.setText("Gestión de pedidos")
    paginas.setCurrentWidget(pagina_mesas)


btn_menu_mesas.clicked.connect(abrir_mesas)
btn_menu_historial = ventana.findChild(
    QPushButton, "btnMenuHistorial"
)

if btn_menu_historial is None:
    btn_menu_historial = ventana.findChild(QPushButton, "pushButton_4")

if btn_menu_historial is None:
    btn_menu_historial = next(
        (
            boton for boton in ventana.findChildren(QPushButton)
            if boton.text().strip().casefold() == "historial"
        ),
        None
    )

if btn_menu_historial is None:
    raise RuntimeError("No se encontró el botón de Historial en inicio.ui")
filtro_fecha_historial = None
nombres_meses_historial = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]
cmb_mes_historial.clear()
cmb_mes_historial.addItem("Todos los meses", None)
for numero_mes, nombre_mes in enumerate(nombres_meses_historial, start=1):
    cmb_mes_historial.addItem(nombre_mes, numero_mes)

cmb_anio_historial.clear()
cmb_anio_historial.addItem("Todos los años", None)
cmb_anio_historial.addItem(str(datetime.now().year), datetime.now().year)


def aplicar_filtros_historial():
    texto = txt_buscar_historial.text().strip().casefold()
    hoy = datetime.now().date()
    mes_seleccionado = cmb_mes_historial.currentData()
    anio_seleccionado = cmb_anio_historial.currentData()

    for fila in range(tabla_historial.rowCount()):
        coincide_texto = not texto

        for columna in (0, 2, 3):
            elemento = tabla_historial.item(fila, columna)

            if elemento and texto in elemento.text().casefold():
                coincide_texto = True
                break

        coincide_fecha = True
        if (
            filtro_fecha_historial is not None
            or mes_seleccionado is not None
            or anio_seleccionado is not None
        ):
            elemento_fecha = tabla_historial.item(fila, 1)
            try:
                fecha_venta = datetime.strptime(
                    elemento_fecha.text(), "%Y-%m-%d %H:%M:%S"
                ).date()
            except (AttributeError, ValueError):
                coincide_fecha = False
            else:
                if filtro_fecha_historial == "hoy":
                    coincide_fecha = fecha_venta == hoy
                elif filtro_fecha_historial == "semana":
                    coincide_fecha = hoy - timedelta(days=6) <= fecha_venta <= hoy
                else:
                    coincide_fecha = (
                        (mes_seleccionado is None or fecha_venta.month == mes_seleccionado)
                        and (anio_seleccionado is None or fecha_venta.year == anio_seleccionado)
                    )

        tabla_historial.setRowHidden(
            fila, not (coincide_texto and coincide_fecha)
        )


def seleccionar_filtro_fecha_historial(periodo):
    print("FILTRO SELECCIONADO:", periodo)
    global filtro_fecha_historial
    filtro_fecha_historial = periodo

    for boton in (btn_historial_hoy, btn_historial_semana):
        boton.setCheckable(True)
        boton.setChecked(boton is {
            "hoy": btn_historial_hoy,
            "semana": btn_historial_semana,
        }[periodo])

    for combo in (cmb_mes_historial, cmb_anio_historial):
        bloquear_senales = combo.blockSignals(True)
        combo.setCurrentIndex(0)
        combo.blockSignals(bloquear_senales)

    aplicar_filtros_historial()


def seleccionar_filtro_personalizado_historial(indice):
    global filtro_fecha_historial
    filtro_fecha_historial = None
    btn_historial_hoy.setChecked(False)
    btn_historial_semana.setChecked(False)
    aplicar_filtros_historial()


txt_buscar_historial.textChanged.connect(aplicar_filtros_historial)
cmb_mes_historial.currentIndexChanged.connect(
    seleccionar_filtro_personalizado_historial
)
cmb_anio_historial.currentIndexChanged.connect(
    seleccionar_filtro_personalizado_historial
)
btn_historial_hoy.clicked.connect(
    lambda: seleccionar_filtro_fecha_historial("hoy")
)
btn_historial_semana.clicked.connect(
    lambda: seleccionar_filtro_fecha_historial("semana")
)


def abrir_historial():
    cargar_historial()
    titulo_pagina.setText("Historial")
    paginas.setCurrentWidget(pagina_historial)


btn_menu_historial.clicked.connect(abrir_historial)
# Guardar los pedidos por mesa
ventanas_pedido = {}
pedidos = {}
nombres_mesas = {}
filtro_mesas_actual = "todas"
productos = [
    {"nombre": "Café", "precio": 2.50},
    {"nombre": "Hamburguesa", "precio": 6.50},
    {"nombre": "Jugo natural", "precio": 3.00},
]

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

def actualizar_cuenta(nombre_mesa, lista_pedido, lbl_total):
    lista_pedido.clear()

    cantidades = {}
    total = 0.0

    for producto in pedidos.get(nombre_mesa, []):
        nombre = producto["nombre"]

        if nombre not in cantidades:
            cantidades[nombre] = {
                "cantidad": 0,
                "precio": producto["precio"]
            }

        cantidades[nombre]["cantidad"] += 1

    for nombre, datos in cantidades.items():
        cantidad = datos["cantidad"]
        precio = datos["precio"]
        subtotal = cantidad * precio
        total += subtotal

        # Crear la fila de la cuenta
        fila = crear_fila_producto(
            nombre,
            cantidad,
            subtotal,
            lambda checked=False, n=nombre: cambiar_cantidad(
                nombre_mesa, n, -1, lista_pedido, lbl_total
            ),
            lambda checked=False, n=nombre: cambiar_cantidad(
                nombre_mesa, n, 1, lista_pedido, lbl_total
            )
        )

        elemento = QListWidgetItem()
        elemento.setSizeHint(QSize(0, 88))

        lista_pedido.addItem(elemento)
        lista_pedido.setItemWidget(elemento, fila)

    lbl_total.setText(f"Total: B/.{total:.2f}")


def cambiar_cantidad(nombre_mesa, nombre_producto, cambio, lista_pedido, lbl_total):
    cuenta = pedidos.get(nombre_mesa, [])

    if cambio == -1:
        # Quitar una unidad
        for indice, producto in enumerate(cuenta):
            if producto["nombre"] == nombre_producto:
                cuenta.pop(indice)
                break

    elif cambio == 1:
        # Agregar una unidad del mismo producto
        for producto in cuenta:
            if producto["nombre"] == nombre_producto:
                cuenta.append(producto.copy())
                break

    actualizar_cuenta(nombre_mesa, lista_pedido, lbl_total)
    filtrar_mesas(filtro_mesas_actual)


def agregar_producto(nombre_mesa, producto, lista_pedido, lbl_total):
    if nombre_mesa not in pedidos:
        pedidos[nombre_mesa] = []

    pedidos[nombre_mesa].append(producto.copy())
    actualizar_cuenta(nombre_mesa, lista_pedido, lbl_total)
    filtrar_mesas(filtro_mesas_actual)

def editar_nombre_desde_pedido(nombre_mesa):
    # Buscar el botón original de la mesa
    indice = mesas.index(nombre_mesa)
    boton_mesa = botones_mesas[indice]

    # Abrir la ventana para escribir el nombre
    asignar_nombre_mesa(nombre_mesa, boton_mesa)

    # Actualizar el nombre en la pantalla del pedido
    pantalla = ventanas_pedido[nombre_mesa]
    etiqueta = pantalla.findChild(QLabel, "lblMesa")

    if etiqueta is not None:
        nombre_cliente = nombres_mesas.get(nombre_mesa, "")

        if nombre_cliente:
            etiqueta.setText(f"{nombre_mesa} - {nombre_cliente}")
        else:
            etiqueta.setText(nombre_mesa)
def preparar_base_datos():
    conexion = sqlite3.connect(str(ruta_base_datos))

    conexion.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            mesa TEXT NOT NULL,
            cliente TEXT,
            productos TEXT NOT NULL,
            total REAL NOT NULL
        )
    """)
    conexion.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio_centimos INTEGER NOT NULL CHECK (precio_centimos > 0),
            categoria TEXT NOT NULL DEFAULT 'General',
            UNIQUE(nombre, categoria)
        )
    """)
    columnas = {
        fila[1]
        for fila in conexion.execute("PRAGMA table_info(productos)")
    }

    if "activo" not in columnas:
        conexion.execute("""
            ALTER TABLE productos
            ADD COLUMN activo INTEGER NOT NULL DEFAULT 1
        """)
    if "imagen" not in columnas:
        conexion.execute("""
            ALTER TABLE productos
            ADD COLUMN imagen TEXT
        """)
    conexion.commit()
    conexion.close()
def migrar_productos_iniciales():
    preparar_base_datos()

    with sqlite3.connect(str(ruta_base_datos)) as conexion:
        for producto in productos:
            conexion.execute(
                """
                INSERT INTO productos (nombre, precio_centimos, categoria)
                VALUES (?, ?, ?)
                ON CONFLICT(nombre, categoria) DO NOTHING
                """,
                (
                    producto["nombre"],
                    round(producto["precio"] * 100),
                    "General"
                )
            )


migrar_productos_iniciales()
def cargar_productos():
    with sqlite3.connect(str(ruta_base_datos)) as conexion:
        filas = conexion.execute("""
            SELECT nombre, precio_centimos, categoria, imagen
            FROM productos
            WHERE activo = 1
            ORDER BY id
        """).fetchall()

    return [
        {
            "nombre": nombre,
            "precio": precio_centimos / 100,
            "categoria": categoria,
            "imagen": imagen
        }
        for nombre, precio_centimos, categoria, imagen in filas
    ]
    with sqlite3.connect(str(ruta_base_datos)) as conexion:
        filas = conexion.execute("""
            SELECT nombre, precio_centimos, categoria
            FROM productos
            WHERE activo = 1
            ORDER BY id
        """).fetchall()

    return [
        {
            "nombre": nombre,
            "precio": precio_centimos / 100,
            "categoria": categoria
        }
        for nombre, precio_centimos, categoria in filas
    ]


productos = cargar_productos()
import json

def guardar_venta(nombre_mesa):
    preparar_base_datos()

    productos_mesa = pedidos.get(nombre_mesa, [])
    cliente = nombres_mesas.get(nombre_mesa, "")
    total = sum(p["precio"] for p in productos_mesa)

    conexion = sqlite3.connect(str(ruta_base_datos))

    conexion.execute(
        """
        INSERT INTO ventas (fecha, mesa, cliente, productos, total)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            nombre_mesa,
            cliente,
            json.dumps(productos_mesa, ensure_ascii=False),
            total
        )
    )

    conexion.commit()
    conexion.close()
    print("VENTA GUARDADA CORRECTAMENTE:", nombre_mesa)


def finalizar_cobro(nombre_mesa):
    # Primero guardar la venta en SQLite
    if not pedidos.get(nombre_mesa):
        QMessageBox.warning(
            ventana, "Cuenta vacía",
            "No hay productos para cobrar."
        )
        return

    guardar_venta(nombre_mesa)

    # Limpiar los productos y el nombre temporal
    pedidos[nombre_mesa] = []
    nombres_mesas.pop(nombre_mesa, None)

    # Restaurar el nombre original de la mesa
    indice = mesas.index(nombre_mesa)
    botones_mesas[indice].setText(nombre_mesa)

    # Actualizar la cuenta visualmente
    pantalla = ventanas_pedido[nombre_mesa]
    pantalla.findChild(QLabel, "lblMesa").setText(nombre_mesa)

    lista = pantalla.findChild(QListWidget, "Listapedido")
    total = pantalla.findChild(QLabel, "lblTotal")

    actualizar_cuenta(nombre_mesa, lista, total)

    # Regresar a la pantalla de mesas
    paginas.setCurrentWidget(pagina_mesas)
    filtrar_mesas(filtro_mesas_actual)


def cargar_historial():
    tabla_historial.setRowCount(0)

    ruta_db = ruta_base_datos

    if not ruta_db.exists():
        actualizar_anios_historial([])
        return

    conexion = sqlite3.connect(str(ruta_db))

    ventas = conexion.execute("""
        SELECT id, fecha, cliente, mesa, total
        FROM ventas
        ORDER BY id DESC
    """).fetchall()

    conexion.close()
    actualizar_anios_historial(ventas)

    tabla_historial.setRowCount(len(ventas))

    for fila, venta in enumerate(ventas):
        for columna, valor in enumerate(venta):
            if columna == 4:
                texto = f"B/.{valor:.2f}"
            else:
                texto = str(valor) if valor is not None else ""

            tabla_historial.setItem(
                fila,
                columna,
                QTableWidgetItem(texto)
            )

    aplicar_filtros_historial()


def actualizar_anios_historial(ventas):
    valor_actual = cmb_anio_historial.currentData()
    anios = {datetime.now().year}

    for venta in ventas:
        try:
            anios.add(datetime.strptime(venta[1], "%Y-%m-%d %H:%M:%S").year)
        except (TypeError, ValueError):
            continue

    bloquear_senales = cmb_anio_historial.blockSignals(True)
    cmb_anio_historial.clear()
    cmb_anio_historial.addItem("Todos los años", None)

    for anio in sorted(anios, reverse=True):
        cmb_anio_historial.addItem(str(anio), anio)

    indice_actual = cmb_anio_historial.findData(valor_actual)
    cmb_anio_historial.setCurrentIndex(max(indice_actual, 0))
    cmb_anio_historial.blockSignals(bloquear_senales)

def cobrar_mesa(nombre_mesa):
    preparar_base_datos()
    print("BOTÓN COBRAR ACTIVADO:", nombre_mesa)

    dialogo = cargar_ui("confirmar_cobro.ui")

    dialogo.setMinimumSize(0, 0)
    dialogo.setMaximumSize(16777215, 16777215)

    while layout_cobro.count():
        elemento = layout_cobro.takeAt(0)
        if elemento.widget():
            elemento.widget().deleteLater()

    layout_cobro.addWidget(dialogo)
    print("Total:", dialogo.findChild(QLabel, "lblTotalCobro"))
    print("Confirmar:", dialogo.findChild(QPushButton, "btnConfirmarCobro"))
    print("Cancelar:", dialogo.findChild(QPushButton, "btnCancelarCobro"))

    dialogo.findChild(QLabel, "lblMesaCobro").setText(nombre_mesa)

    nombre_cliente = nombres_mesas.get(nombre_mesa, "")
    dialogo.findChild(QLabel, "lblClienteCobro").setText(
        f"Cliente: {nombre_cliente or 'Sin asignar'}"
    )

    total_cobro = sum(
        producto["precio"] for producto in pedidos.get(nombre_mesa, [])
    )
    lbl_total_cobro = dialogo.findChild(QLabel, "lblTotalCobro")
    if lbl_total_cobro is None:
        raise RuntimeError("No se encontró lblTotalCobro en confirmar_cobro.ui")
    lbl_total_cobro.setText(f"Total: B/.{total_cobro:.2f}")

    btn_cancelar = dialogo.findChild(
        QPushButton, "btnCancelarCobro"
    )

    btn_confirmar = dialogo.findChild(
        QPushButton, "btnConfirmarCobro"
    )

    btn_cancelar.clicked.connect(
    lambda checked=False: paginas.setCurrentWidget(pagina_pedido)
)
    btn_confirmar.clicked.connect(
        lambda checked=False: finalizar_cobro(nombre_mesa)
    )

    paginas.setCurrentWidget(pagina_cobro)
    print("Formulario:", dialogo.size())
    print("Contenedor:", contenedor_cobro.size())
    print("Total:", dialogo.findChild(QLabel, "lblTotalCobro").geometry())
    print("Confirmar:", dialogo.findChild(QPushButton, "btnConfirmarCobro").geometry())
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
def actualizar_botones_productos():
    for nombre_mesa, pantalla in ventanas_pedido.items():
        area = pantalla.findChild(QScrollArea, "AreaProductos")
        cuadricula = area.widget().layout()

        lista = (
            pantalla.findChild(QListWidget, "Listapedido")
            or pantalla.findChild(QListWidget, "ListaPedido")
            or pantalla.findChild(QListWidget, "listapedido")
        )
        total = pantalla.findChild(QLabel, "lblTotal")

        while cuadricula.count():
            elemento = cuadricula.takeAt(0)
            boton = elemento.widget()
            if boton is not None:
                boton.hide()
                boton.deleteLater()

        for numero, producto in enumerate(productos):
            boton = QPushButton(
                f"{producto['nombre']}\nB/.{producto['precio']:.2f}"
            )
            boton.setMinimumSize(190, 130)
            poner_imagen_producto(boton, producto)
            boton.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed
            )
            boton.setStyleSheet("""
                QPushButton {
                    background-color: #1B2537;
                    color: #F4F2ED;
                    border: 1px solid #354159;
                    border-radius: 14px;
                    font-size: 18px;
                    font-weight: bold;
                    padding: 18px;
                }
                QPushButton:hover {
                    background-color: #26344B;
                    color: #F2C66D;
                    border: 1px solid #D6A74C;
                }
            """)
            cuadricula.addWidget(boton, numero // 2, numero % 2)
            boton.clicked.connect(
                lambda checked=False, p=producto,
                mesa=nombre_mesa, listado=lista, etiqueta=total:
                agregar_producto(mesa, p, listado, etiqueta)
            )
def abrir_pedido(nombre_mesa):
    if nombre_mesa in ventanas_pedido:
        for pantalla in ventanas_pedido.values():
            pantalla.hide()

        ventanas_pedido[nombre_mesa].show()
        paginas.setCurrentWidget(pagina_pedido)
        return

    pantalla_pedido = cargar_ui("pedido.ui")
    pantalla_pedido.setWindowTitle(f"Pedido - {nombre_mesa}")

    etiqueta = (
        pantalla_pedido.findChild(QLabel, "lblMesa")
        or pantalla_pedido.findChild(QLabel, "lblmesa")
    )

    if etiqueta is not None:
        etiqueta.setText(nombre_mesa)

    btn_editar_nombre = pantalla_pedido.findChild(
        QPushButton, "btnEditarNombre"
    )

    if btn_editar_nombre is not None:
        btn_editar_nombre.clicked.connect(
            lambda checked=False: editar_nombre_desde_pedido(nombre_mesa)
        )

    btn_cobrar = pantalla_pedido.findChild(
        QPushButton, "btnCobrar"
    )

    if btn_cobrar is not None:
        btn_cobrar.clicked.connect(
            lambda checked=False: cobrar_mesa(nombre_mesa)
        )
    area_productos = pantalla_pedido.findChild(QScrollArea, "AreaProductos")
    if area_productos is None:
        raise RuntimeError("No se encontró AreaProductos")

    contenedor_productos = QWidget()
    cuadricula_productos = QGridLayout(contenedor_productos)
    cuadricula_productos.setSpacing(12)
    cuadricula_productos.setContentsMargins(15, 15, 15, 15)

    area_productos.setWidgetResizable(True)
    from PySide6.QtWidgets import QScroller

    area_productos.setVerticalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    area_productos.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )

    QScroller.grabGesture(
        area_productos.viewport(),
        QScroller.ScrollerGestureType.TouchGesture
    )
    area_productos.setWidget(contenedor_productos)
    area_productos.setStyleSheet("""
        QScrollArea {
            background-color: #0B1020;
            border: none;
        }

        QScrollArea > QWidget > QWidget {
            background-color: #0B1020;
        }
    """)

    lista_pedido = (
        pantalla_pedido.findChild(QListWidget, "Listapedido")
        or pantalla_pedido.findChild(QListWidget, "ListaPedido")
        or pantalla_pedido.findChild(QListWidget, "listapedido")
    )
    lbl_total = pantalla_pedido.findChild(QLabel, "lblTotal")

    if lista_pedido is None or lbl_total is None:
        raise RuntimeError("No se encontró Listapedido o lblTotal")

    if nombre_mesa not in pedidos:
        pedidos[nombre_mesa] = []

    for numero, producto in enumerate(productos):
        boton_producto = QPushButton(f"{producto['nombre']}\nB/.{producto['precio']:.2f}")
        boton_producto.setMinimumSize(190, 130)
        poner_imagen_producto(boton_producto, producto)
        boton_producto.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        boton_producto.setStyleSheet("""
            QPushButton {
                background-color: #1B2537;
                color: #F4F2ED;
                border: 1px solid #354159;
                border-radius: 14px;
                font-size: 18px;
                font-weight: bold;
                padding: 18px;
            }

            QPushButton:hover {
                background-color: #26344B;
                color: #F2C66D;
                border: 1px solid #D6A74C;
            }
        """)

        fila = numero // 2
        columna = numero % 2
        cuadricula_productos.addWidget(boton_producto, fila, columna)
        boton_producto.clicked.connect(
            lambda checked=False,
            p=producto,
            mesa=nombre_mesa,
            lista=lista_pedido,
            total_label=lbl_total: agregar_producto(mesa, p, lista, total_label)
        )

    # Ocultar el pedido anterior
    for pantalla in ventanas_pedido.values():
        pantalla.hide()

    # Insertar la pantalla dentro de la página
    layout_pedido.addWidget(pantalla_pedido)

    ventanas_pedido[nombre_mesa] = pantalla_pedido

    # Mostrar la página de pedidos
    pantalla_pedido.show()
    paginas.setCurrentWidget(pagina_pedido)


# Buscar el área de mesas
# Buscar el área de mesas
area = ventana.findChild(QScrollArea, "AreaMesas")

# Comprobar que existe
if area is None:
    raise RuntimeError("No se encontró AreaMesas")

# Obtener la distribución de la página
distribucion_mesas = pagina_mesas.layout()

# Crear una distribución si no existe
if distribucion_mesas is None:
    distribucion_mesas = QVBoxLayout(pagina_mesas)

# Eliminar márgenes y espacios
distribucion_mesas.setContentsMargins(0, 0, 0, 0)
distribucion_mesas.setSpacing(0)

# Incorporar AreaMesas a la distribución
if distribucion_mesas.indexOf(area) == -1:
    distribucion_mesas.addWidget(area)

# Permitir que el contenido se adapte al tamaño
area.setWidgetResizable(True)

# Contenedor de las mesas
contenedor = QWidget()
cuadricula = QGridLayout(contenedor)

cuadricula.setSpacing(12)
cuadricula.setContentsMargins(15, 15, 15, 15)

area.setWidget(contenedor)
# Prueba visual temporal
area.setStyleSheet("""
    QScrollArea {
        background-color: #292938;
        border: 3px solid red;
    }
""")
# Fondo oscuro del área de mesas
area.setStyleSheet("""
    QScrollArea {
        background-color: #292938;
        border: none;
    }

    QScrollArea > QWidget > QWidget {
        background-color: #292938;
    }
""")

contenedor.setStyleSheet("""
    background-color: #292938;
""")

# Crear mesas
mesas = ["Mesa 01", "Mesa 02", "Mesa 03", "Mesa 04"]
botones_mesas = []
def asignar_nombre_mesa(nombre_mesa, boton):
    nombre_actual = nombres_mesas.get(nombre_mesa, "")

    nombre, aceptado = QInputDialog.getText(
        ventana,
        "Nombre de la mesa",
        f"Escribe el nombre para {nombre_mesa}:",
        text=nombre_actual
    )

    if aceptado:
        nombre = nombre.strip()

        if nombre:
            nombres_mesas[nombre_mesa] = nombre
            boton.setText(f"{nombre_mesa}\n{nombre}")
        else:
            nombres_mesas.pop(nombre_mesa, None)
            boton.setText(nombre_mesa)


def seleccionar_mesa(boton_actual):
    for boton in botones_mesas:
        boton.setChecked(boton is boton_actual)


for numero, nombre in enumerate(mesas):
    boton = QPushButton(nombre)

    boton.setContextMenuPolicy(
        Qt.ContextMenuPolicy.CustomContextMenu
    )

    boton.customContextMenuRequested.connect(
        lambda posicion, mesa=nombre, btn=boton:
            asignar_nombre_mesa(mesa, btn)
    )

    boton.setCheckable(True)
    boton.setAutoExclusive(True)
    boton.setMinimumSize(150, 110)

    boton.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding
    )

    boton.setStyleSheet("""
        QPushButton {
            background-color: #414154;
            color: white;
            border: 1px solid #55556A;
            border-radius: 12px;
            font-size: 17px;
            font-weight: bold;
            padding: 10px;
        }

        QPushButton:hover {
            background-color: #D4AF37;
            color: black;
        }

        QPushButton:pressed {
            background-color: #C9A228;
            color: black;
        }

        QPushButton:checked {
            background-color: #D4AF37;
            color: black;
            border: 1px solid #E8C65A;
        }
    """)

    botones_mesas.append(boton)

    fila = numero // 2
    columna = numero % 2

    cuadricula.addWidget(boton, fila, columna)

    # Abrir el pedido al pulsar la mesa
    boton.clicked.connect(
        lambda checked=False, mesa=nombre, btn=boton: (
            seleccionar_mesa(btn),
            abrir_pedido(mesa)
        )
    )

# Repartir el espacio entre las cuatro mesas
cuadricula.setRowStretch(0, 1)
cuadricula.setRowStretch(1, 1)

cuadricula.setColumnStretch(0, 1)
cuadricula.setColumnStretch(1, 1)
# Buscar los botones de filtros
btn_todas = ventana.findChild(QPushButton, "btnTodas")
btn_disponibles = ventana.findChild(QPushButton, "btnDisponibles")
btn_ocupadas = ventana.findChild(QPushButton, "btnOcupadas")

print("Todas:", btn_todas)
print("Disponibles:", btn_disponibles)
print("Ocupadas:", btn_ocupadas)
# Obtener la distribución original de los filtros
distribucion_original = ventana.findChild(
    QHBoxLayout, "horizontalLayout_3"
)

if distribucion_original is None:
    raise RuntimeError("No se encontró horizontalLayout_3")

# Sacar los botones de su distribución anterior
for boton in (btn_todas, btn_disponibles, btn_ocupadas):
    distribucion_original.removeWidget(boton)
    boton.setParent(pagina_mesas)

# Crear una nueva fila dentro de PaginaMesas
fila_filtros = QHBoxLayout()
fila_filtros.setSpacing(8)

fila_filtros.addWidget(btn_todas)
fila_filtros.addWidget(btn_disponibles)
fila_filtros.addWidget(btn_ocupadas)

# Colocar la fila encima de AreaMesas
distribucion_mesas.insertLayout(0, fila_filtros)
# Mostrar filtros solo en la pantalla de mesas
def mostrar_filtros(visibles):
    btn_todas.setVisible(visibles)
    btn_disponibles.setVisible(visibles)
    btn_ocupadas.setVisible(visibles)

# Actualizar los filtros cuando cambiamos de página
paginas.currentChanged.connect(
    lambda indice: mostrar_filtros(
        paginas.currentWidget() is pagina_mesas
    )
)

# Aplicar el estado inicial
mostrar_filtros(paginas.currentWidget() is pagina_mesas)
if any(b is None for b in (btn_todas, btn_disponibles, btn_ocupadas)):
    raise RuntimeError("Revisa los objectName en Qt Designer")


# Filtrar las mesas según sus pedidos
def filtrar_mesas(filtro):
    global filtro_mesas_actual
    filtro_mesas_actual = filtro

    mesas_visibles = []

    # Determinar qué mesas deben mostrarse
    for nombre_mesa, boton in zip(mesas, botones_mesas):
        ocupada = len(pedidos.get(nombre_mesa, [])) > 0

        mostrar = (
            filtro == "todas"
            or (filtro == "disponibles" and not ocupada)
            or (filtro == "ocupadas" and ocupada)
        )

        boton.setVisible(mostrar)

        if mostrar:
            mesas_visibles.append(boton)

    # Reorganizar las mesas visibles
    for posicion, boton in enumerate(mesas_visibles):
        fila = posicion // 2
        columna = posicion % 2

        cuadricula.addWidget(boton, fila, columna)


# Conectar los botones
btn_todas.clicked.connect(
    lambda: filtrar_mesas("todas")
)

btn_disponibles.clicked.connect(
    lambda: filtrar_mesas("disponibles")
)

btn_ocupadas.clicked.connect(
    lambda: filtrar_mesas("ocupadas")
)
print("PanelPrincipal:", ventana.findChild(QWidget, "PanelPrincipal").size())
print("PaginasPrincipal:", paginas.size())
print("AreaMesas:", area.size())
print("Contenedor de mesas:", contenedor.size())
# Pantalla de configuración
pagina_configuracion = QWidget()
pagina_configuracion.setObjectName("PaginaConfiguracion")
pagina_configuracion.setStyleSheet("""
    QWidget#PaginaConfiguracion {
        background-color: #0B1020;
        color: #F4F2ED;
    }
    QWidget#PaginaConfiguracion QLabel {
        color: #F4F2ED;
        font-size: 24px;
        font-weight: bold;
        background: transparent;
    }
    QWidget#PaginaConfiguracion QPushButton {
        background-color: #1B2537;
        color: #E9E8E3;
        border: 1px solid #303C52;
        border-radius: 10px;
        padding: 14px 18px;
        font-size: 15px;
        font-weight: 600;
        text-align: left;
    }
    QWidget#PaginaConfiguracion QPushButton:hover {
        background-color: #28354A;
        color: #F2C66D;
        border-color: #D6A74C;
    }
    QWidget#PaginaConfiguracion QPushButton:pressed {
        background-color: #D4AF37;
        color: #111827;
    }
""")
layout_configuracion = QVBoxLayout(pagina_configuracion)
layout_configuracion.setContentsMargins(24, 24, 24, 24)
layout_configuracion.setSpacing(16)

titulo_configuracion = QLabel("Configuración")
layout_configuracion.addWidget(titulo_configuracion)

btn_abrir_productos = QPushButton("Productos")
layout_configuracion.addWidget(btn_abrir_productos)
layout_configuracion.addStretch()

paginas.addWidget(pagina_configuracion)

btn_menu_configuracion = ventana.findChild(
    QPushButton, "btnMenuConfiguracion"
)
btn_menu_configuracion.clicked.connect(
    lambda: paginas.setCurrentWidget(pagina_configuracion)
)
# Pantalla de productos
pagina_productos = QWidget()
layout_productos = QVBoxLayout(pagina_productos)

layout_productos.addWidget(QLabel("Crear producto"))

layout_productos.addWidget(QLabel("Nombre"))
txt_nombre_producto = QLineEdit()
layout_productos.addWidget(txt_nombre_producto)

layout_productos.addWidget(QLabel("Precio (B/.)"))
txt_precio_producto = QLineEdit()
txt_precio_producto.setPlaceholderText("Ejemplo: 2.50")
layout_productos.addWidget(txt_precio_producto)

layout_productos.addWidget(QLabel("Categoría"))
txt_categoria_producto = QLineEdit()
txt_categoria_producto.setPlaceholderText("Ejemplo: Bebidas")
layout_productos.addWidget(txt_categoria_producto)

btn_guardar_producto = QPushButton("Guardar")
layout_productos.addWidget(btn_guardar_producto)
layout_productos.addStretch()

paginas.addWidget(pagina_productos)

btn_abrir_productos.clicked.connect(
    lambda: paginas.setCurrentWidget(pagina_productos)
)
mensaje_producto = QLabel("")
mensaje_producto.setStyleSheet("color: #8ED6A0; font-size: 16px;")
layout_productos.insertWidget(
    layout_productos.indexOf(btn_guardar_producto) + 1,
    mensaje_producto
)
from PySide6.QtWidgets import QFileDialog
from PySide6.QtGui import QPixmap

ruta_imagen_elegida = None

btn_elegir_imagen = QPushButton("Elegir imagen")
vista_imagen_producto = QLabel("Sin imagen")
vista_imagen_producto.setAlignment(Qt.AlignmentFlag.AlignCenter)
vista_imagen_producto.setFixedHeight(130)

posicion = layout_productos.indexOf(btn_guardar_producto)
layout_productos.insertWidget(posicion, btn_elegir_imagen)
layout_productos.insertWidget(posicion + 1, vista_imagen_producto)


def elegir_imagen_producto():
    global ruta_imagen_elegida

    ruta, _ = QFileDialog.getOpenFileName(
        ventana,
        "Elegir imagen del producto",
        "",
        "Imágenes (*.png *.jpg *.jpeg *.webp)"
    )

    if not ruta:
        return

    imagen = QPixmap(ruta)

    if imagen.isNull():
        mensaje_producto.setText("No se pudo abrir esa imagen.")
        return

    ruta_imagen_elegida = ruta
    vista_imagen_producto.setPixmap(
        imagen.scaled(
            180, 120,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
    )


btn_elegir_imagen.clicked.connect(elegir_imagen_producto)
def guardar_imagen_producto():
    from PySide6.QtCore import QStandardPaths
    from uuid import uuid4

    if not ruta_imagen_elegida:
        return None

    carpeta_datos = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.GenericDataLocation
        )
    ) / "TPVBar" / "imagenes"

    carpeta_datos.mkdir(parents=True, exist_ok=True)

    destino = carpeta_datos / f"{uuid4().hex}.png"
    imagen = QPixmap(ruta_imagen_elegida)

    if imagen.isNull():
        raise ValueError("No se pudo leer la imagen seleccionada.")

    imagen = imagen.scaled(
        800, 800,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )

    if not imagen.save(str(destino), "PNG"):
        raise ValueError("No se pudo guardar la imagen.")

    return str(destino)
def guardar_producto():
    from decimal import Decimal, InvalidOperation

    nombre = txt_nombre_producto.text().strip()
    texto_precio = txt_precio_producto.text().strip().replace(",", ".")
    categoria = txt_categoria_producto.text().strip() or "General"

    if not nombre:
        QMessageBox.warning(
            ventana, "Revisar producto", "Escribe el nombre del producto."
        )
        return

    try:
        precio = Decimal(texto_precio)

        if not precio.is_finite() or precio <= 0:
            raise ValueError()

        centimos = precio * 100

        if centimos != centimos.to_integral_value():
            raise ValueError()

        if centimos > 99999999:
            raise ValueError()

        centimos = int(centimos)

    except (InvalidOperation, ValueError):
        QMessageBox.warning(
            ventana,
            "Revisar precio",
            "Introduce un precio entre 0.01 y 999999.99, "
            "con un máximo de dos decimales."
        )
        return

    try:
        imagen_guardada = guardar_imagen_producto()
    except (OSError, ValueError) as error:
        mensaje_producto.setText(f"No se pudo guardar la foto: {error}")
        return

    try:
        with sqlite3.connect(str(ruta_base_datos)) as conexion:
            conexion.execute(
                """
                INSERT INTO productos (
                    nombre, precio_centimos, categoria, imagen
                )
                VALUES (?, ?, ?, ?)
                """,
                (nombre, centimos, categoria, imagen_guardada)
            )

    except sqlite3.IntegrityError:
        QMessageBox.warning(
            ventana,
            "Producto existente",
            "Ya existe un producto con ese nombre y categoría."
        )
        return

    except sqlite3.Error as error:
        QMessageBox.critical(
            ventana, "Error al guardar", str(error)
        )
        return

    productos[:] = cargar_productos()
    actualizar_botones_productos()

    txt_nombre_producto.clear()
    txt_precio_producto.clear()
    txt_categoria_producto.clear()
    txt_nombre_producto.setFocus()

    mensaje_producto.setText(
        f'Producto "{nombre}" guardado correctamente.'
    )


btn_guardar_producto.clicked.connect(guardar_producto)
# Catálogo de productos
layout_productos.insertWidget(
    layout_productos.count() - 1,
    QLabel("Productos guardados")
)

lista_catalogo = QListWidget()
layout_productos.insertWidget(
    layout_productos.count() - 1,
    lista_catalogo
)


def actualizar_lista_catalogo():
    lista_catalogo.clear()

    with sqlite3.connect(str(ruta_base_datos)) as conexion:
        filas = conexion.execute("""
            SELECT id, nombre, precio_centimos, categoria
            FROM productos
            WHERE activo = 1
            ORDER BY nombre COLLATE NOCASE, categoria
        """).fetchall()

    for identificador, nombre, centimos, categoria in filas:
        elemento = QListWidgetItem(
            f"{nombre} · B/.{centimos / 100:.2f} · {categoria}"
        )
        elemento.setData(Qt.ItemDataRole.UserRole, identificador)
        lista_catalogo.addItem(elemento)


actualizar_lista_catalogo()
btn_guardar_producto.clicked.connect(actualizar_lista_catalogo)
btn_eliminar_producto = QPushButton("Eliminar seleccionado")
layout_productos.insertWidget(
    layout_productos.count() - 1,
    btn_eliminar_producto
)


def eliminar_producto():
    elemento = lista_catalogo.currentItem()

    if elemento is None:
        mensaje_producto.setText("Selecciona un producto de la lista.")
        return

    identificador = elemento.data(Qt.ItemDataRole.UserRole)

    try:
        with sqlite3.connect(str(ruta_base_datos)) as conexion:
            conexion.execute(
                "UPDATE productos SET activo = 0 WHERE id = ?",
                (identificador,)
            )
    except sqlite3.Error as error:
        mensaje_producto.setText(f"No se pudo eliminar: {error}")
        return

    productos[:] = cargar_productos()
    actualizar_botones_productos()
    actualizar_lista_catalogo()
    mensaje_producto.setText("Producto retirado del catálogo.")


btn_eliminar_producto.clicked.connect(eliminar_producto)
# Diseño táctil de la pantalla de productos
from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QBoxLayout, QScroller

pagina_productos.setObjectName("PaginaProductos")
pagina_productos.setStyleSheet("""
    QWidget#PaginaProductos { background-color: #101725; }
    QWidget#PaginaProductos QLabel {
        color: #E8E7E2; background: transparent; font-size: 17px;
    }
    QWidget#PaginaProductos QWidget[tarjeta="true"] {
        background-color: #151F30; border: 1px solid #303C52;
        border-radius: 16px;
    }
    QWidget#PaginaProductos QLineEdit {
        background-color: #0D1523; color: #F4F2ED;
        border: 1px solid #42516A; border-radius: 10px;
        padding: 8px 14px; font-size: 20px;
        selection-background-color: #D6A74C; selection-color: #101725;
    }
    QWidget#PaginaProductos QLineEdit:focus { border: 2px solid #D6A74C; }
    QWidget#PaginaProductos QPushButton {
        background-color: #233149; color: #F4F2ED;
        border: 1px solid #42516A; border-radius: 12px;
        font-size: 19px; font-weight: bold; padding: 10px 16px;
    }
    QWidget#PaginaProductos QPushButton:hover { border-color: #D6A74C; }
    QWidget#PaginaProductos QPushButton:pressed { background-color: #354762; }
    QWidget#PaginaProductos QPushButton#GuardarProducto {
        background-color: #E9BA54; color: #111827; border-color: #E9BA54;
    }
    QWidget#PaginaProductos QPushButton#EliminarProducto {
        background-color: #71343C; border-color: #A65660; color: white;
    }
    QWidget#PaginaProductos QListWidget {
        background-color: #0D1523; color: #F4F2ED;
        border: 1px solid #303C52; border-radius: 10px; font-size: 18px;
    }
    QWidget#PaginaProductos QListWidget::item {
        min-height: 60px; padding: 8px 12px; border-bottom: 1px solid #26344B;
    }
    QWidget#PaginaProductos QListWidget::item:selected {
        background-color: #354762; color: #FFE0A0;
    }
""")

# Reutilizar los mismos campos y conexiones de guardar y eliminar.
while layout_productos.count():
    elemento_diseno = layout_productos.takeAt(0)
    widget_diseno = elemento_diseno.widget()
    if widget_diseno is not None and type(widget_diseno) is QLabel:
        if widget_diseno not in (mensaje_producto, vista_imagen_producto):
            widget_diseno.deleteLater()

layout_productos.setContentsMargins(16, 16, 16, 16)
titulo_productos = QLabel("Productos")
titulo_productos.setStyleSheet("font-size: 28px; font-weight: bold; color: #F4F2ED;")
layout_productos.addWidget(titulo_productos)

scroll_productos_config = QScrollArea()
scroll_productos_config.setWidgetResizable(True)
scroll_productos_config.setFrameShape(QScrollArea.Shape.NoFrame)
scroll_productos_config.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
scroll_productos_config.setStyleSheet("QScrollArea { background: transparent; border: none; }")
contenido_productos_config = QWidget()
contenido_productos_config.setObjectName("FondoProductosConfig")
contenido_productos_config.setStyleSheet(
    "QWidget#FondoProductosConfig { background-color: #101725; }"
)
scroll_productos_config.viewport().setObjectName("ViewportProductosConfig")
scroll_productos_config.viewport().setStyleSheet(
    "QWidget#ViewportProductosConfig { background-color: #101725; }"
)
paneles_productos = QBoxLayout(QBoxLayout.Direction.LeftToRight, contenido_productos_config)
paneles_productos.setContentsMargins(0, 0, 0, 0)
paneles_productos.setSpacing(16)

tarjeta_formulario = QWidget()
tarjeta_formulario.setProperty("tarjeta", True)
formulario_tactil = QVBoxLayout(tarjeta_formulario)
formulario_tactil.setContentsMargins(20, 20, 20, 20)
formulario_tactil.setSpacing(10)
titulo_formulario = QLabel("Añadir producto")
titulo_formulario.setStyleSheet("font-size: 23px; font-weight: bold; color: #F2C66D;")
formulario_tactil.addWidget(titulo_formulario)
for texto_campo, campo in (("Nombre", txt_nombre_producto),
                           ("Precio · B/.", txt_precio_producto),
                           ("Categoría", txt_categoria_producto)):
    formulario_tactil.addWidget(QLabel(texto_campo))
    campo.setMinimumHeight(56)
    formulario_tactil.addWidget(campo)
txt_precio_producto.setInputMethodHints(Qt.InputMethodHint.ImhFormattedNumbersOnly)
btn_elegir_imagen.setText("Elegir foto del producto")
formulario_tactil.addWidget(btn_elegir_imagen)
vista_imagen_producto.setStyleSheet("background-color: #0D1523; border: 1px dashed #42516A; border-radius: 10px; color: #AAB7CB;")
formulario_tactil.addWidget(vista_imagen_producto)
btn_guardar_producto.setObjectName("GuardarProducto")
btn_guardar_producto.setText("Guardar producto")
formulario_tactil.addWidget(btn_guardar_producto)
mensaje_producto.setWordWrap(True)
formulario_tactil.addWidget(mensaje_producto)
formulario_tactil.addStretch()

tarjeta_catalogo = QWidget()
tarjeta_catalogo.setProperty("tarjeta", True)
catalogo_tactil = QVBoxLayout(tarjeta_catalogo)
catalogo_tactil.setContentsMargins(20, 20, 20, 20)
catalogo_tactil.setSpacing(12)
titulo_catalogo = QLabel("Catálogo de productos")
titulo_catalogo.setStyleSheet("font-size: 23px; font-weight: bold; color: #F2C66D;")
catalogo_tactil.addWidget(titulo_catalogo)
ayuda_catalogo = QLabel("Selecciona un producto para retirarlo del catálogo.")
ayuda_catalogo.setWordWrap(True)
catalogo_tactil.addWidget(ayuda_catalogo)
lista_catalogo.setMinimumHeight(260)
lista_catalogo.setWordWrap(True)
lista_catalogo.setSpacing(4)
lista_catalogo.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
catalogo_tactil.addWidget(lista_catalogo, 1)
btn_eliminar_producto.setObjectName("EliminarProducto")
catalogo_tactil.addWidget(btn_eliminar_producto)
for boton_tactil in (btn_elegir_imagen, btn_guardar_producto, btn_eliminar_producto):
    boton_tactil.setMinimumHeight(60)

paneles_productos.addWidget(tarjeta_formulario, 1)
paneles_productos.addWidget(tarjeta_catalogo, 1)
scroll_productos_config.setWidget(contenido_productos_config)
layout_productos.addWidget(scroll_productos_config, 1)
for superficie_tactil in (scroll_productos_config.viewport(), lista_catalogo.viewport()):
    QScroller.grabGesture(superficie_tactil, QScroller.ScrollerGestureType.TouchGesture)

class AdaptarPanelesProductos(QObject):
    def eventFilter(self, objeto, evento):
        if evento.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            direccion = (QBoxLayout.Direction.TopToBottom if objeto.width() < 900
                         else QBoxLayout.Direction.LeftToRight)
            if paneles_productos.direction() != direccion:
                paneles_productos.setDirection(direccion)
        return False

adaptador_productos = AdaptarPanelesProductos(pagina_productos)
pagina_productos.installEventFilter(adaptador_productos)

# Mostrar la aplicación
ventana.show()
sys.exit(app.exec())

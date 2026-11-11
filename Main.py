"""Punto de entrada del TPV: navegación, permisos y coordinación de pantallas.

Guía: los datos están en datos.py; la cuenta y los botones en vista_pedidos.py;
los colores compartidos en estilos.py. Consulta GUIA_DEL_PROYECTO.md.
"""
from datos import preparar_archivo_datos, inicializar_catalogo, cargar_productos as leer_productos, registrar_venta, historial_cobros, METODOS_PAGO
from inventario import (
    GestionTurnos, PaginaHojaInventarios, PaginaHorarioTurnos, PaginaInventario,
)
from vista_pedidos import cargar_pantalla, dibujar_cuenta, dibujar_productos
from estilos import HISTORIAL, CONFIGURACION, CATALOGO

import sys
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta
from PySide6.QtWidgets import QComboBox, QHeaderView, QTableWidget, QTableWidgetItem
from PySide6.QtWidgets import QApplication, QGridLayout, QVBoxLayout, QStackedWidget, QPushButton, QSizePolicy, QLineEdit, QWidget, QLabel, QScrollArea, QListWidget, QHBoxLayout, QListWidgetItem

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
app = QApplication(sys.argv)

# Carpeta donde están los archivos
carpeta = Path(__file__).resolve().parent

# Datos persistentes separados de las pantallas y del ejecutable.
from PySide6.QtCore import QStandardPaths


try:
    ruta_base_datos = preparar_archivo_datos(carpeta)
except (OSError, sqlite3.Error, RuntimeError) as error:
    QMessageBox.critical(
        None, "No se pudieron preparar los datos",
        f"No se abrirá el TPV para evitar usar una base vacía.\n{error}"
    )
    sys.exit(1)


# Cuentas persistentes; se crea Admin/Admin solo en la primera instalación.
from usuarios import SesionUsuarios, DialogoAcceso, PaginaUsuarios
from PySide6.QtWidgets import QDialog
try:
    sesion = SesionUsuarios(ruta_base_datos)
except sqlite3.Error as error:
    QMessageBox.critical(None, "Usuarios", f"No se pudieron preparar los usuarios: {error}")
    sys.exit(1)

def requiere_admin():
    if sesion.es_admin():
        return True
    QMessageBox.warning(ventana, "Acceso restringido", "Solo Admin puede acceder a esta opción.")
    return False

def abrir_seccion_admin(pagina):
    if requiere_admin():
        titulo_pagina.setText("Configuración")
        paginas.setCurrentWidget(pagina)

# Cargar la pantalla principal
def cargar_ui(nombre_archivo):
    """Abre un diseño de Qt Designer desde la carpeta del programa."""
    return cargar_pantalla(carpeta, nombre_archivo)

#---------------------------------------------------------------------------------------------------------------------------------

ventana = cargar_ui("inicio.ui")
from desplazamiento import DesplazamientoGlobal
desplazamiento = DesplazamientoGlobal(ventana)
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

tabla_historial.setColumnCount(6)
tabla_historial.setHorizontalHeaderLabels(['N.º', 'Fecha', 'Cliente', 'Mesa', 'Total', 'Pago'])
tabla_historial.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
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
tabla_historial.setStyleSheet(HISTORIAL)

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
    cancelar_asignacion_cliente()
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

        for columna in (0, 2, 3, 5):
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
    if not sesion.usuario:
        return
    cargar_historial()
    titulo_pagina.setText("Historial" if sesion.es_admin() else "Mis cobros")
    paginas.setCurrentWidget(pagina_historial)


btn_menu_historial.clicked.connect(abrir_historial)
# Guardar los pedidos por mesa
ventanas_pedido = {}
pedidos = {}
from clientes import GestionClientes, PaginaClientes, centimos, clave_producto, VENTA_RAPIDA, nombre_operacion
try:
    gestion_clientes = GestionClientes(sesion)
    pedidos.update(gestion_clientes.cargar_pedidos())
except (sqlite3.Error, ValueError) as error:
    QMessageBox.critical(ventana, "Pedidos", f"No se pudieron recuperar los pedidos abiertos: {error}")
    sys.exit(1)
clientes_activos = {}
cliente_por_asignar = None
nombres_mesas = {}
filtro_mesas_actual = "todas"
productos = [
    {"nombre": "Café", "precio": 2.50},
    {"nombre": "Hamburguesa", "precio": 6.50},
    {"nombre": "Jugo natural", "precio": 3.00},
]


def actualizar_cuenta(nombre_mesa, lista_pedido, lbl_total):
    """Redibuja los subtotales por cliente y conecta los botones + y −."""
    dibujar_cuenta(lista_pedido, lbl_total, pedidos.get(nombre_mesa, []),
                   gestion_clientes.de_mesa(nombre_mesa), clientes_activos.get(nombre_mesa),
                   lambda clave, cambio, cliente: cambiar_cantidad(
                       nombre_mesa, clave, cambio, lista_pedido, lbl_total, cliente))
    if nombre_mesa == VENTA_RAPIDA:
        lbl_total.setText(lbl_total.text().replace('Total mesa:', 'Total:'))


def avisar_pedido(nombre_mesa, texto):
    pantalla = ventanas_pedido.get(nombre_mesa)
    if pantalla:
        aviso = pantalla.findChild(QLabel, 'avisoClientes')
        if aviso:
            aviso.setText(texto)
            aviso.setVisible(bool(texto))


def guardar_cuenta_abierta(nombre_mesa, cuenta, lista_pedido, lbl_total):
    """Guarda primero en disco; solo si funciona actualiza el pedido visible."""
    try:
        gestion_turnos.exigir_turno_activo()
        gestion_clientes.guardar_pedido(nombre_mesa, cuenta)
    except (ValueError, PermissionError, sqlite3.Error) as error:
        avisar_pedido(nombre_mesa, f'No se guardó el cambio: {error}')
        return
    pedidos[nombre_mesa] = cuenta
    avisar_pedido(nombre_mesa, '')
    actualizar_cuenta(nombre_mesa, lista_pedido, lbl_total)
    filtrar_mesas(filtro_mesas_actual)


def cambiar_cantidad(nombre_mesa, clave, cambio, lista_pedido, lbl_total, cliente_id=None):
    cuenta = list(pedidos.get(nombre_mesa, []))
    for indice, producto in enumerate(cuenta):
        if clave_producto(producto) == clave and producto.get('cliente_id') == cliente_id:
            if cambio == -1:
                cuenta.pop(indice)
            elif cambio == 1:
                cuenta.append(producto.copy())
            break
    guardar_cuenta_abierta(nombre_mesa, cuenta, lista_pedido, lbl_total)


def agregar_producto(nombre_mesa, producto, lista_pedido, lbl_total):
    """Asigna cada producto al cliente seleccionado de la mesa."""
    cliente_id = clientes_activos.get(nombre_mesa)
    cliente = gestion_clientes.obtener(cliente_id) if cliente_id is not None else None
    if cliente_id is not None and (not cliente or cliente['mesa'] != nombre_mesa):
        avisar_pedido(nombre_mesa, 'Selecciona un cliente asignado a esta mesa.')
        return
    nuevo = producto.copy()
    nuevo['cliente_id'] = cliente_id
    nuevo['cliente_nombre'] = cliente['nombre'] if cliente else ''
    cuenta = list(pedidos.get(nombre_mesa, [])) + [nuevo]
    guardar_cuenta_abierta(nombre_mesa, cuenta, lista_pedido, lbl_total)


def seleccionar_cliente_pedido(nombre_mesa, selector):
    clientes_activos[nombre_mesa] = selector.currentData()
    titulo_pagina.setText(f'{nombre_mesa} · {selector.currentText()}' if selector.currentData() is not None
                         else f'Pedidos · {nombre_mesa}')
    pantalla = ventanas_pedido[nombre_mesa]
    lista = pantalla.findChild(QListWidget, 'Listapedido')
    actualizar_cuenta(nombre_mesa, lista, pantalla.findChild(QLabel, 'lblTotal'))
    for indice in range(lista.count()):
        item = lista.item(indice)
        if lista.itemWidget(item) and lista.itemWidget(item).objectName() == 'CabeceraCliente' and item.data(Qt.ItemDataRole.UserRole) == selector.currentData():
            lista.scrollToItem(item)
            break


def actualizar_selector_clientes(nombre_mesa):
    pantalla = ventanas_pedido[nombre_mesa]
    selector = pantalla.findChild(QComboBox, 'clientePedido')
    clientes = gestion_clientes.de_mesa(nombre_mesa)
    actual = clientes_activos.get(nombre_mesa, 'sin_seleccion')
    ids = [c['id'] for c in clientes]
    if actual is not None and actual not in ids:
        actual = ids[0] if ids else None
    selector.blockSignals(True)
    selector.clear()
    for cliente in clientes:
        selector.addItem(cliente['nombre'], cliente['id'])
    selector.addItem('Cuenta general · sin cliente', None)
    selector.setCurrentIndex(max(0, selector.findData(actual)))
    selector.blockSignals(False)
    clientes_activos[nombre_mesa] = selector.currentData()
    actualizar_cuenta(nombre_mesa, pantalla.findChild(QListWidget, 'Listapedido'), pantalla.findChild(QLabel, 'lblTotal'))


def preparar_selector_clientes(nombre_mesa, pantalla):
    from PySide6.QtWidgets import QFrame
    panel = pantalla.findChild(QFrame, 'PanelCuenta')
    layout = panel.layout()
    etiqueta = QLabel('Añadir productos para:')
    etiqueta.setStyleSheet('color: #AABAD0; font-size: 13px; border: none;')
    selector = QComboBox()
    selector.setObjectName('clientePedido')
    selector.setMinimumWidth(0)
    selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    selector.setStyleSheet('QComboBox { background: #1B293F; color: #F2C66D; padding: 10px; border: 1px solid #465064; border-radius: 8px; font-size: 15px; } QComboBox QAbstractItemView { background: #1B293F; color: #F4F2ED; selection-background-color: #34445E; }')
    selector.currentIndexChanged.connect(lambda: seleccionar_cliente_pedido(nombre_mesa, selector))
    aviso = QLabel('')
    aviso.setObjectName('avisoClientes')
    aviso.setWordWrap(True)
    aviso.setStyleSheet('color: #FFAEAE; font-size: 12px; border: none;')
    aviso.hide()
    posicion = layout.indexOf(pantalla.findChild(QListWidget, 'Listapedido'))
    layout.insertWidget(posicion, etiqueta)
    layout.insertWidget(posicion + 1, selector)
    layout.insertWidget(posicion + 2, aviso)
    if nombre_mesa == VENTA_RAPIDA:
        etiqueta.hide()
        selector.hide()
    actualizar_selector_clientes(nombre_mesa)


def nombres_clientes_cuenta(nombre_mesa):
    nombres = [c['nombre'] for c in gestion_clientes.de_mesa(nombre_mesa)]
    for p in pedidos.get(nombre_mesa, []):
        nombre = p.get('cliente_nombre')
        if nombre and nombre not in nombres:
            nombres.append(nombre)
    return ', '.join(nombres) or nombres_mesas.get(nombre_mesa, '')


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


inicializar_catalogo(sesion, productos)
try:
    gestion_turnos = GestionTurnos(sesion)
except sqlite3.Error as error:
    QMessageBox.critical(ventana, "Inventario", f"No se pudo preparar el inventario: {error}")
    sys.exit(1)

def cargar_productos():
    return leer_productos(sesion)


productos = cargar_productos()

def guardar_venta(nombre_mesa, metodo_pago):
    """Guarda el cobro completo antes de limpiar la cuenta de la pantalla."""
    gestion_clientes.autorizado()
    registrar_venta(sesion, nombre_mesa, nombres_clientes_cuenta(nombre_mesa),
                   pedidos.get(nombre_mesa, []), gestion_turnos.turno_id_para_venta(), metodo_pago=metodo_pago)


def finalizar_cobro(nombre_mesa, metodo_pago):
    """Confirma la venta y libera la mesa; ante un error conserva su cuenta."""
    # Primero guardar la venta en SQLite
    if not pedidos.get(nombre_mesa):
        QMessageBox.warning(
            ventana, "Cuenta vacía",
            "No hay productos para cobrar."
        )
        return

    try:
        guardar_venta(nombre_mesa, metodo_pago)
    except (sqlite3.Error, PermissionError, ValueError) as error:
        paginas.setCurrentWidget(pagina_pedido)
        avisar_pedido(nombre_mesa, f"No se pudo registrar el cobro: {error}")
        return

    # Limpiar los productos y el nombre temporal
    pedidos[nombre_mesa] = []
    nombres_mesas.pop(nombre_mesa, None)

    # Restaurar el nombre original de la mesa
    if nombre_mesa != VENTA_RAPIDA:
        indice = mesas.index(nombre_mesa)
        botones_mesas[indice].setText(nombre_mesa)

    # Actualizar la cuenta visualmente
    pantalla = ventanas_pedido[nombre_mesa]
    pantalla.findChild(QLabel, "lblMesa").setText(nombre_operacion(nombre_mesa))

    lista = pantalla.findChild(QListWidget, "Listapedido")
    total = pantalla.findChild(QLabel, "lblTotal")

    clientes_activos.pop(nombre_mesa, None)
    actualizar_selector_clientes(nombre_mesa)

    # Regresar a la pantalla de mesas
    if nombre_mesa == VENTA_RAPIDA:
        abrir_inicio()
    else:
        paginas.setCurrentWidget(pagina_mesas)
    filtrar_mesas(filtro_mesas_actual)


def cargar_historial():
    tabla_historial.setRowCount(0)
    if not sesion.usuario:
        return
    ventas = historial_cobros(sesion)
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

    dialogo = cargar_ui("confirmar_cobro.ui")

    dialogo.setMinimumSize(0, 0)
    dialogo.setMaximumSize(16777215, 16777215)

    while layout_cobro.count():
        elemento = layout_cobro.takeAt(0)
        if elemento.widget():
            elemento.widget().deleteLater()

    layout_cobro.addWidget(dialogo)

    dialogo.findChild(QLabel, "lblMesaCobro").setText(nombre_operacion(nombre_mesa))

    nombre_cliente = nombres_clientes_cuenta(nombre_mesa)
    dialogo.findChild(QLabel, "lblClienteCobro").setText(
        f"Clientes: {nombre_cliente or 'Cuenta general'}"
    )

    total_cobro = sum(centimos(p) for p in pedidos.get(nombre_mesa, [])) / 100
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
    from PySide6.QtWidgets import QButtonGroup
    metodos = QButtonGroup(dialogo)
    btn_confirmar.setEnabled(False)
    for metodo in METODOS_PAGO:
        boton = dialogo.findChild(QPushButton, "pago" + metodo)
        metodos.addButton(boton)
    metodos.buttonClicked.connect(lambda _: btn_confirmar.setEnabled(True))
    btn_confirmar.clicked.connect(
        lambda checked=False: finalizar_cobro(nombre_mesa, metodos.checkedButton().text())
    )

    paginas.setCurrentWidget(pagina_cobro)

def actualizar_botones_productos():
    """Actualiza el catálogo de todas las mesas que ya se abrieron."""
    for nombre_mesa, pantalla in ventanas_pedido.items():
        area = pantalla.findChild(QScrollArea, "AreaProductos")
        lista = (pantalla.findChild(QListWidget, "Listapedido")
                 or pantalla.findChild(QListWidget, "ListaPedido")
                 or pantalla.findChild(QListWidget, "listapedido"))
        total = pantalla.findChild(QLabel, "lblTotal")
        dibujar_productos(area, productos,
                          lambda producto, mesa=nombre_mesa, listado=lista, etiqueta=total:
                          agregar_producto(mesa, producto, listado, etiqueta))

def abrir_pedido(nombre_mesa):
    """Reutiliza la pantalla de cada mesa para conservar su estado."""
    titulo_pagina.setText(nombre_operacion(nombre_mesa) if nombre_mesa == VENTA_RAPIDA
                          else f"Pedidos · {nombre_mesa}")
    if nombre_mesa in ventanas_pedido:
        for pantalla in ventanas_pedido.values():
            pantalla.hide()

        actualizar_selector_clientes(nombre_mesa)
        ventanas_pedido[nombre_mesa].show()
        paginas.setCurrentWidget(pagina_pedido)
        return

    pantalla_pedido = cargar_ui("pedido.ui")
    pantalla_pedido.setWindowTitle(f"Pedido - {nombre_operacion(nombre_mesa)}")

    etiqueta = (
        pantalla_pedido.findChild(QLabel, "lblMesa")
        or pantalla_pedido.findChild(QLabel, "lblmesa")
    )

    if etiqueta is not None:
        etiqueta.setText(nombre_operacion(nombre_mesa))

    btn_editar_nombre = pantalla_pedido.findChild(
        QPushButton, "btnEditarNombre"
    )

    if btn_editar_nombre is not None:
        btn_editar_nombre.setVisible(nombre_mesa != VENTA_RAPIDA)
        btn_editar_nombre.clicked.connect(
            lambda checked=False: editar_nombre_desde_pedido(nombre_mesa)
        )

    btn_cobrar = pantalla_pedido.findChild(
        QPushButton, "btnCobrar"
    )

    if btn_cobrar is not None:
        if nombre_mesa == VENTA_RAPIDA:
            btn_cobrar.setText('Cobrar venta rápida')
        btn_cobrar.clicked.connect(
            lambda checked=False: cobrar_mesa(nombre_mesa)
        )
    area_productos = pantalla_pedido.findChild(QScrollArea, "AreaProductos")
    if area_productos is None:
        raise RuntimeError("No se encontró AreaProductos")

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

    dibujar_productos(area_productos, productos,
                      lambda producto: agregar_producto(nombre_mesa, producto, lista_pedido, lbl_total))

    # Ocultar el pedido anterior
    for pantalla in ventanas_pedido.values():
        pantalla.hide()

    # Insertar la pantalla dentro de la página
    layout_pedido.addWidget(pantalla_pedido)

    ventanas_pedido[nombre_mesa] = pantalla_pedido
    preparar_selector_clientes(nombre_mesa, pantalla_pedido)

    # Mostrar la página de pedidos
    pantalla_pedido.show()
    paginas.setCurrentWidget(pagina_pedido)


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
from configuracion import CatalogoMesas, PaginaMesasConfiguracion, PaginaMiCuenta
try:
    catalogo_mesas = CatalogoMesas(sesion)
    mesas = catalogo_mesas.listar()
except sqlite3.Error as error:
    QMessageBox.critical(ventana, "Mesas", f"No se pudieron cargar las mesas: {error}")
    sys.exit(1)
botones_mesas = []
from dialogos import EditorNombreMesa
editor_nombre_mesa = EditorNombreMesa(ventana)

def asignar_nombre_mesa(nombre_mesa, boton):
    nombre_actual = nombres_mesas.get(nombre_mesa, "")

    nombre, aceptado = editor_nombre_mesa.solicitar(nombre_mesa, nombre_actual)

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


def crear_boton_mesa(nombre):
    numero = len(botones_mesas)
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
        lambda checked=False, mesa=nombre, btn=boton: activar_mesa(mesa, btn)
    )

for nombre in mesas:
    crear_boton_mesa(nombre)

for fila in range((len(mesas) + 1) // 2):
    cuadricula.setRowStretch(fila, 1)

cuadricula.setColumnStretch(0, 1)
cuadricula.setColumnStretch(1, 1)
# Buscar los botones de filtros
btn_todas = ventana.findChild(QPushButton, "btnTodas")
btn_disponibles = ventana.findChild(QPushButton, "btnDisponibles")
btn_ocupadas = ventana.findChild(QPushButton, "btnOcupadas")

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
    """Muestra todas las mesas o solo las disponibles/ocupadas."""
    global filtro_mesas_actual
    filtro_mesas_actual = filtro

    mesas_visibles = []
    mesas_con_clientes = {c["mesa"] for c in gestion_clientes.listar() if c["mesa"]}

    # Determinar qué mesas deben mostrarse
    for nombre_mesa, boton in zip(mesas, botones_mesas):
        ocupada = bool(pedidos.get(nombre_mesa)) or nombre_mesa in mesas_con_clientes

        mostrar = (
            filtro == "todas"
            or (filtro == "disponibles" and not ocupada)
            or (filtro == "ocupadas" and ocupada)
        )

        boton.setVisible(mostrar)

        if mostrar:
            mesas_visibles.append(boton)

    # Quitar las posiciones anteriores permite filtrar sin dejar huecos.
    for boton in botones_mesas:
        cuadricula.removeWidget(boton)
    for fila in range(cuadricula.rowCount()):
        cuadricula.setRowStretch(fila, 0)
    # Reorganizar las mesas visibles
    for posicion, boton in enumerate(mesas_visibles):
        fila = posicion // 2
        columna = posicion % 2

        cuadricula.addWidget(boton, fila, columna)
        cuadricula.setRowStretch(fila, 1)
    filas_visibles = (len(mesas_visibles) + 1) // 2
    contenedor.setMinimumHeight(30 + filas_visibles * 110 + max(0, filas_visibles - 1) * 12)


def incorporar_mesa(nombre):
    if not requiere_admin():
        return
    mesas.append(nombre)
    crear_boton_mesa(nombre)
    filtrar_mesas(filtro_mesas_actual)


filtrar_mesas("todas")

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
# Pantalla de configuración
pagina_configuracion = QWidget()
pagina_configuracion.setObjectName("PaginaConfiguracion")
pagina_configuracion.setStyleSheet(CONFIGURACION)
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
    lambda: abrir_seccion_admin(pagina_configuracion)
)
# Pantalla de productos
pagina_productos = QWidget()
layout_productos = QVBoxLayout(pagina_productos)


txt_nombre_producto = QLineEdit()

txt_precio_producto = QLineEdit()
txt_precio_producto.setPlaceholderText("Ejemplo: 2.50")

txt_categoria_producto = QLineEdit()
txt_categoria_producto.setPlaceholderText("Ejemplo: Bebidas")

btn_guardar_producto = QPushButton("Guardar")

paginas.addWidget(pagina_productos)

btn_abrir_productos.clicked.connect(
    lambda: abrir_seccion_admin(pagina_productos)
)
mensaje_producto = QLabel("")
mensaje_producto.setStyleSheet("color: #8ED6A0; font-size: 16px;")
from PySide6.QtWidgets import QFileDialog
from PySide6.QtGui import QPixmap

ruta_imagen_elegida = None

btn_elegir_imagen = QPushButton("Elegir imagen")
vista_imagen_producto = QLabel("Sin imagen")
vista_imagen_producto.setAlignment(Qt.AlignmentFlag.AlignCenter)
vista_imagen_producto.setFixedHeight(130)


def elegir_imagen_producto():
    if not requiere_admin():
        return
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
    """Valida el precio en centavos y actualiza los botones de las mesas."""
    if not requiere_admin():
        return
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
        with sesion.conexion() as conexion:
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

lista_catalogo = QListWidget()


def actualizar_lista_catalogo():
    lista_catalogo.clear()

    with sesion.conexion() as conexion:
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


def eliminar_producto():
    """Desactiva el producto del catálogo sin borrar las ventas anteriores."""
    if not requiere_admin():
        return
    elemento = lista_catalogo.currentItem()

    if elemento is None:
        mensaje_producto.setText("Selecciona un producto de la lista.")
        return

    identificador = elemento.data(Qt.ItemDataRole.UserRole)

    try:
        with sesion.conexion() as conexion:
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
pagina_productos.setStyleSheet(CATALOGO)

# Distribución táctil: formulario y catálogo, adaptados al ancho disponible.
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

# Gestión de usuarios y límites de navegación según la sesión.
pagina_usuarios = PaginaUsuarios(sesion, lambda: abrir_seccion_admin(pagina_configuracion))
paginas.addWidget(pagina_usuarios)
btn_usuarios = QPushButton("Usuarios y permisos")
layout_configuracion.insertWidget(layout_configuracion.count() - 1, btn_usuarios)

def abrir_usuarios():
    if requiere_admin():
        pagina_usuarios.actualizar()
        titulo_pagina.setText("Usuarios y permisos")
        paginas.setCurrentWidget(pagina_usuarios)

btn_usuarios.clicked.connect(abrir_usuarios)
pagina_inventario = PaginaInventario(sesion, gestion_turnos, ventana)
paginas.addWidget(pagina_inventario)
btn_menu_inventario = QPushButton("Inventario")
btn_menu_inventario.setObjectName("btnMenuInventario")
contenido_menu_navegacion = btn_menu_mesas.parentWidget()
indice_configuracion = contenido_menu_navegacion.layout().indexOf(btn_menu_configuracion)
contenido_menu_navegacion.layout().insertWidget(indice_configuracion, btn_menu_inventario)

def abrir_inventario():
    if sesion.usuario is not None:
        pagina_inventario.modo_admin = "general"
        pagina_inventario.actualizar()
        titulo_pagina.setText("Inventario")
        paginas.setCurrentWidget(pagina_inventario)

btn_menu_inventario.clicked.connect(abrir_inventario)
pagina_hoja_inventarios = PaginaHojaInventarios(gestion_turnos, ventana)
paginas.addWidget(pagina_hoja_inventarios)
btn_hoja_inventarios = QPushButton("Hoja de inventarios")
btn_hoja_inventarios.setObjectName("btnHojaInventarios")
contenido_menu_navegacion.layout().insertWidget(
    contenido_menu_navegacion.layout().indexOf(btn_menu_inventario) + 1,
    btn_hoja_inventarios,
)

def abrir_hoja_inventarios():
    if sesion.es_admin():
        pagina_hoja_inventarios.actualizar()
        titulo_pagina.setText("Hoja de inventarios")
        paginas.setCurrentWidget(pagina_hoja_inventarios)

btn_hoja_inventarios.clicked.connect(abrir_hoja_inventarios)
pagina_horario_turnos = PaginaHorarioTurnos(gestion_turnos, ventana)
paginas.addWidget(pagina_horario_turnos)
btn_horario_turnos = QPushButton("Horario")
btn_horario_turnos.setObjectName("btnHorarioTurnos")
contenido_menu_navegacion.layout().insertWidget(
    contenido_menu_navegacion.layout().indexOf(btn_hoja_inventarios) + 1,
    btn_horario_turnos,
)

def abrir_horario_turnos():
    if requiere_admin():
        pagina_horario_turnos.actualizar()
        titulo_pagina.setText("Horario semanal")
        paginas.setCurrentWidget(pagina_horario_turnos)

btn_horario_turnos.clicked.connect(abrir_horario_turnos)
panel_lateral = ventana.findChild(QWidget, "PanelLateral")
botones_navegacion = panel_lateral.findChildren(QPushButton)
etiqueta_sesion = QLabel()
etiqueta_sesion.setWordWrap(True)
etiqueta_sesion.setStyleSheet("color: #F2C66D; font-size: 13px; padding: 8px;")
btn_cerrar_sesion = QPushButton("Cerrar sesión")
btn_cerrar_sesion.setObjectName("btnCerrarSesion")
contenido_menu = btn_menu_mesas.parentWidget()
if panel_lateral.layout() is None:
    distribucion_lateral = QVBoxLayout(panel_lateral)
    distribucion_lateral.setContentsMargins(0, 0, 0, 0)
    distribucion_lateral.addWidget(contenido_menu)
contenido_menu.layout().addWidget(etiqueta_sesion)
contenido_menu.layout().addWidget(btn_cerrar_sesion)
# Opciones exclusivas del dueño, integradas en Configuración.
def actualizar_identidad():
    etiqueta_sesion.setText(f"{sesion.usuario['nombre']} · Admin")
    pagina_usuarios.actualizar()

pagina_config_mesas = PaginaMesasConfiguracion(
    catalogo_mesas, incorporar_mesa, lambda: abrir_seccion_admin(pagina_configuracion)
)
pagina_mi_cuenta = PaginaMiCuenta(
    sesion, actualizar_identidad, lambda: abrir_seccion_admin(pagina_configuracion)
)

def abrir_personalizacion(pagina):
    if requiere_admin():
        pagina.actualizar()
        abrir_seccion_admin(pagina)

for texto_boton, pagina in (("Mesas del restaurante", pagina_config_mesas),
                             ("Mi cuenta", pagina_mi_cuenta)):
    paginas.addWidget(pagina)
    boton_config = QPushButton(texto_boton)
    boton_config.clicked.connect(lambda checked=False, p=pagina: abrir_personalizacion(p))
    layout_configuracion.insertWidget(layout_configuracion.count() - 1, boton_config)

def actualizar_asignaciones():
    for nombre_mesa in ventanas_pedido:
        actualizar_selector_clientes(nombre_mesa)
    filtrar_mesas(filtro_mesas_actual)

# Elegir una mesa es un paso táctil sobre la misma pantalla de Mesas.
barra_asignacion = QWidget()
barra_asignacion.setObjectName("BarraAsignacion")
barra_asignacion.setStyleSheet("QWidget#BarraAsignacion { background: #26354B; border: 1px solid #D6AE62; border-radius: 10px; }")
fila_asignacion = QHBoxLayout(barra_asignacion)
aviso_asignacion = QLabel()
aviso_asignacion.setTextFormat(Qt.TextFormat.PlainText)
aviso_asignacion.setWordWrap(True)
aviso_asignacion.setStyleSheet("color: #F2C66D; font-size: 20px; padding: 8px;")
btn_cancelar_asignacion = QPushButton("Cancelar")
btn_cancelar_asignacion.setMinimumHeight(54)
btn_cancelar_asignacion.setStyleSheet("background: #1B293F; color: #F4F2ED; padding: 12px 24px; border-radius: 8px; font-size: 16px;")
fila_asignacion.addWidget(aviso_asignacion, 1)
fila_asignacion.addWidget(btn_cancelar_asignacion)
distribucion_mesas.insertWidget(0, barra_asignacion)
barra_asignacion.hide()

def cancelar_asignacion_cliente():
    global cliente_por_asignar
    cliente_por_asignar = None
    barra_asignacion.hide()

def elegir_mesa_cliente(identificador):
    """Activa el paso de elegir mesa después de seleccionar un cliente."""
    global cliente_por_asignar
    if sesion.usuario is None:
        return
    cliente = gestion_clientes.obtener(identificador)
    if not cliente:
        return
    cliente_por_asignar = identificador
    aviso_asignacion.setText(f"Toca una mesa para {cliente['nombre']}")
    barra_asignacion.show()
    filtrar_mesas("todas")
    titulo_pagina.setText("Elegir mesa")
    paginas.setCurrentWidget(pagina_mesas)

def activar_mesa(nombre_mesa, boton):
    """Un toque asigna al cliente pendiente y abre su cuenta."""
    seleccionar_mesa(boton)
    if cliente_por_asignar is None:
        abrir_pedido(nombre_mesa)
        return
    identificador = cliente_por_asignar
    try:
        gestion_clientes.asignar(identificador, nombre_mesa)
    except (ValueError, PermissionError, sqlite3.Error) as error:
        aviso_asignacion.setText(f"No se pudo asignar la mesa: {error}")
        return
    clientes_activos[nombre_mesa] = identificador
    cancelar_asignacion_cliente()
    actualizar_asignaciones()
    abrir_cliente(identificador)

def abrir_cliente(identificador):
    if sesion.usuario is None:
        return
    cliente = gestion_clientes.obtener(identificador)
    if not cliente:
        return
    if not cliente['mesa']:
        elegir_mesa_cliente(identificador)
        return
    cancelar_asignacion_cliente()
    clientes_activos[cliente['mesa']] = identificador
    abrir_pedido(cliente['mesa'])
    titulo_pagina.setText(f"{cliente['mesa']} · {cliente['nombre']}")

from dialogos import EditorNombreCliente
editor_cliente = EditorNombreCliente(ventana, gestion_clientes)

def agregar_cliente_tactil():
    if sesion.usuario is None:
        return
    identificador = editor_cliente.solicitar_cliente()
    if identificador is not None:
        pagina_clientes.buscar.clear()
        pagina_clientes.actualizar()
        elegir_mesa_cliente(identificador)

pagina_clientes = PaginaClientes(gestion_clientes, pedidos, abrir_cliente, agregar_cliente_tactil)
paginas.addWidget(pagina_clientes)
btn_menu_clientes = ventana.findChild(QPushButton, "pushButton_3")

def abrir_clientes():
    cancelar_asignacion_cliente()
    if sesion.usuario is not None:
        pagina_clientes.actualizar()
        titulo_pagina.setText("Clientes")
        paginas.setCurrentWidget(pagina_clientes)

btn_cancelar_asignacion.clicked.connect(abrir_clientes)
btn_menu_clientes.clicked.connect(abrir_clientes)
paginas.currentChanged.connect(lambda _: cancelar_asignacion_cliente()
                               if paginas.currentWidget() is not pagina_mesas else None)
# Inicio permite vender en barra sin crear ni ocupar una mesa.
pagina_inicio = QWidget()
pagina_inicio.setObjectName('PaginaInicio')
layout_inicio = QVBoxLayout(pagina_inicio)
layout_inicio.setContentsMargins(28, 28, 28, 28)
layout_inicio.setSpacing(18)
ayuda_inicio = QLabel('Venta de barra, sin asignar una mesa.')
ayuda_inicio.setWordWrap(True)
ayuda_inicio.setStyleSheet('color: #AABAD0; font-size: 18px;')
layout_inicio.addWidget(ayuda_inicio)
btn_venta_rapida = QPushButton('Venta rápida')
btn_venta_rapida.setObjectName('btnVentaRapida')
btn_venta_rapida.setMinimumHeight(120)
btn_venta_rapida.setStyleSheet('''
    QPushButton { background: #EDBD58; color: #101725; border: none;
        border-radius: 16px; font-size: 28px; font-weight: bold; padding: 24px; }
    QPushButton:pressed { background: #D6A74C; }
''')
layout_inicio.addWidget(btn_venta_rapida)
btn_agregar_inventario_turno = QPushButton("Agregar inventario a este turno")
btn_agregar_inventario_turno.setMinimumHeight(72)
btn_agregar_inventario_turno.setStyleSheet("""
    QPushButton { background: #233149; color: #F4F2ED; border: 2px solid #D6AE62;
        border-radius: 12px; font-size: 20px; font-weight: bold; padding: 14px; }
    QPushButton:pressed { background: #354762; }
""")
layout_inicio.addWidget(btn_agregar_inventario_turno)

panel_agregar_inventario_turno = QWidget()
panel_agregar_inventario_turno.setObjectName("PanelAgregarInventarioTurno")
panel_agregar_inventario_turno.setStyleSheet("""
    QWidget#PanelAgregarInventarioTurno {
        background: #151F30; border: 1px solid #42516A; border-radius: 14px;
    }
    QWidget#PanelAgregarInventarioTurno QLabel {
        color: #DCE4F0; background: transparent; font-size: 16px;
    }
    QWidget#PanelAgregarInventarioTurno QComboBox,
    QWidget#PanelAgregarInventarioTurno QLineEdit {
        background: #0D1523; color: #F4F2ED; border: 1px solid #42516A;
        border-radius: 10px; padding: 10px 14px; font-size: 19px; min-height: 48px;
    }
    QWidget#PanelAgregarInventarioTurno QComboBox QAbstractItemView {
        background: #151F30; color: #F4F2ED; selection-background-color: #E9BA54;
        selection-color: #111827;
    }
    QWidget#PanelAgregarInventarioTurno QPushButton {
        background: #E9BA54; color: #111827; border: 2px solid #E9BA54;
        border-radius: 12px; padding: 14px 20px; font-size: 19px;
        font-weight: bold; min-height: 56px;
    }
""")
layout_panel_inventario = QVBoxLayout(panel_agregar_inventario_turno)
layout_panel_inventario.setContentsMargins(18, 18, 18, 18)
layout_panel_inventario.setSpacing(12)
layout_panel_inventario.addWidget(QLabel(
    "Admin puede agregar productos al inventario de este turno. "
    "Se requiere su contraseña."
))
selector_producto_agregado = QComboBox()
selector_producto_agregado.setMinimumHeight(58)
layout_panel_inventario.addWidget(selector_producto_agregado)
cantidad_inventario_agregado = QLineEdit()
cantidad_inventario_agregado.setPlaceholderText("Cantidad que se entrega")
cantidad_inventario_agregado.setAlignment(Qt.AlignmentFlag.AlignCenter)
cantidad_inventario_agregado.setMaxLength(6)
cantidad_inventario_agregado.setInputMethodHints(Qt.InputMethodHint.ImhDigitsOnly)
cantidad_inventario_agregado.setValidator(QIntValidator(1, 999999, cantidad_inventario_agregado))
layout_panel_inventario.addWidget(cantidad_inventario_agregado)
password_admin_inventario = QLineEdit()
password_admin_inventario.setPlaceholderText("Contraseña de Admin")
password_admin_inventario.setEchoMode(QLineEdit.EchoMode.Password)
password_admin_inventario.setMaxLength(128)
layout_panel_inventario.addWidget(password_admin_inventario)
btn_confirmar_inventario_agregado = QPushButton("Autorizar y agregar al turno")
layout_panel_inventario.addWidget(btn_confirmar_inventario_agregado)
estado_inventario_agregado = QLabel()
estado_inventario_agregado.setWordWrap(True)
layout_panel_inventario.addWidget(estado_inventario_agregado)
layout_inicio.addWidget(panel_agregar_inventario_turno)
panel_agregar_inventario_turno.hide()
btn_agregar_inventario_turno.hide()
layout_inicio.addStretch()
paginas.addWidget(pagina_inicio)
btn_menu_inicio = ventana.findChild(QPushButton, 'pushButton')

panel_acciones_admin = QWidget()
panel_acciones_admin.setObjectName("AccionesAdminInicio")
panel_acciones_admin.setStyleSheet("""
    QWidget#AccionesAdminInicio {
        background: #151F30; border: 1px solid #34445E; border-radius: 16px;
    }
    QWidget#AccionesAdminInicio QLabel {
        color: #F2C66D; background: transparent; font-size: 22px;
        font-weight: bold; border: none;
    }
    QWidget#AccionesAdminInicio QPushButton {
        background: #233149; color: #F4F2ED; border: 2px solid #42516A;
        border-radius: 12px; font-size: 20px; font-weight: bold;
        padding: 14px 20px; min-height: 68px;
    }
    QWidget#AccionesAdminInicio QPushButton:hover {
        border-color: #D6AE62; color: #F2C66D;
    }
    QWidget#AccionesAdminInicio QPushButton:pressed { background: #354762; }
""")
layout_acciones_admin = QVBoxLayout(panel_acciones_admin)
layout_acciones_admin.setContentsMargins(18, 18, 18, 18)
layout_acciones_admin.setSpacing(12)
layout_acciones_admin.addWidget(QLabel("Administración de inventario"))
btn_admin_asignar_cajero = QPushButton("Asignar cajero")
btn_admin_entrada_inventario = QPushButton("Registrar inventario recibido")
btn_admin_existencias = QPushButton("Ver inventario disponible")
for boton_admin in (
    btn_admin_asignar_cajero,
    btn_admin_entrada_inventario,
    btn_admin_existencias,
):
    layout_acciones_admin.addWidget(boton_admin)
layout_inicio.insertWidget(1, panel_acciones_admin)

def abrir_inicio():
    """La cuenta de barra pendiente se conserva al navegar o cerrar sesión."""
    cancelar_asignacion_cliente()
    if sesion.usuario is not None:
        titulo_pagina.setText('Inicio')
        paginas.setCurrentWidget(pagina_inicio)

def abrir_venta_rapida():
    if sesion.usuario is not None:
        cancelar_asignacion_cliente()
        abrir_pedido(VENTA_RAPIDA)

def abrir_seccion_admin_inventario(modo, titulo):
    if not requiere_admin():
        return
    try:
        pagina_inventario.abrir_seccion_admin(modo)
    except (ValueError, PermissionError, sqlite3.Error) as error:
        pagina_inventario._mostrar_mensaje(
            f"No se pudo abrir la sección: {error}", error=True
        )
        return
    titulo_pagina.setText(titulo)
    paginas.setCurrentWidget(pagina_inventario)

btn_admin_asignar_cajero.clicked.connect(
    lambda: abrir_seccion_admin_inventario("asignar", "Asignar cajero")
)
btn_admin_entrada_inventario.clicked.connect(
    lambda: abrir_seccion_admin_inventario("entrada", "Registrar inventario recibido")
)
btn_admin_existencias.clicked.connect(
    lambda: abrir_seccion_admin_inventario("existencias", "Inventario disponible")
)

def abrir_panel_inventario_agregado():
    if not sesion.usuario or sesion.es_admin():
        return
    try:
        turno = gestion_turnos.turno_del_usuario(sesion.usuario["id"])
        if not turno or turno["estado"] != "activo":
            raise PermissionError("Se necesita un turno activo para agregar inventario.")
        selector_producto_agregado.clear()
        for producto_id, nombre, categoria in gestion_turnos.productos_disponibles():
            selector_producto_agregado.addItem(
                f"{nombre} · {categoria}", producto_id
            )
    except (PermissionError, sqlite3.Error) as error:
        estado_inventario_agregado.setText(str(error))
        estado_inventario_agregado.setStyleSheet("color: #FFAEAE;")
        password_admin_inventario.clear()
        panel_agregar_inventario_turno.show()
        return
    estado_inventario_agregado.clear()
    panel_agregar_inventario_turno.setVisible(
        not panel_agregar_inventario_turno.isVisible()
    )

def guardar_inventario_agregado():
    try:
        texto_cantidad = cantidad_inventario_agregado.text().strip()
        if not texto_cantidad:
            raise ValueError("Escribe cuántas unidades se están agregando.")
        producto_id = selector_producto_agregado.currentData()
        if producto_id is None:
            raise ValueError("No hay productos activos para agregar.")
        gestion_turnos.agregar_inventario_a_turno(
            producto_id,
            int(texto_cantidad),
            password_admin_inventario.text(),
        )
    except (ValueError, PermissionError, sqlite3.Error) as error:
        estado_inventario_agregado.setText(str(error))
        estado_inventario_agregado.setStyleSheet("color: #FFAEAE;")
        password_admin_inventario.clear()
        return
    cantidad_inventario_agregado.clear()
    password_admin_inventario.clear()
    estado_inventario_agregado.setText(
        "Inventario agregado al turno y registrado en la Hoja de inventarios."
    )
    estado_inventario_agregado.setStyleSheet("color: #8ED6A0;")
    pagina_inventario.actualizar()

btn_menu_inicio.clicked.connect(abrir_inicio)
btn_venta_rapida.clicked.connect(abrir_venta_rapida)
btn_agregar_inventario_turno.clicked.connect(abrir_panel_inventario_agregado)
btn_confirmar_inventario_agregado.clicked.connect(guardar_inventario_agregado)
paginas_operacion = (
    pagina_inicio, pagina_mesas, pagina_pedido, pagina_cobro, pagina_clientes,
    pagina_inventario, pagina_historial,
)

def proteger_navegacion(indice):
    if not sesion.es_admin() and paginas.currentWidget() not in paginas_operacion:
        abrir_mesas()

paginas.currentChanged.connect(proteger_navegacion)

def aplicar_permisos():
    """Admin usa el menú de gestión; empleados operan según su turno."""
    admin = sesion.es_admin()
    puede_operar = admin or gestion_turnos.permite_operar()
    btn_pedidos_table.setVisible(sesion.usuario is not None and puede_operar)
    for boton in botones_navegacion:
        permitido = sesion.usuario is not None and (
            (admin and boton not in (
                btn_menu_mesas, btn_menu_clientes, btn_menu_inventario
            ))
            or (not admin and (
                boton in (btn_menu_inventario, btn_menu_historial)
                or (puede_operar and boton in (
                    btn_menu_inicio, btn_menu_mesas, btn_menu_clientes
                ))
            ))
        )
        boton.setVisible(permitido)
        boton.setEnabled(permitido)
    panel_acciones_admin.setVisible(admin)
    btn_venta_rapida.setVisible(not admin)
    turno_actual_cajero = (
        gestion_turnos.turno_del_usuario(sesion.usuario["id"])
        if sesion.usuario and not admin else None
    )
    puede_agregar_inventario = bool(
        turno_actual_cajero and turno_actual_cajero["estado"] == "activo"
    )
    btn_agregar_inventario_turno.setVisible(puede_agregar_inventario)
    if not puede_agregar_inventario:
        panel_agregar_inventario_turno.hide()
        password_admin_inventario.clear()
    ayuda_inicio.setText(
        "Panel de administración." if admin
        else "Venta de barra, sin asignar una mesa."
    )
    for pagina in (
        pagina_configuracion, pagina_productos, pagina_usuarios,
        pagina_config_mesas, pagina_mi_cuenta,
    ):
        pagina.setEnabled(admin)
    btn_menu_historial.setText("Historial" if admin else "Mis cobros")
    pagina_historial.setEnabled(sesion.usuario is not None)
    pagina_inventario.setEnabled(sesion.usuario is not None)
    pagina_hoja_inventarios.setEnabled(admin)
    pagina_horario_turnos.setEnabled(admin)
    paginas.setEnabled(sesion.usuario is not None)
    if sesion.usuario is not None:
        pagina_inventario.actualizar()
    etiqueta_sesion.setText(
        f"{sesion.usuario['nombre']} · {'Admin' if admin else 'Cajero'}"
        if sesion.usuario else "Sin sesión"
    )
    if admin:
        abrir_inicio()
    elif not puede_operar:
        abrir_inventario()
    else:
        abrir_mesas()

pagina_inventario.al_cambio_turno = aplicar_permisos

# La terminal móvil solo envía solicitudes. Esta página las incorpora desde Qt.
from pedidos_table_ui import PaginaPedidosTable
btn_pedidos_table = QPushButton('PedidosTable')
contenido_menu.layout().insertWidget(0, btn_pedidos_table)

def reflejar_solicitud_table(mesa, cuenta):
    pedidos[mesa] = cuenta
    pantalla = ventanas_pedido.get(mesa)
    if pantalla:
        actualizar_cuenta(mesa, pantalla.findChild(QListWidget, 'Listapedido'),
                          pantalla.findChild(QLabel, 'lblTotal'))
    filtrar_mesas(filtro_mesas_actual)

pagina_pedidos_table = PaginaPedidosTable(sesion, gestion_turnos,
                                         reflejar_solicitud_table, btn_pedidos_table)
paginas.addWidget(pagina_pedidos_table)
paginas_operacion = (*paginas_operacion, pagina_pedidos_table)

def abrir_pedidos_table():
    try:
        gestion_turnos.exigir_turno_activo()
    except PermissionError as error:
        QMessageBox.warning(ventana, 'PedidosTable', str(error))
        return
    titulo_pagina.setText('PedidosTable')
    paginas.setCurrentWidget(pagina_pedidos_table)
    pagina_pedidos_table.actualizar()

btn_pedidos_table.clicked.connect(abrir_pedidos_table)
app.aboutToQuit.connect(pagina_pedidos_table.servidor.detener)

def mostrar_resultado_cierre():
    aplicar_permisos()
    titulo_pagina.setText("Inventario")
    paginas.setCurrentWidget(pagina_inventario)

pagina_inventario.al_cierre_turno = mostrar_resultado_cierre

acceso = DialogoAcceso(sesion, ventana)

def cerrar_sesion():
    # Los pedidos abiertos se conservan al cambiar de empleado.
    control_espera.capa.hide()
    sesion.cerrar()
    tabla_historial.setRowCount(0)
    pagina_usuarios.limpiar()
    pagina_mi_cuenta.limpiar()
    txt_nombre_producto.clear()
    txt_precio_producto.clear()
    txt_categoria_producto.clear()
    aplicar_permisos()
    if acceso.exec() == QDialog.DialogCode.Accepted:
        aplicar_permisos()
        control_espera.temporizador.start()
    else:
        ventana.close()

btn_cerrar_sesion.clicked.connect(cerrar_sesion)

# Pedir credenciales antes de mostrar cualquier contenido del restaurante.
aplicar_permisos()
if acceso.exec() != QDialog.DialogCode.Accepted:
    sys.exit(0)
aplicar_permisos()

# Pantalla de espera automática tras dos minutos sin actividad.
from pantalla_espera import ControlEspera
control_espera = ControlEspera(ventana, segundos=120)

# Mostrar la aplicación
ventana.showFullScreen()
sys.exit(app.exec())

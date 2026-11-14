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
from interfaz_adaptable import es_android

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
    etiqueta.setTextFormat(Qt.TextFormat.PlainText)
    etiqueta.setMinimumWidth(0)
    etiqueta.setWordWrap(True)

    etiqueta.setStyleSheet("""
        color: white;
        font-size: 15px;
        background: transparent;
    """)

    layout.addWidget(etiqueta, 1)
    if al_restar is None:
        return fila

    boton_menos = QPushButton("−")
    boton_mas = QPushButton("+")

    boton_menos.setFixedSize(48, 48)
    boton_mas.setFixedSize(48, 48)

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
            background-color: #25d6f4;
            color: black;
            border: none;
            border-radius: 7px;
            font-size: 18px;
            font-weight: bold;
        }
    """)

    layout.addWidget(boton_menos)
    layout.addWidget(boton_mas)

    boton_menos.setAccessibleName(f"Quitar una unidad de {nombre}")
    boton_mas.setAccessibleName(f"Añadir una unidad de {nombre}")
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
    compacto=es_android() and boton.window().width()<760
    alto=152 if compacto else 224
    boton.setFixedHeight(alto)
    boton.setStyleSheet(BOTON_PRODUCTO + f"QPushButton {{ padding: 0px; min-height: {alto}px; max-height: {alto}px; }}")
    boton.setAccessibleName(
        f"{producto['nombre']}, B/.{producto['precio']:.2f}"
    )

    distribucion = QVBoxLayout(boton)
    distribucion.setContentsMargins(8, 8, 8, 8)
    distribucion.setSpacing(6)

    foto = QLabel()
    foto.setFixedHeight(64 if compacto else 100)
    foto.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    foto.setPixmap(
        imagen.scaled(
            120 if compacto else 150, 64 if compacto else 100,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
    )

    texto = QLabel(
        f"{producto['nombre']}\nB/.{producto['precio']:.2f}"
    )
    texto.setWordWrap(True)
    texto.setMinimumHeight(48 if compacto else 64)
    texto.setTextFormat(Qt.TextFormat.PlainText)

    for etiqueta in (foto, texto):
        etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        etiqueta.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        etiqueta.setStyleSheet("""
            background: transparent;
            border: none;
            color: #eaf3ff;
            font-size: 18px;
            font-weight: bold;
            padding: 0px;
        """)
        if compacto:etiqueta.setStyleSheet(etiqueta.styleSheet()+"font-size:14px;")
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
                   al_retirar, al_seleccionar, *, detallada=False):
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
        importe.setStyleSheet('background: transparent; padding: 0; border: none; color: #85eaff; font-size: 15px;')
        importe.setFixedHeight(importe.sizeHint().height())
        for etiqueta in (nombre, importe):
            etiqueta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            contenido.addWidget(etiqueta)
        if al_seleccionar:
            tarjeta.clicked.connect(lambda checked=False, c=identificador: al_seleccionar(c))
        else:
            tarjeta.setCheckable(False)
        fila_cabecera.addWidget(tarjeta, 1)
        if identificador is not None and not grupo['productos'] and al_retirar:
            retirar = QPushButton('Retirar')
            retirar.setObjectName('RetirarClienteMesa')
            retirar.setToolTip('Quita al cliente de esta mesa sin borrar su registro ni cobrar')
            retirar.setMinimumSize(88, 52)
            retirar.setStyleSheet('''
                QPushButton#RetirarClienteMesa { background: #303C50; color: #eaf3ff;
                    border: 1px solid #53647D; border-radius: 8px; padding: 8px 12px;
                    font-size: 14px; font-weight: bold; }
                QPushButton#RetirarClienteMesa:hover { background: #46566B; border-color: #23d7f4; }
                QPushButton#RetirarClienteMesa:pressed { background: #23d7f4; color: #0b1425; }
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
        importes = {}
        variantes = {}
        for producto in grupo['productos']:
            variante = clave_producto(producto)
            clave = variante if detallada else (variante[0], variante[2])
            importes[clave] = importes.get(clave, 0) + centimos(producto)
            cantidades[clave] = cantidades.get(clave, 0) + 1
            variantes.setdefault(clave, set()).add(variante)
        if not cantidades:
            vacio = QListWidgetItem('Sin productos todavía')
            vacio.setSizeHint(QSize(0, 34))
            lista_pedido.addItem(vacio)
        for clave, cantidad in cantidades.items():
            nombre = clave[0]
            if detallada:
                detalles = [f"B/.{clave[1] / 100:.2f} c/u"]
                if clave[3]:
                    detalles.append(f"Preparación: {clave[3]}")
                if clave[4]:
                    detalles.append(f"Acompañamiento: {clave[4]}")
                if clave[5]:
                    detalles.append(f"Extra: {clave[5]} (+B/.{clave[6] / 100:.2f})")
                nombre += "\n" + "\n".join(detalles)
            variante = next(iter(variantes[clave]))
            ajustar = len(variantes[clave]) == 1
            fila = crear_fila_producto(
                nombre, cantidad, importes[clave] / 100,
                (lambda checked=False, k=variante, c=identificador: al_cambiar(k, -1, c)) if ajustar else None,
                (lambda checked=False, k=variante, c=identificador: al_cambiar(k, 1, c)) if ajustar else None,
            )
            elemento = QListWidgetItem()
            elemento.setSizeHint(QSize(0, max(88, fila.sizeHint().height() + 12)))
            lista_pedido.addItem(elemento)
            lista_pedido.setItemWidget(elemento, fila)
    lbl_total.setText(f'Total mesa: B/.{total / 100:.2f}')


class RejillaProductos(QWidget):
    """Redistribuye los botones existentes al girar o redimensionar la terminal."""
    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.botones = []
        self.columnas = 0
        layout = QGridLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

    def distribuir(self):
        columnas = max(1, min(2 if self.width()<600 else 6, (self.width() - 10) // (160 if self.width()<600 else 200)))
        if columnas != self.columnas:
            self.columnas = columnas
            for boton in self.botones:
                self.layout().removeWidget(boton)
            for i, boton in enumerate(self.botones):
                self.layout().addWidget(boton, i // columnas, i % columnas)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.distribuir()


def dibujar_productos(area, productos, al_agregar, agotados=()):
    """Único constructor del catálogo de botones, tanto al abrir como al actualizar."""
    contenedor = area.widget()
    if not isinstance(contenedor, RejillaProductos):
        contenedor = RejillaProductos()
        area.setWidget(contenedor)
    cuadricula = contenedor.layout()
    contenedor.botones.clear()
    contenedor.columnas = 0
    while cuadricula.count():
        boton = cuadricula.takeAt(0).widget()
        if boton is not None:
            boton.hide()
            boton.deleteLater()
    for producto in productos:
        boton = QPushButton(f"{producto['nombre']}\nB/.{producto['precio']:.2f}")
        boton.setMinimumSize(120, 108)
        boton.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        boton.setStyleSheet(BOTON_PRODUCTO + "QPushButton { min-height: 108px; max-height: 108px; padding: 8px; }")
        if producto.get('id') in agotados:
            boton.setText(f"{producto['nombre']}\nNo disponible")
            boton.setEnabled(False)
            boton.setStyleSheet(BOTON_PRODUCTO + "QPushButton { min-height: 108px; max-height: 108px; padding: 8px; } QPushButton:disabled { color: #edb694; background: #26272b; }")
        else:
            poner_imagen_producto(boton, producto)
        boton.clicked.connect(lambda checked=False, p=producto: al_agregar(p))
        contenedor.botones.append(boton)
    contenedor.distribuir()


def personalizar_plato(parent, producto, acompanamientos, recargos):
    from PySide6.QtWidgets import QButtonGroup, QDialog, QStackedWidget
    from dialogos import DialogoIntegrado
    from cocina import opciones

    dialogo = DialogoIntegrado(parent)
    dialogo.setProperty('compacto', True)
    dialogo.setWindowTitle(producto['nombre'])
    dialogo.setStyleSheet("""
        QWidget { background: #101b2e; }
        QLabel { color: #eeeadd; background: transparent; border: none; font-size: 16px; }
        QPushButton { background: #11283f; color: #eaf3ff; border: 1px solid #287b99;
            border-radius: 12px; padding: 14px; font-size: 17px; }
        QPushButton:checked { background: #23d7f4; color: #071725; border: 2px solid #8cefff; }
        QPushButton:disabled { background: #283b34; color: #82978d; }
        QPushButton#ContinuarPlato { background: #23d7f4; color: #071725; font-weight: 600; }
        QPushButton#ContinuarPlato:disabled { background: #283b34; color: #82978d; }
    """)
    layout = QVBoxLayout(dialogo)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(14)
    progreso = QLabel()
    progreso.setStyleSheet('color: #23d7f4; font-size: 14px;')
    layout.addWidget(progreso)
    paginas = QStackedWidget()
    layout.addWidget(paginas)
    from cocina import preparaciones_con_recargo
    lleva_acompanamiento = producto.get('lleva_acompanamiento', True)
    cargos_preparacion = preparaciones_con_recargo(producto.get('preparaciones', ''))
    variantes = opciones(producto.get('preparaciones', ''))
    if not variantes and 'hamburguesa' in producto['nombre'].casefold():
        variantes = ['Completa', 'Sin vegetales']
    if not lleva_acompanamiento and not variantes:
        return dict(preparacion='', acompanamiento='', extra='', recargo_centimos=0)
    seleccion = {'preparacion': '', 'acompanamiento': ''}
    grupos = []
    preparaciones_elegidas = []
    lados_elegidos = []
    limite_lados = max(1, int(producto.get('cantidad_acompanamientos', 1)))

    def pagina(etiqueta, valores, campo):
        widget = QWidget()
        caja = QVBoxLayout(widget)
        caja.setContentsMargins(0, 0, 0, 0)
        titulo = QLabel(etiqueta)
        titulo.setWordWrap(True)
        titulo.setStyleSheet('font-size: 23px; font-weight: 600;')
        caja.addWidget(titulo)
        rejilla = QGridLayout()
        rejilla.setSpacing(10)
        grupo = QButtonGroup(dialogo)
        grupo.setExclusive(campo == 'acompanamiento' and limite_lados == 1)
        grupos.append(grupo)
        from interfaz_adaptable import es_android
        columnas_opciones = 1 if es_android() and parent.window().width() < 600 else 2
        for indice, valor in enumerate(valores):
            cargo_opcion = cargos_preparacion.get(valor, 0) if campo == 'preparacion' else 0
            boton = QPushButton(valor + (f' (+B/.{cargo_opcion / 100:.2f})' if cargo_opcion else ''))
            boton.setMinimumHeight(68)
            boton.setCheckable(True)
            boton.setProperty('opcionPlato', campo)
            grupo.addButton(boton)
            rejilla.addWidget(boton, indice // columnas_opciones, indice % columnas_opciones)
            boton.clicked.connect(lambda checked=False, v=valor: elegir(campo, v))
        caja.addLayout(rejilla)
        caja.addStretch()
        paginas.addWidget(widget)
        return caja

    if variantes:
        pagina('Preparaciones · puedes marcar varias', variantes, 'preparacion')
    caja_lados = pagina(f'Elige hasta {limite_lados} acompañamientos incluidos' if limite_lados > 1 else 'Elige el acompañamiento', acompanamientos, 'acompanamiento') if lleva_acompanamiento else QVBoxLayout()
    extra = QPushButton('Añadir porción extra')
    extra.setMinimumHeight(56)
    extra.setCheckable(True)
    extra.setEnabled(False)
    if lleva_acompanamiento:
        caja_lados.insertWidget(caja_lados.count() - 1, extra)
    else:
        extra.hide()
    resumen = QLabel()
    resumen.setWordWrap(True)
    layout.addWidget(resumen)
    importe = QLabel()
    importe.setStyleSheet('font-size: 21px; color: #79eaff; font-weight: 600;')
    layout.addWidget(importe)
    fila = QHBoxLayout()
    atras = QPushButton('Atrás')
    siguiente = QPushButton('Siguiente')
    siguiente.setObjectName('ContinuarPlato')
    siguiente.setMinimumHeight(56)
    fila.addWidget(atras)
    fila.addWidget(siguiente, 1)
    layout.addLayout(fila)

    def actualizar():
        en_lados = not variantes or paginas.currentIndex() == 1
        progreso.setText(('Paso 2 de 2 · Acompañamiento' if en_lados else 'Paso 1 de 2 · Preparación')
                         if variantes else 'Acompañamiento')
        if not lleva_acompanamiento:
            progreso.setText('Preparaciones')
        atras.setVisible(bool(variantes) and en_lados)
        siguiente.setText('Añadir al pedido' if en_lados or not lleva_acompanamiento else 'Siguiente · Acompañamiento')
        siguiente.setEnabled(bool(seleccion['acompanamiento' if en_lados else 'preparacion']))
        lado_extra = lados_elegidos[-1] if lados_elegidos else ''
        extra.setEnabled(recargos.get(lado_extra, 0) > 0)
        cargo = recargos.get(lado_extra, 0)
        for grupo in grupos:
            for boton in grupo.buttons():
                if boton.property('opcionPlato') == 'acompanamiento' and limite_lados > 1:
                    boton.setEnabled(boton.isChecked() or len(lados_elegidos) < limite_lados)
        extra.setText(f'Porción extra (+B/.{cargo / 100:.2f})' if cargo else 'Porción extra no disponible')
        if limite_lados > 1 and cargo:
            extra.setText(f'Porción extra de {lado_extra} (+B/.{cargo / 100:.2f})')
        adicional = (cargo if extra.isChecked() else 0) + sum(cargos_preparacion.get(v, 0) for v in preparaciones_elegidas)
        importe.setText(f'Total: B/.{(centimos(producto) + adicional) / 100:.2f}')
        resumen.setText(' · '.join(v for v in seleccion.values() if v))

    def elegir(campo, valor):
        if campo == 'preparacion':
            if valor in preparaciones_elegidas:
                preparaciones_elegidas.remove(valor)
            else:
                preparaciones_elegidas.append(valor)
            seleccion[campo] = ' · '.join(preparaciones_elegidas)
        else:
            if limite_lados == 1:
                lados_elegidos[:] = [valor]
            elif valor in lados_elegidos:
                lados_elegidos.remove(valor)
            else:
                lados_elegidos.append(valor)
            seleccion[campo] = ' · '.join(lados_elegidos)
        if campo == 'acompanamiento':
            extra.setChecked(False)
        actualizar()

    def continuar():
        if not lleva_acompanamiento:
            dialogo.accept()
        elif variantes and paginas.currentIndex() == 0:
            paginas.setCurrentIndex(1)
            actualizar()
        elif seleccion['acompanamiento']:
            dialogo.accept()

    atras.clicked.connect(lambda: (paginas.setCurrentIndex(0), actualizar()))
    siguiente.clicked.connect(continuar)
    extra.toggled.connect(actualizar)
    actualizar()
    if dialogo.exec() == QDialog.DialogCode.Accepted:
        return dict(preparacion=seleccion['preparacion'], acompanamiento=seleccion['acompanamiento'],
                        extra=lados_elegidos[-1] if extra.isChecked() and lados_elegidos else '',
                        recargo_centimos=(recargos.get(lados_elegidos[-1], 0) if extra.isChecked() and lados_elegidos else 0)
                        + sum(cargos_preparacion.get(v, 0) for v in preparaciones_elegidas))

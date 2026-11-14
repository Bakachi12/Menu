"""Presentación de configuración y conexión de dispositivos."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QPushButton, QLabel, QApplication, QSizePolicy


class AccesosConfiguracion(QWidget):
    def __init__(self, botones):
        super().__init__()
        self.botones = botones
        self.columnas = 0
        self.rejilla = QGridLayout(self)
        self.rejilla.setContentsMargins(0, 0, 0, 0)
        self.rejilla.setSpacing(16)
        self.distribuir()

    def distribuir(self):
        columnas = 2 if self.width() >= 800 else 1
        if columnas == self.columnas:
            return
        self.columnas = columnas
        for boton in self.botones:
            self.rejilla.removeWidget(boton)
        for i, boton in enumerate(self.botones):
            self.rejilla.addWidget(boton, i // columnas, i % columnas)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.distribuir()


def organizar_configuracion(layout):
    descripciones = {
        'Productos': ('Productos y menú', 'Precios, fotos, preparaciones y extras'),
        'Usuarios y permisos': ('Personal y permisos', 'Cuentas del equipo y accesos'),
        'Mesas del restaurante': ('Mesas', 'Nombres y organización del salón'),
        'Mi cuenta': ('Mi cuenta', 'Nombre y contraseña de administrador'),
        'Dispositivos móviles': ('Dispositivos móviles', 'Conectar tablets y pantalla de cocina'),
    }
    botones = []
    for i in range(layout.count()-1, -1, -1):
        widget = layout.itemAt(i).widget()
        if isinstance(widget, QPushButton) and widget.text() in descripciones:
            titulo, ayuda = descripciones[widget.text()]
            widget.setText(titulo + '\n' + ayuda)
            widget.setAccessibleName(titulo + '. ' + ayuda)
            widget.setMinimumHeight(116)
            widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            widget.setStyleSheet('QPushButton { text-align: left; padding: 18px 22px; font-size: 18px; border: 1px solid #277c9e; border-radius: 16px; background: #112b45; color: #f8f0dc; min-height: 86px; } QPushButton:hover { background: #17415e; border-color: #ff69d5; }')
            layout.removeWidget(widget)
            botones.insert(0, widget)
    ayuda = QLabel('Elige qué quieres configurar.')
    layout.insertWidget(1, ayuda)
    layout.insertWidget(2, AccesosConfiguracion(botones))


def organizar_conexion(panel, activar, ip, nombre, enlace, crear, cocina, terminales, revocar, estado):
    layout = panel.layout()
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().hide()
    layout.setSpacing(16)
    def tarjeta(titulo, descripcion):
        marco = QWidget()
        marco.setObjectName('PasoConexion')
        marco.setStyleSheet('QWidget#PasoConexion { background: #1b332c; border: 1px solid #456253; border-radius: 14px; } QLabel { background: transparent; border: none; color: #f3ebd8; font-size: 16px; }')
        caja = QVBoxLayout(marco)
        caja.setContentsMargins(18,16,18,16)
        etiqueta = QLabel(titulo)
        etiqueta.setStyleSheet('font-size: 21px; color: #ff69d5;')
        caja.addWidget(etiqueta)
        ayuda = QLabel(descripcion)
        ayuda.setWordWrap(True)
        caja.addWidget(ayuda)
        layout.addWidget(marco)
        return caja
    def poner(caja, *widgets):
        for widget in widgets:
            caja.addWidget(widget)
            widget.show()
    paso1 = tarjeta('1. Activa la conexión', 'Conecta esta PC y los dispositivos al mismo Wi-Fi.')
    poner(paso1, activar)
    paso2 = tarjeta('2. Crea el enlace', 'Pon un nombre al dispositivo y elige para qué se usará.')
    paso2.addWidget(QLabel('Nombre del dispositivo (opcional)'))
    nombre.setPlaceholderText('Ejemplo: Tablet terraza')
    crear.setText('Crear enlace para tomar pedidos')
    cocina.setText('Crear enlace para la pantalla de cocina')
    poner(paso2, nombre, crear, cocina)
    paso3 = tarjeta('3. Abre el enlace en el dispositivo', 'Copia el enlace y ábrelo en el navegador de la tablet o del teléfono. Los pedidos necesitan aprobación en caja.')
    enlace.setPlaceholderText('El enlace aparece al crearlo en el paso 2.')
    poner(paso3, enlace)
    copiar = QPushButton('Copiar enlace')
    copiar.setEnabled(bool(enlace.text()))
    enlace.textChanged.connect(lambda texto: copiar.setEnabled(bool(texto)))
    copiar.clicked.connect(lambda: QApplication.clipboard().setText(enlace.text()))
    paso3.addWidget(copiar)
    def desplegable(titulo, widgets):
        boton = QPushButton('+ ' + titulo)
        boton.setCheckable(True)
        layout.addWidget(boton)
        contenido = QWidget()
        caja = QVBoxLayout(contenido)
        for widget in widgets:
            caja.addWidget(widget)
            widget.show()
        layout.addWidget(contenido)
        contenido.hide()
        boton.toggled.connect(contenido.setVisible)
        boton.toggled.connect(lambda abierto: boton.setText(('− ' if abierto else '+ ') + titulo))
    desplegable('Dispositivos con acceso', [terminales, revocar])
    desplegable('Ajustes de red', [QLabel('Dirección IP de esta PC'), ip])
    poner(layout, estado)

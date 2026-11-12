"""Guía visual: aquí se cambian los colores, bordes y tamaños compartidos.

Los selectores #Nombre se refieren al objectName de los widgets.
Los archivos .ui mantienen el diseño de las pantallas hechas en Qt Designer.
"""

# Identidad del bar: azul noche, piedra oscura y oro cálido.
FONDO = "#101c1b"
PANEL = "#192d2a"
PANEL_ELEVADO = "#1A2738"
BORDE = "#34445A"
DORADO = "#D6AE62"
TEXTO = "#F4F2ED"

# Controles comunes para pantallas táctiles; las pantallas pueden añadir
# reglas más específicas para botones de acción o estados peligrosos.
TEMA = """
QWidget { font-family: "Segoe UI", "Roboto", sans-serif; }
QPushButton { min-height: 32px; padding: 6px 12px; border-radius: 10px;
    border: 1px solid #45605e; background: #233b3a; color: #f5f1e8; }
QPushButton:pressed { background: #365652; }
QPushButton:focus { border: 2px solid #ecc77e; }
QPushButton:disabled { color: #a8b4af; background: #293433; }
QComboBox QAbstractItemView::item, QListWidget::item { min-height: 44px; }
QLineEdit, QComboBox, QAbstractSpinBox { min-height: 32px; }
QToolTip { background: #152235; color: #F4F2ED; border: 1px solid #D6AE62;
    border-radius: 6px; padding: 6px; }
QLineEdit, QComboBox, QSpinBox, QTimeEdit {
    background: #192d2a; color: #F4F2ED; border: 1px solid #34445A;
    border-radius: 9px; padding: 10px 12px; selection-background-color: #D6AE62;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTimeEdit:focus {
    border: 2px solid #D6AE62;
}
QScrollBar:vertical { background: #101c1b; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: #46566B; min-height: 28px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #D6AE62; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

# Diseño de formularios.
FORMULARIOS = """
QDialog, QWidget#Usuarios { background: #101c1b; color: #F4F2ED; }
QLabel { color: #DCE4F0; background: transparent; font-size: 15px; }
QLineEdit, QListWidget { background: #1c302c; color: #F4F2ED;
    border: 1px solid #40594f; border-radius: 8px; padding: 10px; font-size: 16px; }
QPushButton { background: #274341; color: #fff5df; border: none;
    border-radius: 8px; padding: 14px; font-size: 16px; font-weight: 600; }
QPushButton:hover { background: #345652; }
QPushButton:default, QPushButton:checked { background: #edc675; color: #162522; }
QPushButton:disabled { background: #40594f; color: #A8B4C8; }
"""

# Diseño de historial.
HISTORIAL = """
QTableWidget {
        background-color: #172a29;
        alternate-background-color: #203532;
        color: white;
        border: none;
        gridline-color: #344d49;
        font-size: 14px;
        selection-background-color: rgba(212, 175, 55, 235);
        selection-color: #20202B;
    }

    QHeaderView::section {
        background-color: #29443f;
        color: #D4AF37;
        padding: 10px;
        border: none;
        font-weight: bold;
    }

    QTableWidget::item {
        padding: 8px;
    }
"""

# Diseño de configuracion.
CONFIGURACION = """
QWidget#PaginaConfiguracion {
        background-color: #101c1b;
        color: #F4F2ED;
    }
    QWidget#PaginaConfiguracion QLabel {
        color: #F4F2ED;
        font-size: 24px;
        font-weight: bold;
        background: transparent;
    }
    QWidget#PaginaConfiguracion QPushButton {
        background-color: #233b36;
        color: #E9E8E3;
        border: 1px solid #3c554d;
        border-radius: 10px;
        padding: 14px 18px;
        font-size: 15px;
        font-weight: 600;
        text-align: left;
    }
    QWidget#PaginaConfiguracion QPushButton:hover {
        background-color: #345249;
        color: #F2C66D;
        border-color: #D6A74C;
    }
    QWidget#PaginaConfiguracion QPushButton:pressed {
        background-color: #D4AF37;
        color: #111827;
    }
"""

# Diseño de catalogo.
CATALOGO = """
QWidget#PaginaProductos { background-color: #132320; }
    QWidget#PaginaProductos QLabel {
        color: #E8E7E2; background: transparent; font-size: 17px;
    }
    QWidget#PaginaProductos QWidget[tarjeta="true"] {
        background-color: #1a2e2b; border: 1px solid #3c554d;
        border-radius: 16px;
    }
    QWidget#PaginaProductos QLineEdit {
        background-color: #10221e; color: #F4F2ED;
        border: 1px solid #516b60; border-radius: 10px;
        padding: 8px 14px; font-size: 20px;
        selection-background-color: #D6A74C; selection-color: #132320;
    }
    QWidget#PaginaProductos QLineEdit:focus { border: 2px solid #D6A74C; }
    QWidget#PaginaProductos QPushButton {
        background-color: #29453e; color: #F4F2ED;
        border: 1px solid #516b60; border-radius: 12px;
        font-size: 19px; font-weight: bold; padding: 10px 16px;
    }
    QWidget#PaginaProductos QPushButton:hover { border-color: #D6A74C; }
    QWidget#PaginaProductos QPushButton:pressed { background-color: #36564b; }
    QWidget#PaginaProductos QPushButton#GuardarProducto {
        background-color: #E9BA54; color: #111827; border-color: #E9BA54;
    }
    QWidget#PaginaProductos QPushButton#EliminarProducto {
        background-color: #71343C; border-color: #A65660; color: white;
    }
    QWidget#PaginaProductos QListWidget {
        background-color: #10221e; color: #F4F2ED;
        border: 1px solid #3c554d; border-radius: 10px; font-size: 18px;
    }
    QWidget#PaginaProductos QListWidget::item {
        min-height: 60px; padding: 8px 12px; border-bottom: 1px solid #26344B;
    }
    QWidget#PaginaProductos QListWidget::item:selected {
        background-color: #36564b; color: #FFE0A0;
    }
"""

# Diseño de boton producto.
BOTON_PRODUCTO = """
QPushButton {
                background-color: #233b36;
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
"""

"""Guía visual: aquí se cambian los colores, bordes y tamaños compartidos.

Los selectores #Nombre se refieren al objectName de los widgets.
Los archivos .ui mantienen el diseño de las pantallas hechas en Qt Designer.
"""

# Identidad del bar: azul noche, piedra oscura y oro cálido.
FONDO = "#0B1220"
PANEL = "#121C2B"
PANEL_ELEVADO = "#1A2738"
BORDE = "#34445A"
DORADO = "#D6AE62"
TEXTO = "#F4F2ED"

# Controles comunes para pantallas táctiles; las pantallas pueden añadir
# reglas más específicas para botones de acción o estados peligrosos.
TEMA = """
QToolTip { background: #152235; color: #F4F2ED; border: 1px solid #D6AE62;
    border-radius: 6px; padding: 6px; }
QLineEdit, QComboBox, QSpinBox, QTimeEdit {
    background: #121C2B; color: #F4F2ED; border: 1px solid #34445A;
    border-radius: 9px; padding: 10px 12px; selection-background-color: #D6AE62;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTimeEdit:focus {
    border: 2px solid #D6AE62;
}
QScrollBar:vertical { background: #0B1220; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: #46566B; min-height: 28px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #D6AE62; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

# Diseño de formularios.
FORMULARIOS = """
QDialog, QWidget#Usuarios { background: #0B1020; color: #F4F2ED; }
QLabel { color: #DCE4F0; background: transparent; font-size: 15px; }
QLineEdit, QListWidget { background: #172235; color: #F4F2ED;
    border: 1px solid #34445E; border-radius: 8px; padding: 10px; font-size: 16px; }
QPushButton { background: #D6AE62; color: #101725; border: none;
    border-radius: 8px; padding: 14px; font-size: 16px; font-weight: 600; }
QPushButton:hover { background: #F2C66D; }
QPushButton:disabled { background: #34445E; color: #A8B4C8; }
"""

# Diseño de historial.
HISTORIAL = """
QTableWidget {
        background-color: rgba(41, 41, 56, 205);
        alternate-background-color: rgba(52, 52, 70, 215);
        color: white;
        border: none;
        gridline-color: #414154;
        font-size: 14px;
        selection-background-color: rgba(212, 175, 55, 235);
        selection-color: #20202B;
    }

    QHeaderView::section {
        background-color: rgba(65, 65, 84, 225);
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
"""

# Diseño de catalogo.
CATALOGO = """
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
"""

# Diseño de boton producto.
BOTON_PRODUCTO = """
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
"""

"""Guía visual: aquí se cambian los colores, bordes y tamaños compartidos.

Los selectores #Nombre se refieren al objectName de los widgets.
Los archivos .ui mantienen el diseño de las pantallas hechas en Qt Designer.
"""

# Identidad del bar: azul noche, piedra oscura y oro cálido.
FONDO = "#0b1425"
PANEL = "#111f35"
PANEL_ELEVADO = "#1A2738"
BORDE = "#34445A"
DORADO = "#23d7f4"
TEXTO = "#eaf3ff"

# Controles comunes para pantallas táctiles; las pantallas pueden añadir
# reglas más específicas para botones de acción o estados peligrosos.
TEMA = """
QWidget { font-family: "Segoe UI", "Roboto", sans-serif; }
QPushButton { min-height: 32px; padding: 6px 12px; border-radius: 10px;
    border: 1px solid #267a99; background: #11283f; color: #f5f1e8; }
QPushButton:pressed { background: #1b4263; }
QPushButton:focus { border: 2px solid #f34bcb; }
QPushButton:disabled { color: #8b9eb9; background: #1b293e; }
QComboBox QAbstractItemView::item, QListWidget::item { min-height: 44px; }
QLineEdit, QComboBox, QAbstractSpinBox { min-height: 32px; }
QToolTip { background: #101e34; color: #eaf3ff; border: 1px solid #23d7f4;
    border-radius: 6px; padding: 6px; }
QLineEdit, QComboBox, QSpinBox, QTimeEdit {
    background: #111f35; color: #eaf3ff; border: 1px solid #34445A;
    border-radius: 9px; padding: 10px 12px; selection-background-color: #23d7f4;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTimeEdit:focus {
    border: 2px solid #23d7f4;
}
QScrollBar:vertical { background: #0b1425; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: #46566B; min-height: 28px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #23d7f4; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

# Diseño de formularios.
FORMULARIOS = """
QDialog, QWidget#Usuarios { background: #0b1425; color: #eaf3ff; }
QLabel { color: #DCE4F0; background: transparent; font-size: 15px; }
QLineEdit, QListWidget { background: #1c302c; color: #eaf3ff;
    border: 1px solid #20354f; border-radius: 8px; padding: 10px; font-size: 16px; }
QPushButton { background: #112e45; color: #fff5df; border: none;
    border-radius: 8px; padding: 14px; font-size: 16px; font-weight: 600; }
QPushButton:hover { background: #345652; }
QPushButton:default, QPushButton:checked { background: #28d8f7; color: #071725; }
QPushButton:disabled { background: #20354f; color: #A8B4C8; }
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
        selection-color: #0d192d;
    }

    QHeaderView::section {
        background-color: #29443f;
        color: #25d6f4;
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
        background-color: #0b1425;
        color: #eaf3ff;
    }
    QWidget#PaginaConfiguracion QLabel {
        color: #eaf3ff;
        font-size: 24px;
        font-weight: bold;
        background: transparent;
    }
    QWidget#PaginaConfiguracion QPushButton {
        background-color: #11283f;
        color: #E9E8E3;
        border: 1px solid #24647d;
        border-radius: 10px;
        padding: 14px 18px;
        font-size: 15px;
        font-weight: 600;
        text-align: left;
    }
    QWidget#PaginaConfiguracion QPushButton:hover {
        background-color: #164263;
        color: #85eaff;
        border-color: #ec48c4;
    }
    QWidget#PaginaConfiguracion QPushButton:pressed {
        background-color: #25d6f4;
        color: #111827;
    }
"""

# Diseño de catalogo.
CATALOGO = """
QWidget#PaginaProductos { background-color: #0b1425; }
    QWidget#PaginaProductos QLabel {
        color: #E8E7E2; background: transparent; font-size: 17px;
    }
    QWidget#PaginaProductos QWidget[tarjeta="true"] {
        background-color: #111f35; border: 1px solid #24647d;
        border-radius: 16px;
    }
    QWidget#PaginaProductos QLineEdit {
        background-color: #101e34; color: #eaf3ff;
        border: 1px solid #287b99; border-radius: 10px;
        padding: 8px 14px; font-size: 20px;
        selection-background-color: #ec48c4; selection-color: #0b1425;
    }
    QWidget#PaginaProductos QLineEdit:focus { border: 2px solid #ec48c4; }
    QWidget#PaginaProductos QPushButton {
        background-color: #112e45; color: #eaf3ff;
        border: 1px solid #287b99; border-radius: 12px;
        font-size: 19px; font-weight: bold; padding: 10px 16px;
    }
    QWidget#PaginaProductos QPushButton:hover { border-color: #ec48c4; }
    QWidget#PaginaProductos QPushButton:pressed { background-color: #1a4260; }
    QWidget#PaginaProductos QPushButton#GuardarProducto {
        background-color: #25d6f4; color: #111827; border-color: #25d6f4;
    }
    QWidget#PaginaProductos QPushButton#EliminarProducto {
        background-color: #71343C; border-color: #A65660; color: white;
    }
    QWidget#PaginaProductos QListWidget {
        background-color: #101e34; color: #eaf3ff;
        border: 1px solid #24647d; border-radius: 10px; font-size: 18px;
    }
    QWidget#PaginaProductos QListWidget::item {
        min-height: 60px; padding: 8px 12px; border-bottom: 1px solid #193355;
    }
    QWidget#PaginaProductos QListWidget::item:selected {
        background-color: #1a4260; color: #85f0ff;
    }
"""

# Diseño de boton producto.
BOTON_PRODUCTO = """
QPushButton {
                background-color: #11283f;
                color: #eaf3ff;
                border: 1px solid #354159;
                border-radius: 14px;
                font-size: 18px;
                font-weight: bold;
                padding: 18px;
            }

            QPushButton:hover {
                background-color: #193355;
                color: #85eaff;
                border: 1px solid #ec48c4;
            }
"""


# Controles compartidos: también se aplica a formularios creados al abrir páginas.
TEMA += """
QWidget { color: #eaf3ff; }
QLineEdit, QComboBox, QAbstractSpinBox, QTextEdit, QPlainTextEdit {
    background-color: #101e34; color: #eaf3ff; border: 1px solid #287b99;
    border-radius: 9px; selection-background-color: #164e72; selection-color: white;
}
QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 2px solid #20d9f5;
}
QTableWidget, QTableView, QListWidget, QTreeView {
    background: #0c172a; alternate-background-color: #13283e;
    color: #eaf3ff; border: 1px solid #28516d; gridline-color: #203a54;
    selection-background-color: #174563; selection-color: #8cefff;
}
QHeaderView::section { background: #142c46; color: #79eaff; padding: 10px; border: 1px solid #28516d; }
QCheckBox, QRadioButton { color: #eaf3ff; spacing: 10px; }
QCheckBox::indicator { width: 22px; height: 22px; border: 1px solid #2883a5; border-radius: 5px; background: #101e34; }
QCheckBox::indicator:checked { background: #20d9f5; border: 2px solid #91f2ff; }
QRadioButton::indicator:checked { background: #20d9f5; border: 2px solid #91f2ff; border-radius: 8px; }
QScrollBar:vertical { background: #0b1425; width: 14px; }
QScrollBar::handle:vertical { background: #286a88; min-height: 28px; border-radius: 6px; }
QScrollBar::handle:vertical:hover { background: #20d9f5; }
QScrollBar:horizontal { background: #0b1425; height: 14px; }
QScrollBar::handle:horizontal { background: #286a88; min-width: 28px; border-radius: 6px; }
QTabBar::tab { background: #11283f; color: #afc8e1; padding: 12px 18px; border-bottom: 2px solid #244963; }
QTabBar::tab:selected { color: #79eaff; border-bottom: 2px solid #f34bcb; }
QGroupBox { border: 1px solid #28516d; border-radius: 12px; margin-top: 14px; padding: 12px; }
QGroupBox::title { color: #79eaff; subcontrol-origin: margin; left: 12px; }
QMenu { background: #101e34; color: #eaf3ff; border: 1px solid #287b99; }
QMenu::item:selected { background: #174563; color: #8cefff; }
"""

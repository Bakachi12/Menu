"""Cierre de turno en un cuadro integrado y desplazable."""
from PySide6.QtWidgets import QLabel, QVBoxLayout
from shiboken6 import isValid
from dialogos import DialogoIntegrado
from inventario import PaginaInventario


def abrir_cierre_integrado(ventana, sesion, gestion):
    dialogo = DialogoIntegrado(ventana)
    dialogo.setProperty('compacto', True)
    dialogo.setProperty('anchoCompacto', 980)
    dialogo.setProperty('altoCompacto', 800)
    dialogo.setWindowTitle('Cierre o cambio de turno')
    layout = QVBoxLayout(dialogo)
    layout.setContentsMargins(0, 0, 0, 0)
    pagina = PaginaInventario(sesion, gestion, dialogo, mostrar_cierre=True)
    pagina.layout().setContentsMargins(0, 0, 0, 0)
    # La cabecera del cuadro ya identifica esta operación.
    for nombre in ('TituloInventario', 'SubtituloInventario'):
        for etiqueta in pagina.findChildren(QLabel, nombre):
            if etiqueta.parentWidget() is pagina:
                etiqueta.hide()
    layout.addWidget(pagina)
    try:
        dialogo.exec()
        return pagina
    finally:
        if hasattr(pagina, 'password_admin') and isValid(pagina.password_admin):
            pagina.password_admin.clear()
        dialogo.hide()

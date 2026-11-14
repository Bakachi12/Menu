"""Comprueba Qt y los recursos empaquetados sin abrir los datos del negocio."""
import json
import os
from pathlib import Path
import traceback


def comprobar(destino):
    resultado = {}
    try:
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtCore import QFile, qVersion
        from PySide6.QtGui import QPixmap
        from PySide6.QtUiTools import QUiLoader
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        raiz = Path(__file__).resolve().parent
        ventanas = []
        for nombre in ('inicio.ui', 'pedido.ui', 'confirmar_cobro.ui'):
            archivo = QFile(str(raiz / nombre))
            if not archivo.open(QFile.OpenModeFlag.ReadOnly):
                raise RuntimeError(f'No se pudo abrir {nombre}')
            loader = QUiLoader()
            try:
                ventana = loader.load(archivo)
            finally:
                archivo.close()
            if ventana is None:
                raise RuntimeError(loader.errorString())
            ventanas.append(ventana)
        imagen = QPixmap(str(raiz / 'fondo_bar.png'))
        if imagen.isNull():
            raise RuntimeError('No se pudo cargar el fondo de Tisamar')
        ventanas[0].show()
        app.processEvents()
        ventanas[0].close()
        resultado.update(ok=True, qt=qVersion(), pantallas=len(ventanas),
                         fondo=[imagen.width(), imagen.height()])
    except Exception:
        resultado.update(ok=False, error=traceback.format_exc())
    Path(destino).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if resultado['ok'] else 1

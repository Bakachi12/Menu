"""Only used to drive an isolated emulator's fresh test database, never packaged."""
from pathlib import Path
p=Path('qa-main.py')
s=p.read_text()
s=s.replace('acceso = DialogoAcceso(sesion, ventana)', "acceso = DialogoAcceso(sesion, ventana)\nQTimer.singleShot(2000, lambda: (acceso.password.setText('Admin'), acceso.validar()))")
s=s.replace('# Pantalla de espera automática', "print('ANDROID_QA_LOGIN', bool(sesion.usuario), 'PAGE', paginas.currentWidget().objectName(), flush=True)\n# Pantalla de espera automática")
s=s.replace('acceso = DialogoAcceso(sesion, ventana)', "acceso = DialogoAcceso(sesion, ventana)\nQTimer.singleShot(6000, lambda: print('ANDROID_QA_HOME_FITS', all(a.verticalScrollBar().maximum()==0 for a in ventana.findChildren(QScrollArea) if a.isVisible()), flush=True))")
p.write_text(s)

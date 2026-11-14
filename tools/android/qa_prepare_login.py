"""Only used to drive an isolated emulator's fresh test database, never packaged."""
from pathlib import Path
p=Path('qa-main.py')
s=p.read_text()
s=s.replace('acceso = DialogoAcceso(sesion, ventana)', "acceso = DialogoAcceso(sesion, ventana)\nQTimer.singleShot(2000, lambda: (acceso.password.setText('Admin'), acceso.validar()))")
s=s.replace('# Pantalla de espera automática', "print('ANDROID_QA_LOGIN', bool(sesion.usuario), 'PAGE', paginas.currentWidget().objectName(), flush=True)\n# Pantalla de espera automática")
p.write_text(s)

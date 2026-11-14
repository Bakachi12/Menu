"""PIN local cifrado mediante derivación de clave y límite persistente de intentos."""
import hashlib,hmac,secrets,time


class AccesoPIN:
    def preparar_pines(self):
        with self.conexion() as db:
            db.execute('CREATE TABLE IF NOT EXISTS acceso_pin(usuario_id INTEGER PRIMARY KEY,sal BLOB,resumen BLOB,iteraciones INTEGER,intentos INTEGER NOT NULL DEFAULT 0,bloqueado REAL NOT NULL DEFAULT 0)')

    def usuarios_acceso(self):
        self.preparar_pines()
        with self.conexion() as db:
            return db.execute('SELECT u.id,u.nombre,u.usuario,u.rol,p.usuario_id IS NOT NULL FROM usuarios u LEFT JOIN acceso_pin p ON p.usuario_id=u.id WHERE u.eliminado=0 ORDER BY u.nombre COLLATE NOCASE').fetchall()

    def configurar_pin(self,usuario_id,pin):
        self.exigir_admin()
        if len(pin)!=6 or not pin.isascii() or not pin.isdigit():raise ValueError('El PIN debe tener exactamente 6 números.')
        self.preparar_pines()
        sal=secrets.token_bytes(16)
        resumen=hashlib.pbkdf2_hmac('sha256',pin.encode(),sal,self.ITERACIONES)
        with self.conexion() as db:
            usuario=db.execute('SELECT rol FROM usuarios WHERE id=? AND eliminado=0',(usuario_id,)).fetchone()
            if not usuario:raise ValueError('El usuario ya no existe.')
            if usuario[0]=='admin':raise ValueError('Admin conserva su contraseña para iniciar sesión y autorizar operaciones.')
            db.execute('INSERT INTO acceso_pin VALUES(?,?,?,?,0,0) ON CONFLICT(usuario_id) DO UPDATE SET sal=excluded.sal,resumen=excluded.resumen,iteraciones=excluded.iteraciones,intentos=0,bloqueado=0',(usuario_id,sal,resumen,self.ITERACIONES))

    def iniciar_pin(self,usuario_id,pin):
        self.cerrar()
        self.preparar_pines()
        with self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            fila=db.execute('SELECT p.sal,p.resumen,p.iteraciones,p.intentos,p.bloqueado FROM acceso_pin p JOIN usuarios u ON u.id=p.usuario_id WHERE u.id=? AND u.eliminado=0 AND u.rol!=?',(usuario_id,'admin')).fetchone()
            if not fila:return False
            sal,esperado,vueltas,intentos,bloqueado=fila
            ahora=time.time()
            if bloqueado>ahora:return False
            valido=len(pin)==6 and pin.isascii() and pin.isdigit() and hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',pin.encode(),sal,vueltas),esperado)
            if not valido:
                intentos=0 if bloqueado else intentos
                intentos+=1
                db.execute('UPDATE acceso_pin SET intentos=?,bloqueado=? WHERE usuario_id=?',(intentos,ahora+60 if intentos>=5 else 0,usuario_id))
            else:db.execute('UPDATE acceso_pin SET intentos=0,bloqueado=0 WHERE usuario_id=?',(usuario_id,))
        return self.restaurar(usuario_id) if valido else False


def configurar_pin_seleccionado(pagina):
    from PySide6.QtWidgets import QVBoxLayout,QLabel,QLineEdit,QPushButton
    from PySide6.QtCore import Qt
    from dialogos import DialogoIntegrado
    item=pagina.lista.currentItem()
    if item is None:pagina.mensaje.setText('Selecciona un usuario para configurar su PIN.');return
    d=DialogoIntegrado(pagina.window());d.setProperty('compacto',True);d.setWindowTitle('Configurar PIN de usuario')
    layout=QVBoxLayout(d);layout.addWidget(QLabel('Escribe un PIN de 6 números. Admin conserva su contraseña.'))
    campos=[]
    for titulo in ('Nuevo PIN','Repetir PIN'):
        layout.addWidget(QLabel(titulo));campo=QLineEdit();campo.setEchoMode(QLineEdit.EchoMode.Password);campo.setMaxLength(6);campo.setInputMethodHints(Qt.InputMethodHint.ImhDigitsOnly);layout.addWidget(campo);campos.append(campo)
    estado=QLabel();layout.addWidget(estado)
    def guardar():
        try:
            if campos[0].text()!=campos[1].text():raise ValueError('Los PIN no coinciden.')
            pagina.sesion.configurar_pin(item.data(Qt.ItemDataRole.UserRole),campos[0].text())
        except (ValueError,PermissionError) as error:estado.setText(str(error));return
        d.accept();pagina.mensaje.setText('PIN guardado. El usuario puede seleccionarse e iniciar con su PIN.')
    boton=QPushButton('Guardar PIN');boton.clicked.connect(guardar);layout.addWidget(boton);d.exec()
    for campo in campos:campo.clear()

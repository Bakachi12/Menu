"""Ficha de contacto y selector de cuentas de barra."""
import sqlite3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout,QLabel,QLineEdit,QPlainTextEdit,QCheckBox,QPushButton,QListWidget,QListWidgetItem
from dialogos import DialogoIntegrado
from clientes import es_barra,centimos


def editar_ficha(ventana, gestion, identificador):
    cliente=gestion.obtener(identificador)
    if not cliente: return False
    d=DialogoIntegrado(ventana);d.setProperty('compacto',True);d.setWindowTitle('Editar cliente')
    layout=QVBoxLayout(d)
    campos={}
    for clave,titulo in [('nombre','Nombre'),('correo','Correo (opcional)'),('telefono','Teléfono (opcional)')]:
        layout.addWidget(QLabel(titulo))
        campo=QLineEdit(cliente.get(clave,''));campo.setMaxLength(254 if clave=='correo' else 80)
        layout.addWidget(campo);campos[clave]=campo
    frecuente=QCheckBox('Cliente frecuente');frecuente.setChecked(cliente.get('frecuente',False));layout.addWidget(frecuente)
    layout.addWidget(QLabel('Notas y preferencias (opcional)'))
    notas=QPlainTextEdit(cliente.get('notas',''));notas.setMaximumHeight(100);layout.addWidget(notas)
    estado=QLabel();estado.setWordWrap(True);layout.addWidget(estado)
    guardar=QPushButton('Guardar cliente');layout.addWidget(guardar)
    def aceptar():
        try:
            gestion.editar(identificador,**{k:v.text() for k,v in campos.items()},frecuente=frecuente.isChecked(),notas=notas.toPlainText())
        except (ValueError,PermissionError,sqlite3.Error) as error:
            estado.setText(str(error));return
        d.accept()
    guardar.clicked.connect(aceptar)
    return d.exec()==d.DialogCode.Accepted


def elegir_cuenta_barra(ventana,gestion,pedidos):
    from PySide6.QtWidgets import QWidget,QScrollArea,QHBoxLayout,QFrame
    d=DialogoIntegrado(ventana);d.setProperty('compacto',True);d.setWindowTitle('Barra · Tus cuentas');d.setProperty('anchoCompacto',1100);d.setProperty('altoCompacto',850)
    d.setStyleSheet('''
        QWidget { background: #0b1425; color: #eaf5ff; }
        QLabel { background: transparent; border: none; font-size: 17px; }
        QLineEdit { background: #111e34; color: white; border: 1px solid #20cfff; border-radius: 10px; padding: 12px; font-size: 18px; min-height: 28px; }
        QPushButton { background: #10263b; color: #75eaff; border: 1px solid #20cfff; border-radius: 10px; padding: 12px; font-size: 17px; min-height: 32px; }
        QPushButton:hover { background: #183952; border-color: #fa43bf; }
        QPushButton#AgregarConsumosBarra { background: #1cd5ef; color: #061625; font-weight: bold; }
        QPushButton#NuevaCuentaBarra { background: #432044; color: #ffb9ec; border-color: #ff48c6; }
        QFrame#CuentaBarra { background: #111f34; border: 1px solid #254d73; border-radius: 14px; }
        QScrollArea { background: transparent; border: none; }
    ''')
    layout=QVBoxLayout(d);layout.setSpacing(12)
    ayuda=QLabel('Busca al cliente y pulsa Agregar consumos para abrir su cuenta.');ayuda.setWordWrap(True);layout.addWidget(ayuda)
    buscar=QLineEdit();buscar.setPlaceholderText('Buscar cliente en barra…');layout.addWidget(buscar)
    area=QScrollArea();area.setWidgetResizable(True);area.setFrameShape(QFrame.Shape.NoFrame)
    area.setMinimumHeight(120);area.setMaximumHeight(560)
    contenido=QWidget();cuentas=QVBoxLayout(contenido);cuentas.setContentsMargins(0,0,0,0);cuentas.setSpacing(12)
    area.setWidget(contenido);layout.addWidget(area,1)
    resultado=[];tarjetas=[]
    def seleccionar(identificador):
        resultado.append(identificador);d.accept()
    clientes=[c for c in gestion.listar() if es_barra(c['mesa'])]
    for c in clientes:
        productos=[p for p in pedidos.get(c['mesa'],[]) if p.get('cliente_id')==c['id']]
        total=sum(centimos(p) for p in productos)
        tarjeta=QFrame();tarjeta.setObjectName('CuentaBarra')
        caja=QVBoxLayout(tarjeta);caja.setContentsMargins(16,14,16,14)
        fila=QHBoxLayout()
        nombre=QLabel(c['nombre']);nombre.setTextFormat(Qt.TextFormat.PlainText);nombre.setWordWrap(True)
        nombre.setStyleSheet('font-size: 21px; font-weight: bold; color: #eaf5ff;')
        importe=QLabel(f'B/.{total/100:.2f}');importe.setStyleSheet('font-size: 23px; font-weight: bold; color: #50e5ff;')
        fila.addWidget(nombre,1);fila.addWidget(importe);caja.addLayout(fila)
        detalle=QLabel(f'{len(productos)} consumos · Cuenta individual');detalle.setStyleSheet('color: #a6bad4; font-size: 15px;');caja.addWidget(detalle)
        abrir=QPushButton('Agregar consumos  →');abrir.setObjectName('AgregarConsumosBarra');abrir.setAccessibleName('Agregar consumos a '+c['nombre'])
        abrir.clicked.connect(lambda checked=False,i=c['id']:seleccionar(i));caja.addWidget(abrir)
        cuentas.addWidget(tarjeta);tarjetas.append((tarjeta,c['nombre'].casefold()))
    vacio=QLabel();vacio.setWordWrap(True);cuentas.addWidget(vacio);cuentas.addStretch()
    def filtrar(texto=''):
        visibles=0
        for tarjeta,nombre in tarjetas:
            coincide=texto.strip().casefold() in nombre;tarjeta.setVisible(coincide);visibles+=int(coincide)
        vacio.setText('No hay coincidencias.' if tarjetas else 'Aún no hay cuentas de barra. Abre una desde Clientes.')
        vacio.setVisible(visibles==0)
    buscar.textChanged.connect(filtrar);filtrar()
    nuevo=QPushButton('+ Nueva cuenta · Elegir cliente');nuevo.setObjectName('NuevaCuentaBarra')
    nuevo.clicked.connect(lambda:seleccionar('clientes'));layout.addWidget(nuevo)
    d.exec()
    return resultado[0] if resultado else None

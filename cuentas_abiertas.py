from PySide6.QtWidgets import QVBoxLayout,QLabel,QLineEdit,QPushButton,QScrollArea,QWidget
from dialogos import DialogoIntegrado
from clientes import centimos,nombre_operacion,es_barra


def resumir_cuentas(clientes,pedidos):
    claves={c['mesa'] for c in clientes if c['mesa']} | {k for k,v in pedidos.items() if v}
    cuentas=[]
    for clave in claves:
        asignados=[c['nombre'] for c in clientes if c['mesa']==clave]
        nombres=list(dict.fromkeys(asignados+[p['cliente_nombre'] for p in pedidos.get(clave,[]) if p.get('cliente_nombre')]))
        cuentas.append(dict(clave=clave,titulo=nombre_operacion(clave),clientes=', '.join(nombres),total=sum(centimos(p) for p in pedidos.get(clave,[]))))
    return sorted(cuentas,key=lambda c:c['titulo'].casefold())


def elegir_cuenta(ventana,clientes,pedidos):
    d=DialogoIntegrado(ventana);d.setProperty('compacto',True);d.setWindowTitle('Cuentas abiertas');d.setProperty('anchoCompacto',1100);d.setProperty('altoCompacto',850)
    d.setStyleSheet('QLabel { color: #dcedff; font-size: 17px; } QLineEdit { background: #111e34; color: white; border: 1px solid #20cfff; padding: 12px; font-size: 18px; } QPushButton { background: #11283f; color: #78eaff; border: 1px solid #20cfff; border-radius: 12px; padding: 14px; font-size: 18px; text-align: left; min-height: 64px; } QPushButton:hover { background: #213a55; border-color: #fa43bf; } QScrollArea { border: none; background: transparent; }')
    layout=QVBoxLayout(d)
    resumen=resumir_cuentas(clientes,pedidos)
    layout.addWidget(QLabel(f"{len(resumen)} cuentas · Total B/.{sum(c['total'] for c in resumen)/100:.2f}"))
    buscar=QLineEdit();buscar.setPlaceholderText('Buscar mesa o cliente…');layout.addWidget(buscar)
    area=QScrollArea();area.setWidgetResizable(True);area.setMaximumHeight(620);area.setMinimumHeight(120)
    contenido=QWidget();lista=QVBoxLayout(contenido);area.setWidget(contenido);layout.addWidget(area)
    resultado=[];botones=[]
    def elegir(clave):resultado.append(clave);d.accept()
    for cuenta in resumen:
        nombre=cuenta['titulo'];detalle=cuenta['clientes'] or 'Cuenta general'
        boton=QPushButton(f"{nombre}     B/.{cuenta['total']/100:.2f}\n{detalle}\nAbrir cuenta →")
        boton.clicked.connect(lambda checked=False,k=cuenta['clave']:elegir(k));lista.addWidget(boton)
        botones.append((boton,(nombre+' '+detalle).casefold()))
    vacio=QLabel();vacio.setWordWrap(True);lista.addWidget(vacio);lista.addStretch()
    def filtrar(texto=''):
        visibles=0
        for boton,nombre in botones:
            coincide=texto.strip().casefold() in nombre;boton.setVisible(coincide);visibles+=int(coincide)
        vacio.setText('No hay coincidencias.' if resumen else 'No hay cuentas abiertas.');vacio.setVisible(not visibles)
    buscar.textChanged.connect(filtrar);filtrar();d.exec()
    return resultado[0] if resultado else None

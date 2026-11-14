"""Registro por sesión de Venta libre sin crear turnos de caja asignados."""
import json
from datetime import datetime

def preparar(db):
    db.execute('CREATE TABLE IF NOT EXISTS hojas_venta_libre(id INTEGER PRIMARY KEY,usuario_id INTEGER,nombre TEXT,apertura TEXT,cierre TEXT)')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS hoja_libre_abierta ON hojas_venta_libre(usuario_id) WHERE cierre IS NULL')
    db.execute('CREATE TABLE IF NOT EXISTS hoja_libre_productos(hoja_id INTEGER,producto_id INTEGER,nombre TEXT,categoria TEXT,inicial INTEGER,agregada INTEGER DEFAULT 0,vendida INTEGER DEFAULT 0,importe INTEGER DEFAULT 0,saldo INTEGER,PRIMARY KEY(hoja_id,producto_id))')

def abrir(db,usuario,cantidades,actuales):
    preparar(db)
    cerrar(db,usuario['id'])
    hoja=db.execute('INSERT INTO hojas_venta_libre(usuario_id,nombre,apertura) VALUES(?,?,?)',(usuario['id'],usuario['nombre'],datetime.now().isoformat(sep=' ',timespec='seconds'))).lastrowid
    for pid,cantidad in cantidades.items():
        nombre,categoria,_=actuales[pid]
        db.execute('INSERT INTO hoja_libre_productos(hoja_id,producto_id,nombre,categoria,inicial) VALUES(?,?,?,?,?)',(hoja,pid,nombre,categoria,cantidad))

def cerrar(db,usuario_id):
    preparar(db)
    for (hoja,) in db.execute('SELECT id FROM hojas_venta_libre WHERE usuario_id=? AND cierre IS NULL',(usuario_id,)).fetchall():
        db.execute('UPDATE hoja_libre_productos SET saldo=inicial+agregada-vendida WHERE hoja_id=?',(hoja,))
        db.execute('UPDATE hojas_venta_libre SET cierre=? WHERE id=?',(datetime.now().isoformat(sep=' ',timespec='seconds'),hoja))

def entrada(db,usuario,producto_id,cantidad,nombre,categoria):
    hoja=db.execute('SELECT id FROM hojas_venta_libre WHERE usuario_id=? AND cierre IS NULL',(usuario['id'],)).fetchone()
    if hoja:
        db.execute('INSERT INTO hoja_libre_productos(hoja_id,producto_id,nombre,categoria,inicial,agregada) VALUES(?,?,?,?,0,?) ON CONFLICT(hoja_id,producto_id) DO UPDATE SET agregada=agregada+excluded.agregada',(hoja[0],producto_id,nombre,categoria,cantidad))

def venta(db,usuario,productos):
    preparar(db)
    hoja=db.execute('SELECT id FROM hojas_venta_libre WHERE usuario_id=? AND cierre IS NULL',(usuario['id'],)).fetchone()
    if not hoja:return
    for p in productos:
        if p.get('seccion')!='Bebidas':continue
        db.execute('UPDATE hoja_libre_productos SET vendida=vendida+1,importe=importe+? WHERE hoja_id=? AND nombre=? AND categoria=?',(round(p['precio']*100),hoja[0],p['nombre'],p.get('categoria','General')))
    return hoja[0]

def reporte(sesion):
    if not sesion.usuario:return []
    resultado=[]
    with sesion.conexion() as db:
        preparar(db)
        condicion='' if sesion.es_admin() else ' AND h.usuario_id=?'
        parametros=() if sesion.es_admin() else (sesion.usuario['id'],)
        for fila in db.execute('SELECT h.id,h.nombre,h.apertura,h.cierre,p.nombre,p.categoria,p.inicial,p.agregada,p.vendida,p.importe,p.saldo FROM hojas_venta_libre h JOIN hoja_libre_productos p ON p.hoja_id=h.id WHERE 1=1'+condicion+' ORDER BY h.id DESC,p.nombre',parametros):
            hid,nombre,inicio,fin,producto,categoria,inicial,agregada,vendida,importe,saldo=fila
            resultado.append(dict(turno_id=-hid,asignacion_fecha=inicio,cierre_fecha=fin,cajero='Venta libre · '+nombre,estado='cerrado' if fin else 'activo',producto=producto+' · '+categoria,nombre=producto,categoria=categoria,recibida=inicial,agregada=agregada,vendida=vendida,dinero_centimos=importe,entregada=saldo if saldo is not None else inicial+agregada-vendida,faltante=None,sobrante=None))
    return resultado

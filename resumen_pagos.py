"""Totals of recorded payments belonging to a single inventory sheet."""
import json
from decimal import Decimal,ROUND_HALF_UP,InvalidOperation

FORMAS_HOJA=('Efectivo','Yappy','Clave','Visa')

def resumen_pagos_hoja(sesion,turno_id,filas=None,*,incluir_cocina=False):
    if not sesion.usuario:raise PermissionError('Inicia sesión para consultar los cobros.')
    ambiguas=0
    contenido="productos" if filas is not None else "NULL"
    with sesion.conexion() as db:
        if turno_id>=0:
            sesion.exigir_admin()
            ventas=db.execute(f'SELECT metodo_pago,total,{contenido} FROM ventas WHERE turno_id=?',(turno_id,)).fetchall()
        else:
            hoja=db.execute('SELECT usuario_id,apertura,cierre FROM hojas_venta_libre WHERE id=?',(-turno_id,)).fetchone()
            if not hoja:raise ValueError('La hoja de Venta libre ya no existe.')
            usuario,inicio,fin=hoja
            if not sesion.es_admin() and usuario!=sesion.usuario['id']:
                raise PermissionError('Solo puedes consultar tus propias hojas.')
            columnas={f[1] for f in db.execute('PRAGMA table_info(ventas)')}
            enlace='hoja_libre_id' if 'hoja_libre_id' in columnas else 'NULL'
            ventas=[]
            for metodo,total,productos,asociada,fecha in db.execute(f'''SELECT metodo_pago,total,{contenido},{enlace},fecha FROM ventas
                    WHERE turno_id IS NULL AND cajero_id=? AND
                    ({enlace}=? OR ({enlace} IS NULL AND fecha>=? AND (? IS NULL OR fecha<=?)))''',
                    (usuario,-turno_id,inicio,fin,fin)):
                if asociada is not None:
                    ventas.append((metodo,total,productos));continue
                # Old receipts had no sheet ID. Never count the same receipt in
                # two sessions that opened/closed within the same second.
                coincidencias=db.execute('''SELECT COUNT(*) FROM hojas_venta_libre WHERE usuario_id=?
                    AND apertura<=? AND (cierre IS NULL OR cierre>=?)''',(usuario,fecha,fecha)).fetchone()[0]
                if coincidencias==1:ventas.append((metodo,total,productos))
                else:ambiguas+=1
    importes=dict.fromkeys(FORMAS_HOJA,0)
    cocina={}
    claves={(f.get('nombre'),f.get('categoria')) for f in filas or [] if f.get('nombre') is not None}
    nombres={f['producto'] for f in filas or []}
    for metodo,total,productos in ventas:
        if filas is not None:
            try:lista=json.loads(productos)
            except (json.JSONDecodeError,TypeError) as error:raise ValueError('Una venta contiene productos inválidos.') from error
            if not isinstance(lista,list) or any(not isinstance(p,dict) for p in lista):
                raise ValueError('Una venta contiene productos inválidos.')
            importe_producto=0
            for p in lista:
                if p.get('seccion')=='Cocina' and incluir_cocina:
                    try:precio=round(float(p['precio'])*100)
                    except (KeyError,ValueError,TypeError,OverflowError) as error:raise ValueError('Un plato contiene un precio inválido.') from error
                    clave_plato=(p.get('nombre','Plato'),p.get('preparacion',''),p.get('acompanamiento',''),p.get('extra',''),precio)
                    plato=cocina.setdefault(clave_plato,dict(nombre=clave_plato[0],preparacion=clave_plato[1],acompanamiento=clave_plato[2],extra=clave_plato[3],unidades=0,centimos=0))
                    plato['unidades']+=1;plato['centimos']+=precio;importe_producto+=precio
                    continue
                if p.get('seccion','Bebidas')!='Bebidas':continue
                clave=(p.get('nombre'),p.get('categoria','General'))
                coincide=clave in claves if claves else f'{clave[0]} · {clave[1]}' in nombres
                if not coincide:continue
                try:importe_producto+=round(float(p['precio'])*100)
                except (KeyError,ValueError,TypeError,OverflowError) as error:raise ValueError('Una venta contiene un precio inválido.') from error
            if importe_producto==0:continue
            importes[metodo or 'Sin registrar']=importes.get(metodo or 'Sin registrar',0)+importe_producto
            continue
        etiqueta=metodo or 'Sin registrar'
        try:importe=Decimal(str(total))*100
        except (InvalidOperation,ValueError,TypeError) as error:
            raise ValueError('Un cobro contiene un importe inválido.') from error
        if not importe.is_finite():raise ValueError('Un cobro contiene un importe inválido.')
        importes[etiqueta]=importes.get(etiqueta,0)+int(importe.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    return dict(importes=importes,total_centimos=sum(importes.values()),ambiguas=ambiguas,cocina=list(cocina.values()),cocina_centimos=sum(p['centimos'] for p in cocina.values()),cocina_unidades=sum(p['unidades'] for p in cocina.values()))

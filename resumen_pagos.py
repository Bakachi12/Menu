"""Totals of recorded payments belonging to a single inventory sheet."""
from decimal import Decimal,ROUND_HALF_UP,InvalidOperation

FORMAS_HOJA=('Efectivo','Yappy','Clave','Visa')

def resumen_pagos_hoja(sesion,turno_id):
    if not sesion.usuario:raise PermissionError('Inicia sesión para consultar los cobros.')
    ambiguas=0
    with sesion.conexion() as db:
        if turno_id>=0:
            sesion.exigir_admin()
            ventas=db.execute('SELECT metodo_pago,total FROM ventas WHERE turno_id=?',(turno_id,)).fetchall()
        else:
            hoja=db.execute('SELECT usuario_id,apertura,cierre FROM hojas_venta_libre WHERE id=?',(-turno_id,)).fetchone()
            if not hoja:raise ValueError('La hoja de Venta libre ya no existe.')
            usuario,inicio,fin=hoja
            if not sesion.es_admin() and usuario!=sesion.usuario['id']:
                raise PermissionError('Solo puedes consultar tus propias hojas.')
            columnas={f[1] for f in db.execute('PRAGMA table_info(ventas)')}
            enlace='hoja_libre_id' if 'hoja_libre_id' in columnas else 'NULL'
            ventas=[]
            for metodo,total,asociada,fecha in db.execute(f'''SELECT metodo_pago,total,{enlace},fecha FROM ventas
                    WHERE turno_id IS NULL AND cajero_id=? AND
                    ({enlace}=? OR ({enlace} IS NULL AND fecha>=? AND (? IS NULL OR fecha<=?)))''',
                    (usuario,-turno_id,inicio,fin,fin)):
                if asociada is not None:
                    ventas.append((metodo,total));continue
                # Old receipts had no sheet ID. Never count the same receipt in
                # two sessions that opened/closed within the same second.
                coincidencias=db.execute('''SELECT COUNT(*) FROM hojas_venta_libre WHERE usuario_id=?
                    AND apertura<=? AND (cierre IS NULL OR cierre>=?)''',(usuario,fecha,fecha)).fetchone()[0]
                if coincidencias==1:ventas.append((metodo,total))
                else:ambiguas+=1
    importes=dict.fromkeys(FORMAS_HOJA,0)
    for metodo,total in ventas:
        etiqueta=metodo or 'Sin registrar'
        try:importe=Decimal(str(total))*100
        except (InvalidOperation,ValueError,TypeError) as error:
            raise ValueError('Un cobro contiene un importe inválido.') from error
        if not importe.is_finite():raise ValueError('Un cobro contiene un importe inválido.')
        importes[etiqueta]=importes.get(etiqueta,0)+int(importe.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    return dict(importes=importes,total_centimos=sum(importes.values()),ambiguas=ambiguas)

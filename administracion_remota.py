"""Administration operations using an independent authenticated session."""
from datetime import date
from decimal import Decimal,InvalidOperation

class AdministracionRemota:
    def __init__(self,ruta,empleado):
        from usuarios import SesionUsuarios
        from inventario import GestionTurnos
        self.sesion=SesionUsuarios(ruta)
        if not self.sesion.restaurar(empleado['id']):raise PermissionError('Inicia sesión de nuevo.')
        self.sesion.exigir_admin()
        self.gestion=GestionTurnos(self.sesion)

    def panel(self,desde=None,hasta=None):
        desde=date.fromisoformat(desde) if desde else date.today()
        hasta=date.fromisoformat(hasta) if hasta else desde
        if desde>hasta:raise ValueError('Desde no puede ser posterior a Hasta.')
        with self.sesion.conexion() as db:
            ventas=[dict(id=i,fecha=f,mesa=m,cliente=c or '',total_centimos=round(t*100),metodo=p or 'Sin registrar',cajero=n or 'Sin registrar') for i,f,m,c,t,p,n in db.execute('''
                SELECT v.id,v.fecha,v.mesa,v.cliente,v.total,v.metodo_pago,u.nombre
                FROM ventas v LEFT JOIN usuarios u ON u.id=v.cajero_id
                WHERE substr(v.fecha,1,10)>=? AND substr(v.fecha,1,10)<=? ORDER BY v.id DESC
                ''',(desde.isoformat(),hasta.isoformat()))]
            productos=[dict(id=i,nombre=n,categoria=c,precio_centimos=p,seccion=s,activo=a) for i,n,c,p,s,a in db.execute('SELECT id,nombre,categoria,precio_centimos,seccion,activo FROM productos ORDER BY nombre COLLATE NOCASE')]
            abiertas=db.execute('SELECT COUNT(*) FROM pedidos_abiertos').fetchone()[0]
        importes=dict(Efectivo=0,Yappy=0,Clave=0,Visa=0)
        for venta in ventas:importes[venta['metodo']]=importes.get(venta['metodo'],0)+venta['total_centimos']
        hojas=[f for f in self.gestion.hoja_inventarios() if f.get('asignacion_fecha') and desde.isoformat()<=f['asignacion_fecha'][:10]<=hasta.isoformat()]
        hojas.sort(key=lambda f:f['asignacion_fecha'].replace('T',' '),reverse=True)
        return dict(desde=desde.isoformat(),hasta=hasta.isoformat(),usuario=self.sesion.usuario['nombre'],ventas=ventas,
                    total_centimos=sum(v['total_centimos'] for v in ventas),pagos=importes,productos=productos,
                    inventario=[dict(id=i,nombre=n,categoria=c,cantidad=q) for i,n,c,q in self.gestion.existencias()],
                    hojas=hojas,turno=self.gestion.turno_abierto(),cuentas_abiertas=abiertas,
                    usuarios=[dict(id=i,nombre=n,usuario=u,rol='venta_libre' if t=='venta_libre' else r) for i,n,u,r,t in self.sesion.listar()])

    def hoja(self,turno_id):
        from resumen_pagos import resumen_pagos_hoja
        filas=[f for f in self.gestion.hoja_inventarios() if f['turno_id']==turno_id]
        if not filas:raise ValueError('No se encontró esa hoja de inventario.')
        return dict(filas=filas,resumen=resumen_pagos_hoja(self.sesion,turno_id,filas,incluir_cocina=True))

    def cambiar(self,accion,datos):
        if not isinstance(datos,dict):raise ValueError('Datos inválidos.')
        if accion=='precio':
            pid=datos.get('producto_id');anterior=datos.get('precio_anterior')
            if type(pid) is not int or not 0<pid<2**63 or type(anterior) is not int:raise ValueError('Selecciona un producto válido.')
            try:precio=Decimal(str(datos.get('precio','')))
            except InvalidOperation:raise ValueError('Escribe un precio válido.') from None
            if not precio.is_finite() or not 0<precio<=999999 or precio*100!=(precio*100).to_integral_value():raise ValueError('El precio debe ser positivo y tener hasta dos decimales.')
            with self.sesion.conexion() as db:
                cursor=db.execute('UPDATE productos SET precio_centimos=? WHERE id=? AND precio_centimos=?',(int(precio*100),pid,anterior))
                if cursor.rowcount!=1:raise ValueError('El producto cambió en otra terminal. Actualiza antes de guardar.')
        elif accion=='entrada':
            pid=datos.get('producto_id');cantidad=datos.get('cantidad')
            if type(pid) is not int or not 0<pid<2**63 or type(cantidad) is not int or not 1<=cantidad<=999999:raise ValueError('Selecciona el producto y una cantidad entera.')
            self.gestion.registrar_entrada(pid,cantidad)
        elif accion=='usuario':
            for campo in ('nombre','usuario','password','rol'):
                if not isinstance(datos.get(campo),str):raise ValueError('Completa los datos del usuario.')
            self.sesion.crear(datos['nombre'],datos['usuario'],datos['password'],datos['rol'])
        else:raise ValueError('Acción de administración no disponible.')
        return dict(mensaje='Cambios guardados en la PC de caja.')

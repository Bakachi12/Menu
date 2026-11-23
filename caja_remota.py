"""Operaciones de caja web. Toda escritura ocurre en SQLite de la PC principal."""
import json
import sqlite3
from contextlib import contextmanager
from uuid import uuid4

from clientes import VENTA_RAPIDA, cuenta_barra, es_barra, nombre_operacion
from cocina import sincronizar_comandas, validar_aumentos, COCINA
from datos import registrar_venta, METODOS_PAGO


class SesionRemota:
    """Identidad aislada de la sesión de Windows."""
    def __init__(self, ruta, empleado):
        self.ruta = str(ruta)
        self.usuario = empleado
        self.inventario_libre_verificado = False

    @contextmanager
    def conexion(self):
        db = sqlite3.connect(self.ruta, timeout=8)
        try:
            with db:
                yield db
        finally:
            db.close()

    def es_admin(self):
        return self.usuario['rol'] == 'admin'

    def es_venta_libre(self):
        return self.usuario.get('tipo') == 'venta_libre'


def turno_activo(db, empleado, verificado=False):
    if empleado['rol'] == 'admin':
        return None
    if empleado.get('tipo') == 'venta_libre':
        if verificado:
            return None
        raise PermissionError('Venta libre requiere verificación local de inventario; usa la caja Windows.')
    fila = db.execute("SELECT id FROM turnos WHERE usuario_id=? AND estado='activo' ORDER BY id DESC LIMIT 1",
                      (empleado['id'],)).fetchone()
    if not fila:
        raise PermissionError('Abre y confirma tu turno en la PC antes de operar.')
    return fila[0]


def permitir(empleado, cobrar=False):
    if empleado['rol'] not in ('admin', 'mesas', 'mesero'):
        raise PermissionError('Tu perfil no puede usar la caja.')
    if cobrar and empleado['rol'] == 'mesero':
        raise PermissionError('El mesero no puede cobrar.')


def resumen(solicitudes, empleado):
    permitir(empleado)
    data = solicitudes.resumen()
    with solicitudes.conexion() as db:
        clientes = [dict(row) for row in db.execute('SELECT id,nombre,mesa FROM clientes ORDER BY nombre')]
        destinos = [(VENTA_RAPIDA, [])]
        for cliente in clientes:
            clave = cuenta_barra(cliente)
            if cliente['mesa'] in (None, clave):
                destinos.append((clave, [cliente]))
        for clave, personas in destinos:
            fila = db.execute('SELECT productos FROM pedidos_abiertos WHERE mesa=?', (clave,)).fetchone()
            cuenta = json.loads(fila[0]) if fila else []
            data['mesas'].append(dict(nombre=clave, clientes=personas, cuenta=cuenta,
                                      total_centimos=sum(round(p['precio'] * 100) for p in cuenta)))
    for m in data['mesas']:
        m['titulo'] = nombre_operacion(m['nombre'])
        m['tipo'] = 'rapida' if m['nombre'] == VENTA_RAPIDA else 'barra' if es_barra(m['nombre']) else 'mesa'
        m['version'] = json.dumps(m['cuenta'], ensure_ascii=False, sort_keys=True)
    data['puede_cobrar'] = empleado['rol'] != 'mesero'
    return data


def destino(solicitudes, db, mesa, cliente_id=None, asignar=False):
    if mesa == VENTA_RAPIDA and cliente_id is None:
        return None
    if es_barra(mesa):
        fila = db.execute('SELECT id,nombre,mesa FROM clientes WHERE id=?', (mesa.split(':', 2)[1],)).fetchone()
        if not fila or cuenta_barra(fila) != mesa or cliente_id not in (None, fila['id']):
            raise ValueError('Selecciona un cliente de barra válido.')
        if asignar and fila['mesa'] is None:
            db.execute('UPDATE clientes SET mesa=? WHERE id=?', (mesa, fila['id']))
        elif fila['mesa'] != mesa:
            raise ValueError('La asignación del cliente ha cambiado.')
        return fila['id']
    solicitudes.validar_destino(db, mesa, cliente_id)
    return cliente_id


def modificar(solicitudes, empleado, datos, verificado=False):
    permitir(empleado)
    mesa = datos.get('mesa')
    accion = datos.get('accion')
    version = datos.get('version')
    if not isinstance(mesa, str) or len(mesa) > 120 or accion not in ('agregar', 'retirar'):
        raise ValueError('Operación inválida.')
    if not isinstance(version, str) or len(version) > 30000:
        raise ValueError('Actualiza la cuenta antes de modificarla.')
    with solicitudes.conexion() as db:
        db.execute('BEGIN IMMEDIATE')
        turno_activo(db, empleado, verificado) if empleado['rol'] == 'mesas' else None
        destino(solicitudes, db, mesa, asignar=accion == "agregar")
        fila = db.execute('SELECT productos FROM pedidos_abiertos WHERE mesa=?', (mesa,)).fetchone()
        anterior = json.loads(fila[0]) if fila else []
        if json.dumps(anterior, ensure_ascii=False, sort_keys=True) != version:
            raise ValueError('La cuenta cambió en otra terminal. Actualiza y vuelve a intentar.')
        cuenta = list(anterior)
        if accion == 'agregar':
            identificador = datos.get('producto_id')
            if type(identificador) is not int:
                raise ValueError('Selecciona un producto.')
            producto = solicitudes.producto_solicitado(db, identificador, datos.get('seleccion'))
            cliente_id = destino(solicitudes, db, mesa, datos.get('cliente_id'))
            if cliente_id is not None:
                producto['cliente_id'] = cliente_id
            if next((p['seccion'] for p in solicitudes.catalogo(db) if p['id'] == identificador), None) == COCINA:
                producto['unidad_cocina'] = uuid4().hex
            cuenta.append(producto)
        else:
            indice = datos.get('indice')
            if type(indice) is not int or not 0 <= indice < len(cuenta):
                raise ValueError('Producto no encontrado. Actualiza.')
            cuenta.pop(indice)
        validar_aumentos(db, anterior, cuenta)
        sincronizar_comandas(db, mesa, anterior, cuenta)
        db.execute('INSERT INTO pedidos_abiertos(mesa,productos) VALUES(?,?) '
                   'ON CONFLICT(mesa) DO UPDATE SET productos=excluded.productos',
                   (mesa, json.dumps(cuenta, ensure_ascii=False)))
    return {'cuenta': cuenta}


def cobrar(solicitudes, empleado, datos, verificado=False):
    permitir(empleado, cobrar=True)
    mesa, metodo, version = datos.get('mesa'), datos.get('metodo_pago'), datos.get('version')
    if not isinstance(mesa, str) or len(mesa) > 120 or metodo not in METODOS_PAGO or not isinstance(version, str):
        raise ValueError('Cobro inválido.')
    with solicitudes.conexion() as db:
        destino(solicitudes, db, mesa)
        fila = db.execute('SELECT productos FROM pedidos_abiertos WHERE mesa=?', (mesa,)).fetchone()
        cuenta = json.loads(fila[0]) if fila else []
        if not cuenta or json.dumps(cuenta, ensure_ascii=False, sort_keys=True) != version:
            raise ValueError('La cuenta cambió o está vacía. Actualiza antes de cobrar.')
        turno_id = turno_activo(db, empleado, verificado)
        nombres = ', '.join(r[0] for r in db.execute('SELECT nombre FROM clientes WHERE mesa=?', (mesa,)))
    sesion = SesionRemota(solicitudes.ruta, empleado)
    sesion.inventario_libre_verificado = verificado
    venta_id = registrar_venta(sesion, mesa, nombres, cuenta, turno_id,
                               metodo_pago=metodo, verificar_cuenta=True)
    return {'venta_id': venta_id, 'mensaje': 'Cobro registrado en la PC principal.'}


def historial(solicitudes, empleado):
    permitir(empleado, cobrar=True)
    with solicitudes.conexion() as db:
        return [dict(id=r[0], fecha=r[1], mesa=r[2], total=r[3], metodo_pago=r[4])
                for r in db.execute('SELECT id,fecha,mesa,total,metodo_pago FROM ventas WHERE cajero_id=? ORDER BY id DESC LIMIT 80',
                                    (empleado['id'],))]

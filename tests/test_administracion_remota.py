import json,tempfile,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from usuarios import SesionUsuarios
from datos import inicializar_catalogo,registrar_venta
from inventario import GestionTurnos
from pedidos_table import SolicitudesTable,ServidorTable

class AdministracionRemotaTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.iteraciones=patch.object(SesionUsuarios,'ITERACIONES',1000);self.iteraciones.start();self.addCleanup(self.iteraciones.stop)
        self.ruta=Path(self.tmp.name)/'ventas.db'
        admin=SesionUsuarios(self.ruta);admin.iniciar('Admin','Admin')
        inicializar_catalogo(admin,[dict(nombre='Café',precio=2.5,categoria='Bebidas',seccion='Bebidas'),dict(nombre='Hamburguesa',precio=9,categoria='Cocina',seccion='Cocina')])
        GestionTurnos(admin)
        from clientes import GestionClientes
        GestionClientes(admin)
        admin.crear('Alberto','alberto','prueba123','venta_libre')
        self.caja=SesionUsuarios(self.ruta);self.caja.iniciar('alberto','prueba123');self.caja.inventario_libre_verificado=True
        self.original=self.caja.usuario.copy()
        self.servicio=SolicitudesTable(self.ruta)
        self.servidor=ServidorTable(self.servicio,self.caja.identificar)
        self.url=f"http://127.0.0.1:{self.servidor.iniciar(host='127.0.0.1',puerto=0)}"
        self.addCleanup(self.servidor.detener)
        self.clave=self.servicio.vincular('PC del administrador','admin')
        self.headers={'Authorization':'Bearer '+self.clave,'Content-Type':'application/json'}
        self.login()

    def api(self,path,body=None,headers=None):
        req=Request(self.url+'/api/admin/'+path,headers=headers or self.headers,data=None if body is None else json.dumps(body).encode())
        try:
            with urlopen(req,timeout=15) as r:return json.load(r)
        except HTTPError as error:
            error.read();error.close();raise

    def login(self):
        self.headers['X-Sesion']=self.api('login',dict(usuario='Admin',password='Admin'))['token']

    def test_admin_and_cashier_keep_independent_sessions(self):
        with urlopen(self.url+'/admin') as r:self.assertIn('Administración'.encode(),r.read())
        registrar_venta(self.caja,'Venta rápida','',[dict(nombre='Hamburguesa',categoria='Cocina',seccion='Cocina',precio=9)],metodo_pago='Visa')
        panel=self.api('panel')
        self.assertEqual(panel['usuario'],'Admin')
        self.assertEqual(panel['caja_usuario']['nombre'],'Alberto')
        self.assertEqual(panel['total_centimos'],900)
        self.api('logout',{})
        self.assertEqual(self.caja.usuario,self.original)
        self.assertTrue(self.caja.inventario_libre_verificado)
        with self.assertRaises(HTTPError):self.api('panel')

    def test_cashier_and_order_links_cannot_access_admin(self):
        with self.assertRaises(HTTPError) as e:self.api('login',dict(usuario='alberto',password='prueba123'))
        self.assertEqual(e.exception.code,403)
        clave=self.servicio.vincular('Solo pedidos')
        with self.assertRaises(HTTPError) as e:self.api('login',dict(usuario='Admin',password='Admin'),dict(self.headers,Authorization='Bearer '+clave))
        self.assertEqual(e.exception.code,401)
        self.assertEqual(self.caja.usuario,self.original)

    def test_price_changes_are_central_and_detect_stale_edits(self):
        cafe=next(p for p in self.api('panel')['productos'] if p['nombre']=='Café')
        self.api('precio',dict(producto_id=cafe['id'],precio_anterior=250,precio='3.00'))
        self.assertEqual(self.servidor.leer_cambios_admin(),['precio'])
        with self.assertRaises(HTTPError):self.api('precio',dict(producto_id=cafe['id'],precio_anterior=250,precio='4.00'))
        actualizado=next(p for p in self.api('panel')['productos'] if p['id']==cafe['id'])
        self.assertEqual(actualizado['precio_centimos'],300)
        self.assertEqual(self.caja.usuario,self.original)

    def test_inventory_entries_and_new_users_do_not_switch_cashier(self):
        cafe=next(p for p in self.api('panel')['inventario'] if p['nombre']=='Café')
        self.api('entrada',dict(producto_id=cafe['id'],cantidad=5))
        self.api('usuario',dict(nombre='Mesero nuevo',usuario='mesero2',password='prueba123',rol='mesero'))
        panel=self.api('panel')
        self.assertEqual(next(p for p in panel['inventario'] if p['id']==cafe['id'])['cantidad'],5)
        self.assertTrue(any(u['usuario']=='mesero2' for u in panel['usuarios']))
        self.assertEqual(self.caja.usuario,self.original)

    def test_revoking_terminal_immediately_blocks_existing_admin_session(self):
        self.servicio.revocar(self.servicio.terminal(self.clave)[0])
        with self.assertRaises(HTTPError) as e:self.api('panel')
        self.assertEqual(e.exception.code,401)
        self.assertEqual(self.caja.usuario,self.original)

    def test_admin_reads_can_run_while_cashier_sells(self):
        def venta():registrar_venta(self.caja,'Venta rápida','',[dict(nombre='Hamburguesa',categoria='Cocina',seccion='Cocina',precio=9)],metodo_pago='Yappy')
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(self.api,'panel') for _ in range(3)]+[pool.submit(venta)]
            for future in futures:future.result()
        self.assertEqual(self.api('panel')['total_centimos'],900)
        self.assertEqual(self.caja.usuario,self.original)

    def test_admin_link_can_be_created_without_logging_out_cashier(self):
        with self.assertRaises(PermissionError):self.servidor.vincular_admin('alberto','prueba123')
        clave=self.servidor.vincular_admin('Admin','Admin')
        self.assertEqual(self.servicio.terminal(clave)[2],'admin')
        self.assertEqual(self.caja.usuario,self.original)
        self.assertTrue(self.caja.inventario_libre_verificado)

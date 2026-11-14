"""Roles, migración y retirada de acceso, siempre con datos temporales."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sqlite3
import tempfile
import unittest
from pathlib import Path
from usuarios import SesionUsuarios, PaginaUsuarios, ROLES
from PySide6.QtWidgets import QApplication,QPushButton

class RolesUsuariosTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.ruta=Path(self.temp.name)/'ventas.db'
        self.anterior=SesionUsuarios.ITERACIONES; SesionUsuarios.ITERACIONES=1000
        self.addCleanup(setattr,SesionUsuarios,'ITERACIONES',self.anterior)
        self.sesion=SesionUsuarios(self.ruta); self.assertTrue(self.sesion.iniciar('Admin','Admin'))

    def test_crear_roles_y_retirar_acceso_conserva_historial(self):
        for rol in ROLES:
            self.sesion.crear('Persona '+rol,'prueba-'+rol,'clave',rol)
            p=self.sesion.identificar('prueba-'+rol,'clave')
            self.assertEqual(p['rol'],'mesas' if rol=='venta_libre' else rol)
        mesero=self.sesion.identificar('prueba-mesero','clave')
        with self.sesion.conexion() as db:
            db.execute('CREATE TABLE referencia(usuario_id INTEGER REFERENCES usuarios(id))')
            db.execute('INSERT INTO referencia VALUES(?)',(mesero['id'],))
        self.sesion.eliminar(mesero['id'])
        self.assertIsNone(self.sesion.identificar('prueba-mesero','clave'))
        self.assertIsNone(self.sesion.perfil(mesero['id']))
        self.assertFalse(self.sesion.restaurar(mesero['id']))
        with self.sesion.conexion() as db:
            self.assertEqual(db.execute('SELECT usuario_id FROM referencia').fetchone()[0],mesero['id'])
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_limites_admin_y_propia_cuenta(self):
        with self.assertRaises(ValueError): self.sesion.eliminar(self.sesion.usuario['id'])
        self.sesion.crear('Mesero','mesero','clave','mesero')
        self.sesion.iniciar('mesero','clave')
        with self.assertRaises(PermissionError): self.sesion.crear('Otro','otro','clave','admin')
        with self.assertRaises(PermissionError): self.sesion.eliminar(1)

    def test_migracion_legacy_conserva_id_credenciales_y_referencias(self):
        with self.sesion.conexion() as db:
            db.execute("CREATE TABLE legado AS SELECT * FROM usuarios")
            db.execute('DROP TABLE usuarios')
            db.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY,nombre TEXT NOT NULL,usuario TEXT,clave_nombre TEXT UNIQUE NOT NULL,sal BLOB NOT NULL,resumen BLOB NOT NULL,iteraciones INTEGER NOT NULL,rol TEXT CHECK(rol IN ('admin','mesas')),tipo TEXT DEFAULT 'normal')")
            db.execute('INSERT INTO usuarios SELECT id,nombre,usuario,clave_nombre,sal,resumen,iteraciones,rol,tipo FROM legado')
            db.execute('DROP TABLE legado')
            db.execute('CREATE TABLE referencia(usuario_id INTEGER REFERENCES usuarios(id))')
            db.execute('INSERT INTO referencia VALUES(1)')
        nueva=SesionUsuarios(self.ruta)
        self.assertTrue(nueva.iniciar('Admin','Admin'))
        self.assertEqual(nueva.usuario['id'],1)
        nueva.crear('Cocinero','cocinero','clave','cocinero')
        with nueva.conexion() as db:self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_formulario_roles_sin_boton_volver_duplicado(self):
        type(self).app=QApplication.instance() or QApplication([])
        pagina=PaginaUsuarios(self.sesion,lambda:None); pagina.actualizar()
        self.assertEqual({pagina.rol.itemData(i) for i in range(pagina.rol.count())},set(ROLES))
        self.assertFalse(any('Volver' in b.text() for b in pagina.findChildren(QPushButton)))
        pagina.close()
        from PySide6.QtCore import QCoreApplication,QEvent
        pagina.deleteLater()
        QCoreApplication.sendPostedEvents(pagina,QEvent.Type.DeferredDelete)

    def test_permisos_http_y_revocacion_de_sesion(self):
        from test_pedidos_table import TestPedidosTable
        from pedidos_table import ServidorTable
        from urllib.request import Request,urlopen
        from urllib.error import HTTPError
        import json
        f=TestPedidosTable();f.setUp();self.addCleanup(f.doCleanups)
        s=SesionUsuarios(f.ruta);s.iniciar('Admin','Admin')
        s.crear('Mesero','m','clave','mesero');s.crear('Cocinero','c','clave','cocinero')
        server=ServidorTable(f.servicio,s.identificar);puerto=server.iniciar(host='127.0.0.1',puerto=0);self.addCleanup(server.detener)
        mesa=f.servicio.vincular('Mesa');cocina=f.servicio.vincular('Cocina','cocina')
        def login(usuario,tipo,clave):
            ruta='/api/cocina/login' if tipo=='cocina' else '/api/login'
            req=Request(f'http://127.0.0.1:{puerto}'+ruta,headers={'Authorization':'Bearer '+clave,'Content-Type':'application/json'},data=json.dumps(dict(usuario=usuario,password='clave')).encode())
            with urlopen(req) as r:return json.load(r)
        token=login('m','mesas',mesa)['token'];login('c','cocina',cocina)
        for usuario,tipo,clave in [('m','cocina',cocina),('c','mesas',mesa)]:
            with self.assertRaises(HTTPError) as e:login(usuario,tipo,clave)
            self.assertEqual(e.exception.code,403)
        s.eliminar(s.identificar('m','clave')['id'])
        with self.assertRaises(HTTPError) as e:
            urlopen(Request(f'http://127.0.0.1:{puerto}/api/resumen',headers={'Authorization':'Bearer '+mesa,'X-Sesion':token}))
        self.assertEqual(e.exception.code,401)

if __name__=='__main__':unittest.main()

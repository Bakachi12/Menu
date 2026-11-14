"""Payment summaries isolate turns/sheets and retain cent precision."""
import sqlite3,tempfile,unittest
from pathlib import Path
from contextlib import contextmanager
from resumen_pagos import resumen_pagos_hoja

class ResumenPagosTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.ruta=Path(self.tmp.name)/'ventas.db'
        self.usuario=dict(id=7,rol='admin')
        with self.conexion() as db:
            db.executescript('''CREATE TABLE ventas(metodo_pago TEXT,total REAL,turno_id INTEGER,cajero_id INTEGER,hoja_libre_id INTEGER,fecha TEXT);
                CREATE TABLE hojas_venta_libre(id INTEGER PRIMARY KEY,usuario_id INTEGER,apertura TEXT,cierre TEXT);''')

    @contextmanager
    def conexion(self):
        db=sqlite3.connect(self.ruta)
        try:
            with db:yield db
        finally:db.close()

    def es_admin(self):return self.usuario['rol']=='admin'
    def exigir_admin(self):
        if not self.es_admin():raise PermissionError('Solo Admin')

    def test_turno_totals_do_not_mix_other_turns_or_free_sales(self):
        with self.conexion() as db:
            for metodo,total in [('Efectivo',0.1),('Efectivo',0.2),('Yappy',19),('Clave',7.55),('Visa',2.5)]:
                db.execute('INSERT INTO ventas VALUES(?,?,1,7,NULL,?)',(metodo,total,'2026-11-14'))
            db.execute("INSERT INTO ventas VALUES('Efectivo',999,2,8,NULL,'2026-11-14')")
            db.execute("INSERT INTO ventas VALUES('Visa',88,NULL,7,1,'2026-11-14')")
        resumen=resumen_pagos_hoja(self,1)
        self.assertEqual(resumen['importes'],dict(Efectivo=30,Yappy=1900,Clave=755,Visa=250))
        self.assertEqual(resumen['total_centimos'],2935)

    def test_old_receipts_without_payment_method_remain_in_total(self):
        with self.conexion() as db:db.execute("INSERT INTO ventas VALUES(NULL,3,1,7,NULL,'2026-11-14')")
        resumen=resumen_pagos_hoja(self,1)
        self.assertEqual(resumen['importes']['Sin registrar'],300)
        self.assertEqual(resumen['importes']['Yappy'],0)
        self.assertEqual(resumen['total_centimos'],300)

    def test_free_sheets_are_exact_even_when_opened_in_the_same_second(self):
        with self.conexion() as db:
            db.executemany('INSERT INTO hojas_venta_libre VALUES(?,7,?,?)',[(1,'2026-11-14 10:00:00','2026-11-14 10:00:00'),(2,'2026-11-14 10:00:00',None)])
            db.execute("INSERT INTO ventas VALUES('Yappy',19,NULL,7,1,'2026-11-14 10:00:00')")
            db.execute("INSERT INTO ventas VALUES('Visa',5,NULL,7,2,'2026-11-14 10:00:00')")
            db.execute("INSERT INTO ventas VALUES('Efectivo',2,NULL,7,NULL,'2026-11-14 10:00:00')")
        self.assertEqual(resumen_pagos_hoja(self,-1)['total_centimos'],1900)
        resumen=resumen_pagos_hoja(self,-2)
        self.assertEqual(resumen['total_centimos'],500)
        self.assertEqual(resumen['ambiguas'],1)
        self.usuario=dict(id=8,rol='venta_libre')
        with self.assertRaises(PermissionError):resumen_pagos_hoja(self,-1)

    def test_unambiguous_legacy_free_receipts_match_owner_and_dates(self):
        with self.conexion() as db:
            db.execute("INSERT INTO hojas_venta_libre VALUES(1,7,'2026-11-14 10:00:00','2026-11-14 11:00:00')")
            db.execute("INSERT INTO ventas VALUES('Clave',4.25,NULL,7,NULL,'2026-11-14 10:30:00')")
            db.execute("INSERT INTO ventas VALUES('Clave',50,NULL,8,NULL,'2026-11-14 10:30:00')")
            db.execute("INSERT INTO ventas VALUES('Clave',50,NULL,7,NULL,'2026-11-14 12:00:00')")
        self.assertEqual(resumen_pagos_hoja(self,-1)['total_centimos'],425)

    def test_inventory_payments_match_products_not_the_full_receipt_total(self):
        import json
        cristal=dict(nombre='Cristal',categoria='Bebidas',seccion='Bebidas',precio=1)
        plato=dict(nombre='Hamburguesa',categoria='General',seccion='Cocina',precio=13)
        with self.conexion() as db:
            db.execute('ALTER TABLE ventas ADD COLUMN productos TEXT')
            for metodo,total,productos in [('Efectivo',15,[cristal,cristal,plato]),('Yappy',17,[cristal]*17),('Visa',8,[dict(plato,precio=8)])]:
                db.execute('INSERT INTO ventas VALUES(?,?,1,7,NULL,?,?)',(metodo,total,'2026-11-14',json.dumps(productos)))
        filas=[dict(nombre='Cristal',categoria='Bebidas',producto='Cristal · Bebidas')]
        resumen=resumen_pagos_hoja(self,1,filas)
        self.assertEqual(resumen['total_centimos'],1900)
        self.assertEqual(resumen['importes'],dict(Efectivo=200,Yappy=1700,Clave=0,Visa=0))
        con_cocina=resumen_pagos_hoja(self,1,filas,incluir_cocina=True)
        self.assertEqual(con_cocina['total_centimos'],4000)
        self.assertEqual(con_cocina['cocina_centimos'],2100)
        self.assertEqual(con_cocina['cocina_unidades'],2)
        self.assertEqual(con_cocina['importes'],dict(Efectivo=1500,Yappy=1700,Clave=0,Visa=800))

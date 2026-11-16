"""Recibos comerciales POS. No constituye facturación fiscal autorizada."""
import json
from collections import Counter
from html import escape
from decimal import Decimal, ROUND_HALF_UP
from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QTextDocument, QPageSize
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

CLAVE = "impresion_recibos_habilitada"

def _tabla(db):
    db.execute("CREATE TABLE IF NOT EXISTS configuracion_impresion (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)")

def habilitada(sesion):
    with sesion.conexion() as db:
        _tabla(db)
        fila = db.execute("SELECT valor FROM configuracion_impresion WHERE clave=?", (CLAVE,)).fetchone()
        return bool(fila and fila[0] == "1")

def configurar(sesion, activa):
    sesion.exigir_admin()
    with sesion.conexion() as db:
        _tabla(db)
        db.execute("INSERT OR REPLACE INTO configuracion_impresion (clave,valor) VALUES (?,?)",
                   (CLAVE, "1" if activa else "0"))

def obtener_venta(sesion, venta_id):
    if not sesion.usuario:
        raise PermissionError("Inicia sesión.")
    with sesion.conexion() as db:
        fila = db.execute("""SELECT v.id,v.fecha,v.mesa,v.cliente,v.productos,v.total,
            v.metodo_pago,u.nombre,v.cajero_id
            FROM ventas v LEFT JOIN usuarios u ON u.id=v.cajero_id WHERE v.id=?""", (venta_id,)).fetchone()
    if not fila:
        raise ValueError("No existe ese cobro.")
    if not sesion.es_admin() and fila[8] != sesion.usuario["id"]:
        raise PermissionError("Solo puedes imprimir tus propios cobros.")
    return dict(zip(("id","fecha","mesa","cliente","productos","total","metodo","cajero","cajero_id"),fila))

def recibo_html(venta):
    productos=json.loads(venta["productos"])
    if not isinstance(productos,list):
        raise ValueError("Productos del cobro inválidos.")
    grupos={}
    for p in productos:
        nombre=str(p.get("nombre") or "Producto")
        precio=int((Decimal(str(p["precio"]))*100).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
        clave=(nombre,precio)
        grupos[clave]=grupos.get(clave,0)+1
    filas="".join("<tr><td>{} × {}</td><td style='text-align:right'>B/. {:.2f}</td></tr>".format(
        cantidad,escape(nombre),cantidad*precio/100) for (nombre,precio),cantidad in grupos.items())
    total=Decimal(str(venta["total"]))
    return """<!doctype html><html><head><meta charset="utf-8"><style>
    body{font-family:Arial,sans-serif;font-size:9pt;color:black}
    h2{text-align:center;margin:0 0 5px}p{text-align:center;margin:3px}
    table{width:100%;border-collapse:collapse}td{padding:4px 0;border-bottom:1px dashed #999}
    .total{font-size:13pt;font-weight:bold;text-align:right}
    </style></head><body><h2>TISAMAR EVOLUTION</h2>
    <p>RECIBO COMERCIAL · NO FISCAL</p>
    <p>N.º {id} · {fecha}</p><p>{mesa} · {cliente}</p>
    <p>Cajero: {cajero}</p><hr><table>{filas}</table><hr>
    <p class="total">TOTAL B/. {total:.2f}</p>
    <p>Pago: {metodo}</p><p>Gracias por su compra</p>
    </body></html>""".format(id=venta["id"],fecha=escape(str(venta["fecha"])),
      mesa=escape(str(venta["mesa"])),cliente=escape(str(venta["cliente"] or "")),
      cajero=escape(str(venta["cajero"] or "")),filas=filas,total=total,
      metodo=escape(str(venta["metodo"] or "Sin registrar")))

def _documento(venta):
    documento=QTextDocument()
    documento.setHtml(recibo_html(venta))
    return documento

def imprimir(sesion,venta_id):
    if not habilitada(sesion):
        raise PermissionError("La impresión está desactivada en Administración.")
    venta=obtener_venta(sesion,venta_id)
    impresora=QPrinter(QPrinter.PrinterMode.HighResolution)
    impresora.setPrinterName(QPrinterInfo.defaultPrinterName())
    if not impresora.printerName() or not impresora.isValid():
        raise RuntimeError("No hay impresora configurada en Windows.")
    # Formato de rollo de 80 mm; la altura se amplía para cuentas largas.
    impresora.setPageSize(QPageSize(QPageSize.PageSizeId.Custom,
                                   __import__("PySide6.QtCore",fromlist=["QSizeF"]).QSizeF(80, 280),
                                   QPageSize.Unit.Millimeter))
    impresora.setPageMargins(QMarginsF(4,4,4,4))
    _documento(venta).print_(impresora)

def guardar_pdf(sesion,venta_id,ruta):
    venta=obtener_venta(sesion,venta_id)
    impresora=QPrinter(QPrinter.PrinterMode.HighResolution)
    impresora.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    impresora.setOutputFileName(str(ruta))
    impresora.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    _documento(venta).print_(impresora)

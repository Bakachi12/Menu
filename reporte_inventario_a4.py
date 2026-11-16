"""Exportación A4 de hojas de inventario; no modifica los cierres ni la base de datos."""
from html import escape
from pathlib import Path
from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument

CATEGORIAS = (
    ("Cervezas de Botellas", ("cerveza",)),
    ("Refrescos, Energéticos, Agua, Otros", ("refresco", "energ", "agua", "soda", "jugo")),
    ("Licores Botellas y Tragos", ("licor", "trago", "ron", "vodka", "whisky")),
    ("Ceviches", ("ceviche",)),
    ("Cigarrillos y Encendedores", ("cigarr", "encendedor")),
    ("Otros", ()),
)

def _categoria(fila):
    valor = (str(fila.get("categoria") or "") + " " + str(fila.get("nombre") or "")).lower()
    for titulo, palabras in CATEGORIAS[:-1]:
        if any(p in valor for p in palabras):
            return titulo
    return "Otros"

def _importe(centimos):
    return f"{int(centimos or 0) / 100:.2f}"

def _celda(valor):
    return escape(str(valor if valor is not None else ""))

def construir_html(turno, filas, resumen=None):
    """Usa los datos calculados por GestionTurnos.hoja_inventarios(), sin recalcular el cierre."""
    resumen = resumen or {}
    agrupadas = {titulo: [] for titulo, _ in CATEGORIAS}
    for fila in filas:
        agrupadas[_categoria(fila)].append(fila)
    filas_html = []
    for titulo, _ in CATEGORIAS:
        filas_html.append(f'<tr class="grupo"><td colspan="8">{escape(titulo)}</td></tr>')
        for f in agrupadas[titulo]:
            recibido = int(f.get("recibida") or 0)
            agregado = int(f.get("agregada") or 0)
            vendido = int(f.get("vendida") or 0)
            entregado = f.get("entregada") if f.get("cierre_fecha") else None
            filas_html.append("<tr>" + "".join(f"<td>{_celda(x)}</td>" for x in (
                f.get("nombre") or f.get("producto") or "",
                recibido, agregado, "", "", vendido,
                _importe(f.get("dinero_centimos")),
                entregado if entregado is not None else "Pendiente",
            )) + "</tr>")
    pagos = resumen.get("importes") or {}
    total = sum(int(f.get("dinero_centimos") or 0) for f in filas)
    total += int(resumen.get("cocina_centimos") or 0)
    pagos_html = "".join(f"<tr><td>{escape(str(k))}</td><td>B/. {_importe(v)}</td></tr>" for k, v in pagos.items())
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    body {{font-family:Arial,sans-serif;font-size:9pt;color:#111}}
    h1 {{font-size:20pt;text-align:center;margin:0 0 8px}}
    .datos {{margin:8px 0 12px}}
    table {{border-collapse:collapse;width:100%;table-layout:fixed}}
    th,td {{border:1px solid #222;padding:5px 3px;overflow-wrap:break-word}}
    th {{background:#ddd;font-size:8pt}}
    .grupo td {{background:#222;color:white;text-align:center;font-weight:bold}}
    .resumen {{width:46%;margin-left:auto;margin-top:15px}}
    .firma {{margin-top:28px}}
    </style></head><body>
    <h1>INVENTARIO TISAMAR EVOLUTION</h1>
    <div class="datos"><b>Encargado de Bar:</b> {_celda(turno.get("cajero"))}
    &nbsp;&nbsp; <b>Turno:</b> {_celda(turno.get("turno_id"))}<br>
    <b>Entrada:</b> {_celda(turno.get("asignacion_fecha"))}
    &nbsp;&nbsp; <b>Salida:</b> {_celda(turno.get("cierre_fecha") or "En curso")}</div>
    <table><thead><tr><th width="27%">Descripción</th><th>Unidades recibidas</th>
    <th>Unidades agregadas</th><th>A crédito*</th><th>Mal estado*</th>
    <th>Unidades vendidas</th><th>Efectivo B/.</th><th>Unidades entregadas</th></tr></thead>
    <tbody>{''.join(filas_html)}</tbody></table>
    <table class="resumen"><tr><th>Concepto</th><th>Importe</th></tr>
    {pagos_html}<tr><th>TOTAL VENDIDO</th><th>B/. {_importe(total)}</th></tr></table>
    <p class="firma"><b>Referencia / observaciones:</b> _______________________________________</p>
    <p>Firma saliente: ____________________ &nbsp; Firma entrante: ____________________</p>
    <p style="font-size:7pt">* Los campos a crédito y mal estado quedan en blanco si el sistema no los registra por producto.
    Los importes de pago reflejan los métodos registrados, sin inventar gastos o créditos.</p>
    </body></html>"""

def exportar_pdf(ruta, turno, filas, resumen=None):
    """Genera PDF A4 multipágina. Solo exporta; no envía a una impresora."""
    ruta = Path(ruta)
    if ruta.suffix.lower() != ".pdf":
        raise ValueError("Selecciona un archivo PDF.")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(ruta))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(8, 10, 8, 10))
    writer.setResolution(150)
    documento = QTextDocument()
    documento.setHtml(construir_html(turno, filas, resumen))
    documento.print_(writer)
    return str(ruta)

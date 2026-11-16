"""Envío opcional de recibos comerciales por SMTP. Credenciales en almacén seguro del SO."""
import re
import smtplib
import ssl
from email.message import EmailMessage
from PySide6.QtCore import QSettings
from PySide6.QtGui import QTextDocument, QPageSize
from PySide6.QtPrintSupport import QPrinter
from impresion_recibos import obtener_venta, recibo_html

SERVICE="TisamarEvolutionSMTP"
def _ajustes():
    return QSettings("Bakachi12", "Menu")
def configuracion():
    a=_ajustes()
    return dict(nombre=a.value("correo/nombre","TISAMAR EVOLUTION"),
        remitente=a.value("correo/remitente",""),servidor=a.value("correo/servidor",""),
        puerto=int(a.value("correo/puerto",587)),usuario=a.value("correo/usuario",""),
        tls=a.value("correo/tls",True,type=bool),activo=a.value("correo/activo",False,type=bool))
def guardar(sesion, *, nombre,remitente,servidor,puerto,usuario,tls,activo,password=None):
    sesion.exigir_admin()
    if activo and (not remitente or not servidor or not usuario):
        raise ValueError("Completa correo, servidor y usuario antes de activar.")
    if not 1<=int(puerto)<=65535:raise ValueError("Puerto SMTP inválido.")
    if password:
        try:import keyring
        except ImportError as error:raise RuntimeError("Instala 'keyring' para guardar la clave en el almacén seguro.") from error
        keyring.set_password(SERVICE, usuario, password)
    a=_ajustes()
    for clave,valor in dict(nombre=nombre,remitente=remitente,servidor=servidor,
                             puerto=int(puerto),usuario=usuario,tls=bool(tls),activo=bool(activo)).items():
        a.setValue("correo/"+clave,valor)
    a.sync()
    if a.status()!=QSettings.Status.NoError:raise OSError("No se pudieron guardar los ajustes.")
def _clave(usuario):
    try:import keyring
    except ImportError as error:raise RuntimeError("Instala 'keyring' para acceder a las credenciales.") from error
    clave=keyring.get_password(SERVICE,usuario)
    if not clave:raise ValueError("Configura una contraseña de aplicación SMTP en Administración.")
    return clave
def _pdf(venta):
    # PDF temporal en memoria: nunca guardar credenciales ni datos del cliente en disco.
    from tempfile import TemporaryDirectory
    from pathlib import Path
    with TemporaryDirectory() as carpeta:
        ruta=Path(carpeta)/"recibo.pdf"
        impresora=QPrinter(QPrinter.PrinterMode.HighResolution)
        impresora.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        impresora.setOutputFileName(str(ruta))
        impresora.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        doc=QTextDocument();doc.setHtml(recibo_html(venta));doc.print_(impresora)
        return ruta.read_bytes()
def enviar(sesion, venta_id, destinatario):
    cfg=configuracion()
    if not cfg["activo"]:raise PermissionError("El envío por correo está desactivado.")
    destinatario=destinatario.strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",destinatario):
        raise ValueError("Correo del cliente inválido.")
    venta=obtener_venta(sesion,venta_id)
    mensaje=EmailMessage()
    mensaje["From"]=cfg["remitente"]
    mensaje["To"]=destinatario
    mensaje["Subject"]=f"Recibo comercial TISAMAR - Venta {venta_id}"
    mensaje.set_content("Adjuntamos el recibo comercial de tu compra. Este documento no es una factura fiscal.")
    mensaje.add_attachment(_pdf(venta),maintype="application",subtype="pdf",filename=f"recibo_{venta_id}.pdf")
    clave=_clave(cfg["usuario"])
    contexto=ssl.create_default_context()
    if cfg["tls"]:
        with smtplib.SMTP(cfg["servidor"],cfg["puerto"],timeout=15) as smtp:
            smtp.starttls(context=context)
            smtp.login(cfg["usuario"],clave)
            smtp.send_message(mensaje)
    else:
        with smtplib.SMTP_SSL(cfg["servidor"],cfg["puerto"],timeout=15,context=context) as smtp:
            smtp.login(cfg["usuario"],clave)
            smtp.send_message(mensaje)
    return True

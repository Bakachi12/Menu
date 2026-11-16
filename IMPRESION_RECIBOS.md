# Impresión de recibos comerciales (rama de desarrollo)

- Administrador: Configuración > «Imprimir recibo comercial al cobrar».
- Caja: al confirmar un cobro, la casilla «Imprimir recibo al cerrar esta cuenta» permite omitir la impresión sin omitir la venta.
- Historial: seleccionar una venta y usar «Guardar recibo PDF» o «Reimprimir recibo».
- La impresión usa la impresora predeterminada de Windows y un papel personalizado de 80 mm; hay que probar el controlador de la impresora real.
- La configuración se guarda en SQLite (tabla configuracion_impresion).
- Sin impresora, desactivar la opción. Si falla al imprimir, el cobro ya registrado no se revierte.
- Es un RECIBO COMERCIAL NO FISCAL: no reemplaza facturación autorizada por la DGI de Panamá.
- PENDIENTE DE QA: ejecución Windows, comprobación de diseño del diálogo Qt, pruebas con impresora térmica, cortes y tickets largos. No fusionar en main hasta completar QA.

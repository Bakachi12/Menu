# Caja web — primera fase

La caja de Windows sigue siendo la fuente de verdad. Se añade la ruta `http://IP-DE-LA-PC:8765/caja` al servidor de PedidosTable, que debe estar iniciado en la aplicación principal.

## Cómo probar

1. Ejecutar Menu en la PC y activar el servidor de PedidosTable.
2. Vincular la tablet con un enlace de **PedidosTable** emitido por la PC (la misma terminal debe estar autorizada).
3. Abrir `http://IP-DE-LA-PC:8765/caja` en el navegador de la tablet, en la misma red.
4. Introducir el enlace de vinculación y seleccionar la tarjeta del empleado. Los empleados con PIN configurado pueden iniciar automáticamente al completar 4–6 cifras. Los demás usan su contraseña.
5. Consultar mesas, productos y enviar pedidos a la PC para revisión.

## Alcance real y limitaciones

Esta primera fase **no es aún una caja web completa**: aprovecha el flujo de solicitudes de PedidosTable, por lo que las órdenes se envían para aceptación en la PC. **No se permite cobrar, cerrar turnos ni modificar inventario desde el navegador**. Se requiere diseñar y probar operaciones de caja remotas atómicas, bloqueo de cuentas, validación de turno y permisos antes de habilitar cobros.

El servidor está accesible en la red local: no publicar el puerto 8765 a Internet. La vinculación y la sesión son necesarias; la autenticación por PIN reutiliza el bloqueo de intentos persistente. El sistema no ha sido probado en tablets ni con el ejecutable.

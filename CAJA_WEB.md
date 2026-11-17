# Caja HTML — versión experimental

**No usar para ventas reales hasta validar los cobros con una base de datos de prueba y verificar los turnos, la impresión y los inventarios.** Cambios guardados en la rama `feature/impresion-recibos-inventario-a4`, sin publicar un EXE.

## Cómo vincular

1. Actualiza la rama de desarrollo en una PC de pruebas, realiza respaldo de `ventas.db` y ejecuta `Main.py` (o compila un EXE nuevo con `menu_windows.spec`).
2. En Windows abre **Configuración → Conectar dispositivos → Activar conexión móvil** y genera un enlace de **PedidosTable** para la tablet.
3. Conecta tablet y PC al mismo Wi-Fi y abre `http://IP-DE-LA-PC:8765/caja` en el navegador.
4. Pega el enlace completo de PedidosTable, selecciona el perfil e inicia con PIN (4–6 cifras) o contraseña.
5. Prueba abrir una mesa, añadir y retirar bebidas, cerrar con Efectivo/Yappy/Clave/Visa y consultar **Mis cobros**.
6. Confirma en la PC que cada venta aparece una sola vez, que se liberó la mesa, que el inventario del turno se descontó correctamente y que el historial pertenece al cajero autenticado.

## Qué está programado

- Reutilización del servidor PedidosTable, perfiles y PIN.
- Catálogo y cuentas consultados desde SQLite de la PC.
- Agregar y retirar productos de mesas con control de versión para detectar cambios simultáneos.
- Cobro de cuentas con verificación de estado dentro de la misma transacción SQLite; aplica controles de rol, turno e inventario del programa existente.
- Historial del empleado, actualización periódica en navegador y actualización de cuentas en Windows.
- Caja HTML incluida en la configuración de empaquetado del EXE.

## Pendiente / limitaciones

- **No se han ejecutado pruebas de integración ni pruebas reales con tablet, Windows o impresora.**
- La interfaz web todavía no permite seleccionar preparación y acompañamientos de cocina, asignar clientes, crear cuentas de barra, imprimir o enviar recibos, ni operar Venta libre.
- El inicio de sesión web y los cobros dependen de un servidor HTTP local: **no publicar el puerto 8765 en Internet ni usarlo en Wi-Fi público**.
- El historial de la caja web muestra los últimos 80 cobros del empleado, no herramientas administrativas.
- El ejecutable anterior **no contiene estos cambios**. Es necesario ejecutar el código actualizado o compilar uno nuevo.

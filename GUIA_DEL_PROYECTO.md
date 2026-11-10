# Guía del proyecto Menu

El programa arranca desde `Main.py`. Los comentarios que empiezan con `#` y los textos entre comillas triples explican el código: no aparecen como mensajes al usuario.

## Qué hace cada archivo

| Archivo | Para qué sirve |
| --- | --- |
| `Main.py` | Arranque, navegación, historial, configuración de productos y coordinación de pedidos y cobros. |
| `datos.py` | Prepara o migra la base local, carga productos y registra las ventas. |
| `vista_pedidos.py` | Dibuja los botones de productos, los consumos por cliente y sus subtotales. |
| `estilos.py` | Colores, bordes y tamaños compartidos de formularios, catálogo, historial y botones de productos. |
| `clientes.py` | Registra clientes, los asigna a mesas y conserva pedidos abiertos. También construye la lista de Clientes. |
| `configuracion.py` | Permite agregar mesas y cambiar el nombre o contraseña del administrador. |
| `usuarios.py` | Inicio de sesión, contraseñas y permisos de administrador y empleados. El nombre completo se muestra en turnos y el usuario separado se usa para iniciar sesión. |
| `inventario.py` | Persistencia y horarios semanales de turnos, asignación de productos, conteos de apertura/cierre, autorización y pantallas de Inventario, Horario y Hoja de inventarios. |
| `dialogos.py` | Cuadros integrados para escribir el nombre de una mesa o de un cliente. |
| `pantalla_espera.py` | Fondo de bloqueo, reloj y temporizador de inactividad. |
| `desplazamiento.py` | Arrastre táctil y con ratón; distingue deslizar de pulsar un botón. |
| `inicio.ui` | Diseño base de la ventana principal, mesas e historial. |
| `pedido.ui` | Diseño base del menú y la cuenta de una mesa. |
| `confirmar_cobro.ui` | Diseño de la confirmación de cobro. |

Los archivos `.ui` se pueden abrir con Qt Designer. Parte del diseño se construye en Python, por ejemplo las tarjetas de productos y los clientes. Los nombres internos (`objectName`) conectan el diseño con el código; cambiarlos requiere actualizar sus referencias.

## Cómo se conecta todo

1. `Main.py` prepara los datos, carga la ventana y pide iniciar sesión.
2. Al agregar un cliente, `dialogos.py` pide su nombre y `clientes.py` lo guarda.
3. `elegir_mesa_cliente()` muestra las mesas. `activar_mesa()` asigna la mesa elegida y abre su pedido.
4. `dibujar_productos()` crea los botones del menú. Al tocar uno, llama a `agregar_producto()` en `Main.py`.
5. `guardar_cuenta_abierta()` guarda el pedido antes de actualizar la pantalla. `dibujar_cuenta()` muestra el subtotal de cada cliente y el total de la mesa.
6. Al confirmar el cobro, `registrar_venta()` registra la venta, elimina el pedido pendiente y libera los clientes en una sola transacción. Si falla, se conserva la cuenta.
7. Admin registra las entradas recibidas en Inventario y asigna existencias disponibles a un usuario de caja. La asignación queda pendiente hasta que el cajero verifica físicamente cada producto; cualquier faltante o sobrante de apertura queda registrado.
8. El cajero no puede abrir pedidos ni cobrar antes de confirmar el inventario. Al cobrar, cada venta y sus unidades se asocian al turno activo. El cierre solicita la contraseña de Admin en la misma pantalla, sin cerrar ni cambiar la sesión del cajero; después registra el conteo final y muestra ventas, existencias finales, faltantes y sobrantes.
9. Asignación, apertura, autorización y cierre se realizan dentro de Inventario, sin ventanas emergentes. Las cantidades se escriben directamente en campos numéricos grandes, compatibles con teclado táctil, y la pantalla permite desplazamiento táctil. Solo puede haber un turno pendiente o activo a la vez; Admin puede cancelar una asignación que todavía no se ha iniciado.

Los parámetros `al_agregar` y `al_cambiar` son funciones que se ejecutan cuando se toca un botón. Permiten reutilizar la misma presentación sin repetir la lógica de guardar datos.

## Dónde buscar un cambio

- **Colores de los botones del menú:** `BOTON_PRODUCTO` en `estilos.py`.
- **Tamaño y columnas de productos:** `dibujar_productos()` en `vista_pedidos.py`.
- **Nombres, cantidades y subtotales de la cuenta:** `dibujar_cuenta()` en `vista_pedidos.py`.
- **Validación del precio:** `guardar_producto()` en `Main.py`.
- **Buscar ventas por texto o fecha:** `aplicar_filtros_historial()` en `Main.py`.
- **Acceso de los empleados:** `aplicar_permisos()` en `Main.py` y comprobaciones en `usuarios.py`.
- **Alta de usuarios:** `PaginaUsuarios` en `usuarios.py` guarda por separado nombre completo, usuario de acceso y contraseña; el inicio de sesión usa el usuario, y los turnos muestran el nombre completo. Las cuentas antiguas se migran conservando su nombre actual como usuario de acceso.
- **Navegación a Inventario y permisos para operar:** `abrir_inventario()` y `aplicar_permisos()` en `Main.py`.
- **Acceso a la hoja de turnos:** `abrir_hoja_inventarios()` en `Main.py`; la página y el reporte están en `PaginaHojaInventarios` y `GestionTurnos.hoja_inventarios()` en `inventario.py`.
- **Horario semanal y asignación del siguiente cajero al cerrar:** `PaginaHorarioTurnos`, `GestionTurnos.guardar_horario()` y `GestionTurnos._asignar_proximo_horario()` en `inventario.py`.
- **Asignación, conteos, autorización y resumen de turnos:** `GestionTurnos` y `PaginaInventario` en `inventario.py`.
- **Asociación de una venta al turno activo:** `registrar_venta()` en `datos.py`; el campo `ventas.turno_id` se agrega mediante migración.
- **Tiempo para bloquear la pantalla:** la creación de `ControlEspera` al final de `Main.py`.
- **Comportamiento al arrastrar:** `DesplazamientoGlobal` en `desplazamiento.py`.

## Datos y ejecución

Desde la carpeta del proyecto, ejecuta `python Main.py` con Python y PySide6 instalados.

Los datos se guardan en `TPVBar/ventas.db`, dentro de la ubicación de datos que proporciona Windows mediante Qt. La ruta exacta la decide `preparar_archivo_datos()` en `datos.py`. Una base antigua en la carpeta del proyecto se copia solo cuando aún no existe la base de destino; se conserva el original.

`__pycache__` y los archivos `.pyc` los genera Python automáticamente. No se editan ni se necesitan subir a GitHub. Las bases `.db` contienen los datos del negocio y están excluidas del repositorio.

Al modificar el programa, conserva las comprobaciones de permisos y las transacciones: ocultar un botón no sustituye validar quién ejecuta la acción. Trabaja con una base temporal para probar cobros o cambios de clientes.

Los turnos y sus conteos se conservan en `turnos` y `turno_inventario`, en esa misma base. La inicialización de `GestionTurnos` crea esas tablas y agrega `ventas.turno_id`, `turnos.asignacion_fecha` y `turnos.nombre_cajero` si faltan, sin reemplazar los datos existentes. En turnos anteriores a la captura de asignación, la fecha puede aparecer como no disponible; el nombre usa el usuario actual como respaldo. Las ventas anteriores a la asociación de turnos no tienen un turno asociado. Admin puede seguir operando sin turno; sus ventas no se atribuyen a la caja de un empleado.

`existencias_inventario` guarda las unidades disponibles en almacén. Al asignarlas al cajero se descuentan; al cierre, las unidades contadas se devuelven al almacén y quedan disponibles para el siguiente turno. `movimientos_inventario` conserva el detalle interno de entradas de Admin, entregas, ventas, cancelaciones, faltantes y sobrantes. La opción de la barra izquierda “Hoja de inventarios” agrupa el reporte por turno: el nombre del cajero y las fechas de asignación/cierre aparecen una sola vez en el encabezado; al pulsarlo se despliegan los productos con unidades recibidas/verificadas al abrir, inventario agregado durante el turno, unidades vendidas, importe vendido, unidades devueltas y faltantes/sobrantes al cierre. Los turnos pendientes y activos también aparecen, con devolución y diferencias marcadas como pendientes. El dinero vendido se calcula con el precio guardado en cada venta. Admin accede a las pantallas de asignación, entradas y existencias desde botones separados en Inicio; Inventario no aparece en su barra lateral y “Hoja de inventarios” permanece como acceso lateral al reporte.

La opción “Horario” permite a Admin asignar un cajero a un día y hora recurrente de la semana. El selector y la tabla muestran la hora en formato de 12 horas (por ejemplo, 1:00 PM); la fecha de la tabla indica la próxima ocurrencia de cada horario. Al cerrar el turno actual, el programa busca la próxima ocurrencia futura y, si hay inventario disponible, se lo reserva al cajero programado mediante una nueva asignación pendiente. El siguiente cajero debe iniciar sesión y confirmar físicamente la apertura antes de vender. Si no queda inventario disponible, se informa a Admin y no se crea una asignación vacía.

## Qué se simplificó

- Los botones de productos se construyen en un solo lugar, tanto al abrir una mesa como al actualizar el catálogo.
- La cuenta por cliente y la persistencia tienen módulos separados y comentarios de guía.
- Los estilos compartidos se definen una sola vez.
- El formulario de productos se monta directamente en sus tarjetas, sin crear y desmontar un diseño anterior.
- Se retiraron impresiones de depuración, imports sin uso y una consulta duplicada que estaba después de un `return`.
- Las consultas del catálogo e historial reutilizan la conexión que se cierra automáticamente.


## Venta rápida de barra

En Inicio, el botón Venta rápida abre el menú sin asignar mesa ni cliente para los empleados. Admin conserva Inicio como pantalla inicial, pero no ve Venta rápida ni las pestañas laterales Mesas y Clientes. Al confirmar el cobro, el historial muestra Venta rápida y la cuenta queda vacía para la siguiente venta. Cancelar la confirmación vuelve al pedido sin registrar una venta.

`abrir_venta_rapida()` en Main.py abre la cuenta. `VENTA_RAPIDA` en clientes.py es su identificador interno, separado de los nombres de mesa. Los productos pendientes se guardan en la misma base y se conservan al navegar o reiniciar. `nombre_operacion()` convierte ese identificador en el texto visible Venta rápida; datos.py usa ese texto al registrar la venta. La pantalla de Inicio se construye en Main.py.

## Inventario y turnos de caja

El botón Inventario de la barra lateral abre la pantalla definida por `PaginaInventario` en `inventario.py` para los cajeros, que verifican la apertura y realizan el cierre. En Inicio, Admin dispone de accesos separados para asignar un cajero, registrar entradas al almacén y consultar las existencias disponibles. Cada botón abre solo su sección; la pantalla completa de Inventario se oculta del menú lateral de Admin. La asignación pendiente se puede cancelar desde la sección de asignación si todavía no se ha confirmado la apertura.

Admin registra las unidades que llegan al almacén desde la sección de entradas y asigna existencias a un usuario de caja. La asignación reserva esas unidades y se puede cancelar antes de iniciar el turno. La opción “Hoja de inventarios” de la barra izquierda abre una tabla agrupada por turno. El cajero y las fechas se muestran una vez en el encabezado; al tocarlo se despliegan las filas de productos con recibido/asignado, vendido, importe vendido y unidades devueltas al cerrar.

En “Horario”, Admin configura los cajeros por día y hora semanal; las horas se presentan en formato AM/PM y cada fila muestra la próxima fecha programada. El horario no cierra un turno automáticamente: solo después de autorizar y completar el cierre con el conteo final, el sistema crea la asignación pendiente del siguiente cajero programado y reserva para él todo el stock disponible. El cajero deberá verificar la apertura para empezar a cobrar.

Al iniciar sesión, el cajero asignado entra a Inventario y verifica físicamente cada cantidad. Si hay faltantes o sobrantes, la pantalla muestra un aviso y pide confirmar otra vez; al iniciar, el registro queda guardado en el historial. Una vez iniciado el turno, el cajero puede trabajar en Inicio, Mesas y Clientes; el TPV guarda cada cobro y sus unidades en ese turno.

Para agregar existencias a un turno activo sin cambiar de sesión, el cajero pulsa “Agregar inventario a este turno” en Inicio. Admin autoriza cada entrega con su contraseña; se elige el producto y la cantidad en el formulario integrado. El programa registra la entrega vinculada al turno y la muestra en la columna “Inventario agregado” de la Hoja de inventarios. Al cierre, el conteo esperado es el inventario verificado al abrir más lo agregado durante el turno, menos las unidades vendidas; el resumen y la hoja registran las diferencias reales de faltantes/sobrantes.

Para cerrar, se escribe la contraseña de Admin en la sección Cierre de turno, sin salir de la sesión del cajero. Tras autorizarla, se muestra el total de unidades vendidas; el usuario escribe el inventario final y confirma el cierre. Si no había un cajero asignado por horario, Admin puede elegir al siguiente cajero desde la misma pantalla de cierre, con las existencias disponibles preparadas para una asignación rápida; no necesita cerrar la sesión actual. Cuando la autorización se hace desde una sesión de cajero, el permiso para asignar se limita a ese cierre y expira a los 30 minutos. El resumen presenta los agregados, las ventas, el conteo final y los faltantes o sobrantes, sin mostrar los cálculos internos de esperado/diferencia. Las unidades finales regresan al inventario disponible para el siguiente cajero. Los campos numéricos grandes y el desplazamiento táctil están implementados en `PaginaInventario`; los datos de turnos y movimientos se gestionan en `GestionTurnos`.



## Terminal móvil PedidosTable

La opción PedidosTable conecta celulares y tablets del personal a la PC por la
red local. `pedidos_table.py` implementa el servicio y las solicitudes persistentes;
`pedidos_table_ui.py` integra activación y aprobación en el TPV;
`pedidos_table.html` contiene la interfaz móvil. Consulta [PEDIDOS_TABLE.md](PEDIDOS_TABLE.md)
para iniciar la conexión, comprobar el firewall y recompilar el ejecutable.

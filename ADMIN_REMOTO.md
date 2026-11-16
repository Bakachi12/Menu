# Admin en otra PC mientras caja sigue activa

La PC de caja mantiene la base de datos y el servidor. El administrador entra desde el navegador de otra PC de la misma red, con su propio usuario Admin. Iniciar o cerrar la sesión remota no cambia la sesión del cajero.

## Preparación inicial

1. Reinicia el programa Menu de la PC central después de actualizar el código.
2. En Inicio pulsa **Conectar PC de Admin**, sin salir del usuario de caja.
3. Introduce las credenciales de una cuenta Admin y pulsa **Crear enlace de administración**. La cuenta del cajero no cambia.
4. Copia el enlace completo y ábrelo en el navegador de la otra PC. Inicia sesión con una cuenta de administrador.
5. Cierra el cuadro del enlace en la PC central y continúa usando caja. El administrador permanece conectado desde la segunda PC y ambos trabajan a la vez.

También se puede generar el enlace desde **Configuración → Dispositivos móviles → Crear enlace para otra PC · Administración** cuando la PC central tiene una sesión Admin.

La PC central debe permanecer encendida y Menu abierto. Ambas PC deben estar en la misma red. No hay que copiar ni compartir el archivo de base de datos: las operaciones se realizan en la PC central.

## Funciones del panel

- Resumen de ventas, formas de pago, cuentas abiertas y usuario conectado en caja.
- Ventas y cobros filtrados por fechas.
- Existencias y registro de entradas de inventario al almacén.
- Hojas de inventario, incluyendo resumen y detalle de cocina.
- Consulta de productos y edición de precios.
- Consulta del personal y creación de usuarios.

Los cambios de precio se reciben en caja; los productos ya añadidos a una cuenta conservan el precio con el que se añadieron. Si el precio cambió en otra terminal mientras se editaba, se pide actualizar antes de guardarlo.

El resumen, los cobros y las hojas se actualizan automáticamente cada diez segundos. Productos, inventario y usuarios tienen **Actualizar**, para no reemplazar formularios mientras el administrador escribe.

## Accesos independientes

El enlace de administración es distinto de los de PedidosTable y Cocina. Requiere una cuenta con rol Admin; un cajero o un enlace de pedidos no pueden entrar. El enlace se puede retirar desde la lista de dispositivos de Configuración, invalidando inmediatamente esa terminal.

**Cerrar esta sesión** dentro del navegador solo cierra el acceso remoto. No cierra el turno ni la sesión del cajero.

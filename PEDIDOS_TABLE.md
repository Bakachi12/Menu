# PedidosTable · primera versión móvil

Terminal web para el **personal** en celulares y tablets. Funciona en la red
local del negocio, con la PC encendida y el TPV abierto. No necesita instalar
una APK ni contratar alojamiento. GitHub guarda el código; la PC atiende los
pedidos. Esta versión no es un kiosco público para clientes.

## Iniciar

1. Descarga esta rama completa, conservando los archivos `.ui`. Con Python y
   PySide6 instalados, ejecuta `python Main.py` desde la carpeta del proyecto.
2. Inicia sesión como Admin y abre **PedidosTable** en la barra lateral.
3. Comprueba la IP local de la PC con `ipconfig` en Windows (dirección IPv4
   del adaptador Wi-Fi o Ethernet conectado al restaurante). Corrige la IP
   mostrada si la PC tiene varios adaptadores o una VPN.
4. Pulsa **Activar conexión móvil** y copia el enlace completo al celular.
   El enlace incluye una clave de acceso. Compártelo solo con el personal.
5. Conecta el celular al mismo Wi-Fi y abre el enlace en su navegador.
   Si Windows pregunta por Python, permite el acceso únicamente en redes
   privadas. Se utiliza el puerto TCP 8765. Una red de invitados con aislamiento
   entre dispositivos puede impedir la conexión.
6. Inicia sesión con tu propio usuario y contraseña del TPV. La caja muestra el usuario que envió cada solicitud. Usa **Cerrar sesión** para cambiar de empleado. La sesión móvil vence a las ocho horas.
7. Elige mesa, cuenta general o cliente ya asignado, productos y cantidades.
   Escribe un nombre para el dispositivo y pulsa **Enviar a caja**.
8. En la PC, Admin o un cajero con turno activo abre **PedidosTable**, selecciona
   la solicitud y la acepta o rechaza. La cuenta del celular se actualiza cada
   ocho segundos. Las solicitudes nuevas aparecen en la PC aproximadamente
   cada 2,5 segundos.

El TPV guarda las solicitudes en `solicitudes_table` dentro de la base existente.
Una solicitud pendiente no modifica cuentas, ventas ni inventario. Aceptarla
añade unidades a la cuenta existente y registra quién la revisó; cobrar sigue
usando las validaciones de inventario del TPV. Las notas son instrucciones que
se muestran al cajero y permanecen en la solicitud, no en los renglones de venta.

Las mesas, clientes, precios, categorías y fotos vienen del TPV. Si no hay foto
se muestra la inicial del producto. Los precios se calculan en la PC, y se vuelve
a validar mesa, cliente y catálogo al aceptar. Si cambió un producto o precio,
rechaza la solicitud y envíala de nuevo. Cobrar una mesa rechaza automáticamente
sus solicitudes pendientes para que no pasen a una cuenta posterior.

## Conexión y límites

- Usa una red privada de confianza: esta primera versión usa HTTP local y las credenciales viajan sin cifrado de transporte.
  No abras este puerto al Internet. El enlace y una cuenta del personal permiten consultar menú, mesas y
  cuentas; no concede permiso para aceptar, cobrar o administrar.
- Solo Admin activa o desactiva el servidor. Desactivarlo corta la conexión;
  reactivarlo genera una clave nueva. Al cerrar el programa se detiene.
- Un envío sin respuesta conserva su identificador y se puede reintentar sin
  añadir una segunda solicitud. No se envía sin conexión. El borrador y el
  historial del navegador son de la sesión; la PC conserva los registros.
- Si la mesa o el cliente cambian, revisa el destino antes de aceptar. No se
  crean clientes, se cobran cuentas ni se administran productos desde el móvil.
- Si empaquetas con PyInstaller, incluye `pedidos_table.html` como dato junto
  a `Main.py`, además de los `.ui`, e incorpora ambos módulos `pedidos_table.py`
  y `pedidos_table_ui.py`. El ejecutable anterior necesita recompilarse.

## Verificación

`python -m unittest discover -s tests -v` prueba el servicio con una base
temporal. La prueba real desde un Android y el firewall de Windows debe hacerse
en el restaurante; este entorno no tiene acceso a esa red ni a su base real.

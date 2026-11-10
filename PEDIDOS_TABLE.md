# Conectar la caja de Windows con PedidosTable en Android

La PC guarda las mesas y cuentas del restaurante. El celular envía solicitudes a esa PC por la red local. Para trabajar, deja el programa de caja abierto y conecta ambos equipos al mismo router. La PC puede estar conectada por cable y el celular por Wi-Fi.

## 1. Preparar Windows y Android

- **PC.** Usa la versión del proyecto que incluye **PedidosTable** en la barra lateral. Si tu ejecutable todavía no muestra esa opción, descarga la rama `codex/pedidos-table-movil`, extrae la carpeta completa y, con Python y PySide6 instalados, ejecuta `python Main.py` desde esa carpeta.
- **Android.** Instala el APK y abre **PedidosTable** desde su icono. Si lo descargas desde [la compilación de GitHub](https://github.com/Bakachi12/Menu/actions/runs/42914924254), inicia sesión en GitHub, abre **Artifacts → PedidosTable-Android**, extrae el ZIP e instala `app-debug.apk`. **Probar la demo** abre una caja simulada para practicar.

## 2. Obtener el enlace en la PC

1. Entra como **Admin** y abre **PedidosTable** en la barra lateral.
2. En Windows, abre el **Símbolo del sistema** y escribe `ipconfig`. Busca la **Dirección IPv4** del adaptador Ethernet o Wi-Fi conectado al router del negocio. Comprueba que coincide con la IP mostrada en PedidosTable y corrígela si hace falta.
3. Pulsa **Activar conexión móvil**. Si Windows solicita permiso de red, permite el acceso para la **red privada** del negocio.
4. Copia el enlace completo al celular. Tendrá una forma parecida a `http://192.168.1.20:8765/#CLAVE_DE_EJEMPLO`. Usa el que genera tu PC, incluida toda la parte que sigue a `#`. Compártelo solo con el personal.

## 3. Vincular el celular e iniciar sesión

1. Conecta Android al Wi-Fi del negocio y abre **PedidosTable**. En **Vincular con la caja**, pega el enlace y toca **Guardar y conectar**. Si estás en la demo, toca **Conexión con la caja → Volver** para llegar a esa pantalla.
2. Introduce el usuario y la contraseña que el empleado tiene en el sistema de caja. Si la conexión funciona, verás las mesas configuradas en la PC. Las credenciales de la demo solo sirven para practicar.
3. La app recuerda el enlace al volver a abrirla. Usa **Cerrar sesión** cuando cambie el empleado. Si utilizas el navegador del celular, puedes abrir el mismo enlace e iniciar sesión allí.

## 4. Comprobar que los pedidos llegan a la caja

1. **En Android**, selecciona una mesa de prueba y su cuenta general o un cliente asignado. Añade un producto, escribe el nombre del dispositivo y toca **Enviar a caja**.
2. **En Windows**, abre **PedidosTable** como Admin o como cajero con turno activo. En unos segundos debe aparecer la solicitud con la mesa, el producto y el usuario que la envió.
3. Para comprobar la conexión sin añadir consumo, selecciona la solicitud y pulsa **Rechazar**. En el celular, toca **Actualizar** y comprueba que aparece *rechazada* y que el total sigue igual. Para probar la aceptación, envía otra solicitud y pulsa **Aceptar y añadir a la cuenta** en la PC. El producto aparecerá en la cuenta elegida.

## Si no conecta

| Qué ves | Qué comprobar |
| --- | --- |
| Android pide un enlace válido | Copia de nuevo el enlace completo de la PC, con la IPv4 privada, el puerto `8765`, la barra y la clave. |
| El celular no llega a la pantalla de usuario | Comprueba que el TPV esté abierto y la conexión móvil activa. Verifica la IPv4, el permiso de Windows para el puerto TCP 8765 en la red privada y que el Wi-Fi permita comunicación entre dispositivos. Una red de invitados puede aislarlos. |
| Antes conectaba y ahora pide una clave | Si cerraste el TPV o desactivaste y reactivaste la conexión, copia el enlace nuevo. En la app, toca **Conexión con la caja → Volver**, pega el enlace y pulsa **Guardar y conectar**. Haz lo mismo si cambia la IP de la PC. |
| Aparece «Usuario o contraseña incorrectos» | Usa una cuenta registrada en esa caja. La clave del enlace vincula el dispositivo y la contraseña identifica al empleado. |
| La PC recibe el pedido pero el total no cambia | Revisa si la solicitud sigue pendiente. El total cambia cuando el cajero la acepta. |

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

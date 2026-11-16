# Configurar correo del local

En Administración → Configuración se encuentran los campos de remitente, servidor SMTP, puerto, usuario y contraseña de aplicación. El correo y servidor quedan en blanco inicialmente; el envío está desactivado.

1. Instalar dependencia: `pip install keyring`. En Windows se utiliza el almacén de credenciales del sistema. Añadir esta dependencia a la compilación del EXE.
2. Configurar el servidor SMTP del proveedor (STARTTLS/587 o SSL/465) y una contraseña de aplicación o credencial SMTP dedicada. No utilizar la contraseña personal habitual.
3. Guardar y activar el envío. Al cobrar aparece el campo opcional de correo del cliente.
4. Si no se proporciona correo, el cobro no intenta enviar nada. Un fallo de envío no revierte una venta ya guardada.

**Limitaciones:** pendiente de pruebas reales de Windows, proveedor SMTP, red y empaquetado del EXE. La función requiere acceso a internet. Los correos no se guardan como contactos del cliente. Es un recibo comercial no fiscal. No enviar datos sensibles adicionales ni usarlo como factura fiscal autorizada.

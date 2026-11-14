# Menu completo para Android

Esta compilación ejecuta la aplicación Python/Qt completa en Android y guarda sus datos localmente. No requiere la caja de Windows. El proyecto `android/` sigue siendo la terminal PedidosTable que se conecta a una PC; son aplicaciones distintas.

## Descargar e instalar

En GitHub Actions abre **Menu completo Android** y descarga el artefacto **Tisamar-Menu-Android-ARM64** de una ejecución correcta. Extrae el ZIP e instala el APK en un dispositivo ARM64 con Android 9 o posterior. Android puede pedir permiso para instalar aplicaciones desde el navegador o explorador de archivos utilizado.

El primer APK es una compilación **debug para pruebas**, no una publicación de Google Play. No se ha validado todavía en un dispositivo físico. La compilación inicial ocupa aproximadamente 167 MiB.

La aplicación crea su propia base de datos. No copia usuarios, productos, cuentas ni inventarios de la PC. En una instalación nueva, el acceso inicial de Admin mantiene las credenciales iniciales del proyecto (`Admin` / `Admin`); configura la contraseña y los usuarios antes de usar datos reales.

## Compilación

Archivo: `.github/workflows/menu-completo-android.yml`.

- Servidor Ubuntu 24.04 y Java 17.
- Qt for Python 6.12.0 y paquetes Android oficiales.
- SDK 35, NDK 28.2 y arquitectura ARM64.
- Pruebas de Python ejecutadas en X11 virtual antes de compilar.
- Preparación aislada del código mediante `tools/android/build_menu_android.py`.
- Los archivos de datos `.db`, SQLite y ejecutables de Windows no se empaquetan.
- El APK y los registros de diagnóstico quedan como artefactos de GitHub Actions.

Puede repetirse desde **Actions → Menu completo Android → Run workflow**. El proceso también se inicia al cambiar el workflow o `tools/android/`.

La firma debug de GitHub Actions es de prueba y puede cambiar entre ejecuciones. Antes de distribuir actualizaciones de uso diario se necesita configurar una clave de firma estable guardada como secreto, además de realizar las pruebas en Android.

## Comprobaciones realizadas en el primer APK

La ejecución `43569491067` completó las 30 pruebas y la compilación. Se verificó el APK descargado: manifiesto Android, bibliotecas ARM64 de Python 3.14 y Qt Widgets, módulos de caja/clientes/inventario/usuarios/PIN, archivos UI y recursos HTML. El paquete no contiene bases de datos del negocio.

Pendiente: instalar y probar inicio de sesión, teclado táctil, cobros, persistencia y cierre/reapertura en un dispositivo físico.

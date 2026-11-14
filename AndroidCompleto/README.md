# Android completo de Tisamar Menu

La versión Android queda por ahora en **0.1.6**, horizontal, con barra lateral y datos locales.
Esta carpeta reúne su entrega y sus herramientas dentro del proyecto de PC.

## Contenido

- `APK/Tisamar-Menu-Android-0.1.6-Barra-Lateral.apk`: APK actual, copiado y verificado en esta PC. Los APK se conservan localmente y no se suben a Git.
- `herramientas/build_menu_android.py`: prepara una copia temporal del código compartido y compila Android en GitHub Actions.
- `herramientas/run_tests.py`: ejecuta las pruebas compartidas desde la raíz de Menu.
- `herramientas/qa_prepare_login.py`: automatización exclusiva para la base de pruebas del emulador; no se incluye en el APK distribuido.
- `COMPILACION.md`: requisitos y detalles de compilación.

## Mejorar PC y Android a la par

El código común sigue en la raíz de `Menu`: `Main.py`, `clientes.py`, `inventario.py`, `usuarios.py`, `vista_pedidos.py`, `estilos.py`, pantallas `.ui` y demás módulos.
No hay una segunda copia independiente de ese código en esta carpeta. Cada compilación Android toma la revisión actual del proyecto.
`interfaz_adaptable.py` mantiene las diferencias de distribución para Android, sin aplicar esos ajustes a Windows.

Los datos de Windows y Android son independientes: compartir código no sincroniza usuarios, productos, cuentas ni inventarios.
La base `ventas.db` de la PC no se copia ni se empaqueta en el APK.

## Compilar cuando se necesite

En GitHub: Actions → **Menu completo Android** → Run workflow.
Los workflows deben permanecer en `.github/workflows/` porque GitHub los busca allí.
Se dejaron en modo manual, para seguir trabajando sin generar APKs en cada cambio.

Desde la raíz de Menu, las pruebas se ejecutan con:

```powershell
python AndroidCompleto/herramientas/run_tests.py
```

La carpeta `android/` anterior corresponde a la terminal PedidosTable conectada a una PC. Es distinta de esta aplicación Android completa y se mantiene aparte.

## Comprobación de la versión actual

Código de la versión: `82f84d3`. Compilación: https://github.com/Bakachi12/Menu/actions/runs/43583018714
34 pruebas correctas. En emulador Android se comprobó el acceso Admin y que Inicio no necesita scroll.
También se comprobó la distribución a 800×360, 915×412 y 1280×800. Falta validar los flujos completos en una tablet física.

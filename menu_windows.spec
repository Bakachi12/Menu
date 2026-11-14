# Compilación reproducible: python -m PyInstaller --clean --noconfirm menu_windows.spec
from pathlib import Path

raiz = Path(SPECPATH)
recursos = ['inicio.ui', 'pedido.ui', 'confirmar_cobro.ui', 'fondo_bar.png', 'pedidos_table.html']
a = Analysis(
    [str(raiz / 'Main.py')], pathex=[str(raiz)],
    binaries=[], datas=[(str(raiz / nombre), '.') for nombre in recursos]
    + [(str(raiz / 'imagenes_pagos'), 'imagenes_pagos')],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[], noarchive=False, optimize=0,
)
# Qt usa la API ICU de Windows (funciones sin sufijo). PyInstaller puede recoger
# por PATH la ICU de Poppler/Conda, cuyos símbolos llevan sufijo de versión.
# No empaquetar esas DLL: deben resolverse desde Windows, como al ejecutar Python.
a.binaries = [entrada for entrada in a.binaries
              if Path(entrada[0]).name.lower() != 'icuuc.dll'
              and not Path(entrada[0]).name.lower().startswith('icudt')]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='Menu',
          debug=False, bootloader_ignore_signals=False, strip=False,
          upx=True, upx_exclude=[], runtime_tmpdir=None, console=False,
          disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None)

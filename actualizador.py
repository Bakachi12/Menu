"""Comprobación e instalación segura de versiones publicadas en GitHub Releases."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen

from version import __version__

API_RELEASE = "https://api.github.com/repos/Bakachi12/Menu/releases/latest"
AGENTE = "Menu-Windows-Updater"
SCRIPT_PS = r'''param([string]$Destino, [string]$Descarga, [int]$PidAplicacion)
$ErrorActionPreference = 'Stop'
$respaldo = "$Destino.anterior"
try {
    Wait-Process -Id $PidAplicacion -Timeout 180 -ErrorAction Stop
    for ($intento = 0; $intento -lt 20; $intento++) {
        try {
            if (Test-Path -LiteralPath $respaldo) { Remove-Item -LiteralPath $respaldo -Force }
            Move-Item -LiteralPath $Destino -Destination $respaldo -Force
            Move-Item -LiteralPath $Descarga -Destination $Destino -Force
            $nuevo = Start-Process -FilePath $Destino -WorkingDirectory (Split-Path -Parent $Destino) -PassThru
            Start-Sleep -Seconds 10
            if (Get-Process -Id $nuevo.Id -ErrorAction SilentlyContinue) {
                Remove-Item -LiteralPath $respaldo -Force -ErrorAction SilentlyContinue
                exit 0
            }
            Move-Item -LiteralPath $Destino -Destination "$Destino.fallido" -Force
            Move-Item -LiteralPath $respaldo -Destination $Destino -Force
            $env:MENU_SKIP_AUTO_UPDATE = '1'
            Start-Process -FilePath $Destino -WorkingDirectory (Split-Path -Parent $Destino)
            exit 1
        } catch {
            if ((Test-Path -LiteralPath $respaldo) -and -not (Test-Path -LiteralPath $Destino)) {
                Move-Item -LiteralPath $respaldo -Destination $Destino -Force -ErrorAction SilentlyContinue
            }
            Start-Sleep -Seconds 2
        }
    }
} catch { }
'''


def _version(partes):
    texto = str(partes or "").strip().lstrip("vV")
    coincidencia = re.match(r"^(\d+(?:\.\d+)*)", texto)
    if not coincidencia:
        return None
    return tuple(int(parte) for parte in coincidencia.group(1).split("."))


def _es_mas_nueva(remota, instalada):
    a, b = _version(remota), _version(instalada)
    if a is None or b is None:
        return False
    largo = max(len(a), len(b))
    return a + (0,) * (largo - len(a)) > b + (0,) * (largo - len(b))


def _registrar(texto):
    try:
        carpeta = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TPVBar"
        carpeta.mkdir(parents=True, exist_ok=True)
        with (carpeta / "actualizador.log").open("a", encoding="utf-8") as archivo:
            archivo.write(f"{texto}\n")
    except OSError:
        pass


def comprobar_e_instalar():
    """Descarga una Release nueva y delega el reemplazo del EXE a PowerShell.

    Devuelve True si se inició el reemplazo; se invoca solo desde el EXE de Windows,
    antes de crear la ventana y abrir la base de datos.
    """
    if (sys.platform != "win32" or not getattr(sys, "frozen", False)
            or os.environ.get("MENU_SKIP_AUTO_UPDATE") == "1"):
        return False

    ejecutable = Path(sys.executable).resolve()
    if not ejecutable.is_file() or not os.access(ejecutable.parent, os.W_OK):
        _registrar("Actualización omitida: carpeta del ejecutable sin permiso de escritura.")
        return False

    try:
        request = Request(API_RELEASE, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": AGENTE,
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urlopen(request, timeout=5) as respuesta:
            release = json.loads(respuesta.read().decode("utf-8"))
        etiqueta = release.get("tag_name", "")
        if release.get("draft") or release.get("prerelease") or not _es_mas_nueva(etiqueta, __version__):
            return False

        asset = next((item for item in release.get("assets", [])
                      if item.get("name") == "Menu.exe" and item.get("state") == "uploaded"), None)
        if not asset or not asset.get("browser_download_url"):
            _registrar(f"Release {etiqueta} no incluye Menu.exe; no se actualizó.")
            return False

        carpeta = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TPVBar" / "actualizaciones"
        carpeta.mkdir(parents=True, exist_ok=True)
        descarga = carpeta / "Menu.nuevo.exe"
        request = Request(asset["browser_download_url"], headers={"User-Agent": AGENTE})
        digest = hashlib.sha256()
        tamano = 0
        with urlopen(request, timeout=30) as respuesta, descarga.open("wb") as archivo:
            while True:
                bloque = respuesta.read(1024 * 1024)
                if not bloque:
                    break
                archivo.write(bloque)
                digest.update(bloque)
                tamano += len(bloque)

        if tamano <= 0 or (asset.get("size") and tamano != asset["size"]):
            descarga.unlink(missing_ok=True)
            raise ValueError("El tamaño del ejecutable descargado no coincide con la Release.")
        checksum = asset.get("digest") or ""
        if checksum.startswith("sha256:") and digest.hexdigest().lower() != checksum[7:].lower():
            descarga.unlink(missing_ok=True)
            raise ValueError("La verificación SHA-256 del ejecutable falló.")

        script = carpeta / "aplicar_actualizacion.ps1"
        script.write_text(SCRIPT_PS, encoding="utf-8")
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if not powershell.is_file():
            raise FileNotFoundError("No se encontró Windows PowerShell para aplicar la actualización.")
        inicio = subprocess.STARTUPINFO()
        inicio.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        comando = [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                   "-File", str(script), "-Destino", str(ejecutable), "-Descarga", str(descarga),
                   "-PidAplicacion", str(os.getpid())]
        subprocess.Popen(comando, cwd=str(ejecutable.parent), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         startupinfo=inicio, creationflags=subprocess.CREATE_NO_WINDOW,
                         close_fds=True)
        _registrar(f"Descargada {etiqueta}; se reemplazará el ejecutable y se reiniciará Menu.")
        return True
    except Exception as error:
        _registrar(f"No se pudo instalar una actualización: {type(error).__name__}: {error}")
        return False

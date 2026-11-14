"""Prepare an isolated full-application source tree and build it with Qt for Python."""
import argparse
import configparser
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen, urlretrieve

VERSION = '6.12.0'

def stage(root, destination):
    destination.mkdir(parents=True, exist_ok=False)
    for source in root.glob('*.py'):
        if source.name != 'Main.py':
            shutil.copy2(source, destination / source.name)
    shutil.copy2(root / 'Main.py', destination / 'main.py')
    for extension in ('*.ui', '*.html', '*.png'):
        for source in root.glob(extension):
            shutil.copy2(source, destination / source.name)
    for name in ('imagenes_pagos', 'Imagenes_productos'):
        if (root / name).is_dir():
            shutil.copytree(root / name, destination / name)
    # No business database or credentials from the Windows machine may be bundled.
    assert not list(destination.rglob('*.db'))
    return destination

def download_wheel(package, arch, directory):
    base = f'https://download.qt.io/official_releases/QtForPython/{package.lower()}/'
    with urlopen(base, timeout=90) as response:
        index = response.read().decode()
    wheels = re.findall(r'href="([^"]+\.whl)"', index)
    matches = [name for name in wheels if name.lower().startswith(package.lower() + '-' + VERSION + '-')
               and name.endswith(f'android_{arch}.whl')]
    if not matches:
        raise RuntimeError(f'No official {package} {VERSION} Android {arch} wheel found')
    name = sorted(matches)[-1]
    target = directory / name
    urlretrieve(base + name, target)
    print(f'{name}: sha256 {hashlib.file_digest(target.open("rb"), "sha256").hexdigest()}', flush=True)
    return target.resolve()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage-only', action='store_true')
    parser.add_argument('--arch', default='aarch64', choices=['aarch64', 'x86_64'])
    parser.add_argument('--sdk')
    parser.add_argument('--ndk')
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    target = stage(root, Path(args.destination).resolve())
    if args.stage_only:
        print(target)
        return
    wheels = target.parent / 'wheels'
    wheels.mkdir(exist_ok=True)
    pyside = download_wheel('PySide6', args.arch, wheels)
    shiboken = download_wheel('shiboken6', args.arch, wheels)
    command = ['pyside6-android-deploy', '--init', '--force', '--verbose', '--keep-deployment-files',
               '--name', 'TisamarMenu', '--wheel-pyside', str(pyside),
               '--wheel-shiboken', str(shiboken), '--sdk-path', args.sdk,
               '--ndk-path', args.ndk, '--extra-modules', 'Core,Gui,Widgets,UiTools,Network,OpenGL']
    subprocess.run(command, cwd=target, check=True)
    spec = target / 'buildozer.spec'
    if not spec.is_file():
        raise RuntimeError('Qt deployment did not create buildozer.spec')
    config = configparser.ConfigParser(interpolation=None)
    config.read(spec)
    settings = {
        'title': 'Tisamar Menu', 'package.name': 'menu', 'package.domain': 'pa.tisamar',
        'version': '0.1.4', 'source.include_exts': 'py,png,jpg,jpeg,ui,html,json,js',
        'source.exclude_exts': 'db,sqlite,sqlite3,exe', 'orientation': 'portrait,landscape',
        'android.permissions': 'INTERNET,ACCESS_NETWORK_STATE',
        'android.accept_sdk_license': 'True',
        'requirements': 'python3,sqlite3,openssl,shiboken6,PySide6',
        'icon.filename': str(target / 'fondo_bar.png'),
    }
    for key, value in settings.items():
        config.set('app', key, value)
    with spec.open('w') as output:
        config.write(output)
    # Buildozer 1.6 still looks in tools/bin, removed from current Android SDKs.
    sdk = Path(args.sdk)
    legacy = sdk / 'tools' / 'bin' / 'sdkmanager'
    if not legacy.exists():
        import shlex
        real = sorted((sdk / 'cmdline-tools').glob('*/bin/sdkmanager'))[-1].resolve()
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text('#!/bin/sh\nexec ' + shlex.quote(str(real)) + ' --sdk_root=' + shlex.quote(str(sdk)) + ' "$@"\n')
        legacy.chmod(0o755)
    subprocess.run(['buildozer', '-v', 'android', 'debug'], cwd=target, check=True)
    apks = list(target.rglob('*.apk'))
    # Qt deploy's bin_dir can refer to the parent of the staged source.
    if not apks:
        apks = list(target.parent.glob('*.apk'))
    if not apks:
        raise RuntimeError('Build finished without an APK')
    output = root / 'apk-output'
    output.mkdir(exist_ok=True)
    shutil.copy2(apks[0], output / f'Tisamar-Menu-{args.arch}-debug.apk')

if __name__ == '__main__':
    main()

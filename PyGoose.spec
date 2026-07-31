# -*- mode: python ; coding: utf-8 -*-
import sys

is_mac = sys.platform == 'darwin'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets/sounds', 'assets/sounds'),
        ('assets/fonts',  'assets/fonts'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries if is_mac else [],
    a.zipfiles if is_mac else [],
    a.datas   if is_mac else [],
    exclude_binaries=not is_mac,
    name='PyGoose',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if not is_mac:
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='PyGoose',
    )

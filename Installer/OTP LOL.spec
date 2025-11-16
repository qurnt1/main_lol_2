# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('f:\\Users\\qurnt1\\Documents\\MAIN_LOL v4\\config', 'config')]
binaries = []
hiddenimports = ['keyboard', 'pygame.mixer', 'pygame.sndarray', 'psutil', 'urllib3', 'pystray', 'PIL.Image', 'PIL.ImageTk']
tmp_ret = collect_all('ttkbootstrap')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['f:\\Users\\qurnt1\\Documents\\MAIN_LOL v4\\app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OTP LOL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['f:\\Users\\qurnt1\\Documents\\MAIN_LOL v4\\config\\imgs\\garen.ico'],
)

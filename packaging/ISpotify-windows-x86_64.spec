# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["../main.py"],
    pathex=[".."],
    binaries=[],
    datas=[("../assets", "assets")],
    hiddenimports=["PySide6.QtSvg"],
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
    name="ISpotify-windows-x86_64",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    version="windows-version.txt",
    icon=["../assets/branding/ispotify-logo.ico"],
)

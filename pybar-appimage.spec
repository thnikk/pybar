# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('style.css', '.'), ('modules_waybar', 'modules_waybar'), ('modules', 'modules')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={
        "gi": {
            "themes": ["Adwaita"],
            "icons": ["Adwaita"],
            "languages": ["en_US"],
            "module-versions": {
                "Gtk": "3.0",
            },
        },
    },
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pybar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pybar',
)

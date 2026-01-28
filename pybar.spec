# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('style.css', '.'),
        ('modules', 'modules'),
        ('fonts', 'fonts'),
    ],
    hiddenimports=collect_submodules('modules'),
    hookspath=[],
    hooksconfig={
        "gi": {
            "themes": ["Adwaita"],
            "icons": ["Adwaita"],
            "languages": ["en_US"],
            "module-versions": {
                "Gtk": "4.0",
                "Gtk4LayerShell": "1.0",
                "Gdk": "4.0",
                "GdkPixbuf": "2.0",
                "Pango": "1.0",
                "Gio": "2.0",
                "GLib": "2.0",
                "GObject": "2.0",
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
    a.binaries,
    a.datas,
    [],
    name='pybar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

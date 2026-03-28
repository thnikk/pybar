# -*- mode: python ; coding: utf-8 -*-
import os
import glob
from PyInstaller.utils.hooks import collect_submodules

# Include VERSION file only if it exists (written by CI before build)
extra_datas = []
if os.path.exists('VERSION'):
    extra_datas.append(('VERSION', '.'))


layer_shell_libs = glob.glob(
    '/usr/lib/**/libgtk4-layer-shell.so*', recursive=True
)
layer_shell_typelibs = glob.glob(
    '/usr/lib/**/girepository-1.0/Gtk4LayerShell*.typelib', recursive=True
)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(lib, '.') for lib in layer_shell_libs],
    datas=[
        ('LICENSE', '.'),
        ('style.css', '.'),
        ('modules', 'modules'),
        ('fonts', 'fonts'),
        ('assets', 'assets'),
    ] + [(tl, 'gi_typelibs/') for tl in layer_shell_typelibs] + extra_datas,
    hiddenimports=collect_submodules('modules') + collect_submodules('dasbus') + [
        'requests',
        'aiohttp',
        'hid',
        'pulsectl',
        'psutil',
        'transmission_rpc',
        'colorsys',
        'evdev',
        'icalendar',
        'caldav',
    ],
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
                "Rsvg": "2.0",
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
    upx_exclude=[],
    runtime_tmpdir=None,
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

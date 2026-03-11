"""
Description: Font registration and resource path helpers
Author: thnikk
"""
import os
import sys


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller."""
    if getattr(sys, 'frozen', False):
        # PyInstaller bundles everything under _MEIPASS
        base_path = sys._MEIPASS
    else:
        # Walk up from common/ to the project root
        base_path = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def register_fonts(font_dir):
    """
    Register fonts with fontconfig for the application.
    For PyInstaller, copy fonts to permanent cache to avoid temp path issues.
    """
    import shutil
    from ctypes import CDLL, c_char_p, c_bool, c_void_p
    from common.helpers import print_debug

    # If running from PyInstaller temp dir, copy fonts to cache
    if getattr(sys, 'frozen', False) and '_MEI' in font_dir:
        cache_fonts_dir = os.path.expanduser('~/.cache/pybar/fonts')
        try:
            os.makedirs(cache_fonts_dir, exist_ok=True)

            if os.path.exists(font_dir):
                for font_file in os.listdir(font_dir):
                    src = os.path.join(font_dir, font_file)
                    dst = os.path.join(cache_fonts_dir, font_file)
                    if os.path.isfile(src):
                        # Only copy if missing or outdated
                        if not os.path.exists(dst) or \
                           os.path.getmtime(src) > os.path.getmtime(dst):
                            shutil.copy2(src, dst)

            font_dir = cache_fonts_dir
            print_debug(
                f"Copied fonts to permanent cache: {cache_fonts_dir}",
                color='green'
            )
        except Exception as e:
            print_debug(
                f"Failed to copy fonts to cache: {e}",
                color='red'
            )

    try:
        fontconfig = CDLL('libfontconfig.so.1')
        fontconfig.FcConfigAppFontAddDir.argtypes = [c_void_p, c_char_p]
        fontconfig.FcConfigAppFontAddDir.restype = c_bool
        success = fontconfig.FcConfigAppFontAddDir(
            None, font_dir.encode('utf-8'))
        print_debug(f"Registered fonts in {font_dir}: {success}")
    except Exception as e:
        print_debug(f"Font registration failed: {e}", color='red')

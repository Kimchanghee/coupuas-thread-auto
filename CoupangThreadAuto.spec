# -*- mode: python ; coding: utf-8 -*-


import os
import playwright

playwright_driver = os.path.join(os.path.dirname(playwright.__file__), "driver")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('fonts', 'fonts'), ('images/app_icon.ico', 'images'), (playwright_driver, 'playwright/driver')],
    hiddenimports=['google.generativeai', 'google.ai.generativelanguage', 'google.api_core', 'google.auth', 'google.protobuf', 'grpc', 'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.sip', 'playwright', 'playwright.sync_api', 'playwright.async_api', 'playwright._impl', 'PIL', 'PIL.Image', 'requests', 'urllib3', 'json', 'hashlib', 're', 'asyncio', 'packaging', 'packaging.version', 'packaging.specifiers', 'src', 'src.main_window', 'src.config', 'src.coupang_uploader', 'src.settings_dialog', 'src.threads_playwright_helper', 'src.computer_use_agent', 'src.auto_updater', 'src.update_dialog', 'src.login_window', 'src.auth_client', 'src.runtime_security', 'src.theme', 'src.events', 'src.tutorial', 'src.services', 'src.services.aggro_generator', 'src.services.image_search', 'src.services.link_history', 'src.services.coupang_parser'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'tkinter', 'test', 'unittest'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CoupangThreadAuto',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='images/app_icon.ico',
)

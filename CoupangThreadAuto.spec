# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('src', 'src'), ('C:\\Users\\HOME\\Documents\\GitHub\\coupuas-thread-auto\\.venv\\Lib\\site-packages\\playwright\\driver', 'playwright/driver')],
    hiddenimports=['google.generativeai', 'google.ai.generativelanguage', 'google.api_core', 'google.auth', 'google.protobuf', 'grpc', 'PyQt5', 'PyQt5.QtWidgets', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.sip', 'playwright', 'playwright.sync_api', 'playwright.async_api', 'playwright._impl', 'PIL', 'PIL.Image', 'requests', 'urllib3', 'json', 'hashlib', 're', 'asyncio', 'src', 'src.main_window', 'src.config', 'src.coupang_uploader', 'src.settings_dialog', 'src.threads_playwright_helper', 'src.computer_use_agent', 'src.services', 'src.services.aggro_generator', 'src.services.image_search', 'src.services.link_history', 'src.services.coupang_parser', 'src.services.telegram_service'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'tkinter', 'test', 'unittest'],
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
    name='CoupangThreadAuto',
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
)

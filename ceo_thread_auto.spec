# -*- mode: python ; coding: utf-8 -*-
"""
Coupang Partners Thread Auto - PyInstaller Spec File
빌드 명령어: pyinstaller --clean ceo_thread_auto.spec
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

block_cipher = None

# 프로젝트 루트 경로
project_root = os.path.dirname(os.path.abspath(SPEC))

# 모든 숨겨진 imports 수집
hidden_imports = [
    # ============ src 패키지 (쿠팡 파트너스 전용) ============
    'src',
    'src.main_window',
    'src.config',
    'src.coupang_uploader',
    'src.settings_dialog',
    'src.computer_use_agent',
    'src.threads_playwright_helper',
    'src.threads_uploader',

    # services 패키지 (쿠팡 파트너스)
    'src.services',
    'src.services.coupang_parser',
    'src.services.alibaba1688_service',
    'src.services.aggro_generator',
    'src.services.telegram_service',

    # ============ Google/Gemini AI ============
    'google',
    'google.generativeai',
    'google.generativeai.types',
    'google.generativeai.client',
    'google.generativeai.models',
    'google.genai',
    'google.genai.types',
    'google.genai.client',
    'google.genai.models',
    'google.ai',
    'google.ai.generativelanguage',
    'google.ai.generativelanguage_v1beta',
    'google.api_core',
    'google.api_core.gapic_v1',
    'google.api_core.exceptions',
    'google.api_core.retry',
    'google.auth',
    'google.auth.credentials',
    'google.auth.transport',
    'google.auth.transport.requests',
    'google.oauth2',
    'google.protobuf',
    'google.protobuf.json_format',
    'googleapis_common_protos',
    'proto',
    'proto.marshal',

    # ============ gRPC ============
    'grpc',
    'grpc._cython',
    'grpc._cython.cygrpc',
    'grpc.experimental',
    'grpc_status',

    # ============ Playwright ============
    'playwright',
    'playwright.sync_api',
    'playwright.async_api',
    'playwright._impl',
    'pyee',
    'pyee.base',

    # ============ HTTP/Network ============
    'requests',
    'requests.adapters',
    'requests.auth',
    'requests.sessions',
    'urllib3',
    'urllib3.util',
    'httpx',
    'httpcore',
    'h11',
    'certifi',
    'idna',
    'charset_normalizer',

    # ============ Pillow (PIL) ============
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',

    # ============ Tkinter ============
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    'tkinter.scrolledtext',

    # ============ Pydantic ============
    'pydantic',
    'pydantic.main',
    'pydantic_core',
    'annotated_types',
    'typing_extensions',

    # ============ Async/Concurrency ============
    'anyio',
    'anyio._core',
    'anyio._backends',
    'sniffio',

    # ============ 기타 필수 모듈 ============
    'dotenv',
    'tqdm',
    'tenacity',
    'colorama',

    # ============ DuckDuckGo 검색 ============
    'duckduckgo_search',
    'duckduckgo_search.duckduckgo_search',

    # ============ 표준 라이브러리 ============
    'json',
    'base64',
    'io',
    'os',
    'sys',
    'time',
    'datetime',
    'threading',
    'concurrent',
    'concurrent.futures',
    'typing',
    'dataclasses',
    'pathlib',
    'tempfile',
    'shutil',
    're',
    'traceback',
    'logging',
    'hashlib',
    'uuid',
]

# 데이터 파일 수집
datas = []
binaries = []

# Google 관련 전체 수집
try:
    tmp_ret = collect_all('google.generativeai')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hidden_imports += tmp_ret[2]
except Exception as e:
    print(f"Warning: google.generativeai collect failed: {e}")

try:
    tmp_ret = collect_all('google.genai')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hidden_imports += tmp_ret[2]
except Exception as e:
    print(f"Warning: google.genai collect failed: {e}")

try:
    tmp_ret = collect_all('google.api_core')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hidden_imports += tmp_ret[2]
except Exception as e:
    print(f"Warning: google.api_core collect failed: {e}")

try:
    tmp_ret = collect_all('google.protobuf')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hidden_imports += tmp_ret[2]
except Exception as e:
    print(f"Warning: google.protobuf collect failed: {e}")

# Playwright 전체 수집
try:
    tmp_ret = collect_all('playwright')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hidden_imports += tmp_ret[2]
except Exception as e:
    print(f"Warning: playwright collect failed: {e}")

# grpc 전체 수집
try:
    tmp_ret = collect_all('grpc')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hidden_imports += tmp_ret[2]
except Exception as e:
    print(f"Warning: grpc collect failed: {e}")

# pydantic 전체 수집
try:
    tmp_ret = collect_all('pydantic')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hidden_imports += tmp_ret[2]
except Exception as e:
    print(f"Warning: pydantic collect failed: {e}")

# certifi 인증서 포함
try:
    import certifi
    datas += [(certifi.where(), 'certifi')]
except Exception as e:
    print(f"Warning: certifi collect failed: {e}")

# Analysis
a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=binaries,
    datas=datas + [
        ('src', 'src'),  # src 폴더 전체 포함
        ('fonts', 'fonts'),  # UI fonts (Pretendard 등)
    ],
    hiddenimports=list(set(hidden_imports)),  # 중복 제거
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 불필요한 대용량 모듈 제외
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'sklearn',
        'tensorflow',
        'torch',
        'cv2',
        'opencv',
        'jupyter',
        'IPython',
        'notebook',
        'pytest',
        'unittest',
        'test',
        'tests',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ (Python 아카이브)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# EXE - 단일 실행 파일
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Coupang_Thread_Auto',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 콘솔 표시 (로그 확인용, 배포시 False로 변경)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 아이콘 파일: 'icon.ico'
)

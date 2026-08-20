# -*- mode: python ; coding: utf-8 -*-
"""
dpdp_scanner.spec
------------------
PyInstaller build spec. Produces a single DPDP_Scanner.exe with Python,
FastAPI, uvicorn, SQLAlchemy, httpx, and BeautifulSoup all bundled in —
no separate install needed on the machine that runs it.

Build with:  python -m PyInstaller dpdp_scanner.spec --clean --noconfirm
(or just run BUILD.bat, which does this for you)
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [('gui', 'gui')]
datas += collect_data_files('certifi')  # CA bundle used by httpx for HTTPS requests

hiddenimports = []
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('sqlalchemy.dialects.sqlite')
hiddenimports += [
    'httpx', 'httpcore', 'h11', 'anyio', 'sniffio',
    'bs4', 'soupsieve',
    'fastapi', 'starlette', 'pydantic', 'pydantic_core',
]

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name='DPDP_Scanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,           # keep a console window visible (shows the dashboard URL, logs, errors)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

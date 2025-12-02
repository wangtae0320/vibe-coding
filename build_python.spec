# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for PDF 문서 비교 프로그램
Python 3.11.4 호환
"""

import sys
import os

block_cipher = None

# PySide6 데이터 파일 수집 (선택적)
try:
    from PyInstaller.utils.hooks import collect_data_files
    pyside6_datas = collect_data_files('PySide6', includes=['**/*.dll', '**/*.so', '**/*.dylib'])
    pymupdf_datas = collect_data_files('fitz')
    datas_list = pyside6_datas + pymupdf_datas
except ImportError:
    # PyInstaller가 설치되지 않았거나 버전이 낮은 경우
    datas_list = []

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtOpenGL',
        'fitz',
        'PIL',
        'PIL._tkinter_finder',
        'pandas',
        'openpyxl',
        'openpyxl.cell._writer',
        'numpy',
        'numpy.core._methods',
        'numpy.lib.format',
        'difflib',
        'json',
        'threading',
        'traceback',
        'collections',
        'collections.abc',
        'dataclasses',
        'typing',
        'typing_extensions',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PDF문서비교프로그램',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 애플리케이션이므로 콘솔 창 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 아이콘 파일이 있다면 경로 지정
)


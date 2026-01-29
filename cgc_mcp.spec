# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['cgc/mcp/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'spacy', 'gliner', 'scipy', 'sklearn', 'transformers', 'thinc'],
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
    name='cgc_mcp',
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

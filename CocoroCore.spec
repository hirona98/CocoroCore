# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\MyProject\\AliceEncoder\\DesktopAssistant\\CocoroAI\\CocoroCore\\.venv\\Lib\\site-packages\\tiktoken', 'tiktoken'), ('D:\\MyProject\\AliceEncoder\\DesktopAssistant\\CocoroAI\\CocoroCore\\.venv\\Lib\\site-packages\\tiktoken_ext', 'tiktoken_ext'), ('D:\\MyProject\\AliceEncoder\\DesktopAssistant\\CocoroAI\\CocoroCore\\.venv\\Lib\\site-packages\\litellm\\litellm_core_utils\\tokenizers', 'litellm/litellm_core_utils/tokenizers')],
    hiddenimports=['tiktoken', 'tiktoken.core', 'litellm', 'litellm.utils', 'litellm.litellm_core_utils.tokenizers'],
    hookspath=[],
    hooksconfig={},
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
    name='CocoroCore',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name='CocoroCore',
)

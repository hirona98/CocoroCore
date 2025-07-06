#!/usr/bin/env python
"""PyInstallerスペックファイルを動的に生成するスクリプト"""

import sys
import os
from pathlib import Path

def create_spec_file():
    """仮想環境のパスを動的に検出してスペックファイルを生成"""
    
    # 仮想環境のsite-packagesパスを取得
    if hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix):
        # 仮想環境内
        if sys.platform == "win32":
            site_packages = Path(sys.prefix) / "Lib" / "site-packages"
        else:
            site_packages = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    else:
        # システムPython
        import site
        site_packages = Path(site.getsitepackages()[0])
    
    print(f"Site-packages path: {site_packages}")
    
    # 必要なデータファイルをチェック
    data_entries = []
    
    # tiktoken
    tiktoken_path = site_packages / "tiktoken"
    if tiktoken_path.exists():
        data_entries.append(f"('{tiktoken_path}', 'tiktoken')")
        print(f"✅ tiktoken found: {tiktoken_path}")
    
    # tiktoken_ext
    tiktoken_ext_path = site_packages / "tiktoken_ext"
    if tiktoken_ext_path.exists():
        data_entries.append(f"('{tiktoken_ext_path}', 'tiktoken_ext')")
        print(f"✅ tiktoken_ext found: {tiktoken_ext_path}")
    
    # litellm tokenizers
    litellm_tokenizers_path = site_packages / "litellm" / "litellm_core_utils" / "tokenizers"
    if litellm_tokenizers_path.exists():
        data_entries.append(f"('{litellm_tokenizers_path}', 'litellm/litellm_core_utils/tokenizers')")
        print(f"✅ litellm tokenizers found: {litellm_tokenizers_path}")
    
    # mcp (オプショナル)
    mcp_path = site_packages / "mcp"
    if mcp_path.exists():
        data_entries.append(f"('{mcp_path}', 'mcp')")
        print(f"✅ mcp found: {mcp_path}")
    else:
        print("⚠️ mcp not found (optional)")
    
    # hiddenimportsリスト
    hidden_imports = [
        'tiktoken',
        'tiktoken.core', 
        'litellm',
        'litellm.utils',
        'litellm.litellm_core_utils.tokenizers'
    ]
    
    # MCPが利用可能な場合は追加
    if mcp_path.exists():
        hidden_imports.extend([
            'mcp',
            'mcp.client',
            'mcp.client.stdio', 
            'mcp.types'
        ])
    
    # スペックファイルの内容を生成
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src\\\\main.py'],
    pathex=[],
    binaries=[],
    datas=[{', '.join(data_entries)}],
    hiddenimports={hidden_imports},
    hookspath=[],
    hooksconfig={{}},
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
"""
    
    # スペックファイルを書き込み
    spec_file_path = "CocoroCore.spec"
    with open(spec_file_path, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"✅ Spec file created: {spec_file_path}")
    return spec_file_path

if __name__ == "__main__":
    create_spec_file()
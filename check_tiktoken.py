#!/usr/bin/env python
"""
tiketokenのエンコーディングデータの場所を確認するスクリプト
"""

import os
import sys
import tiktoken
from tiktoken.registry import get_encoding


def check_tiktoken_data():
    """tiketokenのデータファイルの場所を確認する"""
    print(f"Tiktoken version: {tiktoken.__version__}")
    print(f"Tiktoken module path: {os.path.dirname(tiktoken.__file__)}")

    # モジュール内のファイルを確認
    tiktoken_dir = os.path.dirname(tiktoken.__file__)
    print(f"Files in tiktoken directory: {os.listdir(tiktoken_dir)}")

    # site-packagesディレクトリを確認
    site_packages = next(p for p in sys.path if "site-packages" in p)
    print(f"Site packages: {site_packages}")

    # tiktoken_extの確認
    tiktoken_ext_path = os.path.join(site_packages, "tiktoken_ext")
    if os.path.exists(tiktoken_ext_path):
        print(f"tiktoken_ext exists: {True}")
        print(f"Files in tiktoken_ext: {os.listdir(tiktoken_ext_path)}")
    else:
        print(f"tiktoken_ext does not exist")

    # エンコーディングの読み込みテスト
    print("\nTesting encoding access:")
    try:
        enc = get_encoding("cl100k_base")
        print(f"Successfully loaded cl100k_base encoding")
        print(f"First tokens of 'Hello world': {enc.encode('Hello world')[:10]}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    check_tiktoken_data()

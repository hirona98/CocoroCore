#!/usr/bin/env python
"""
litellmモジュールのディレクトリ構造を確認するスクリプト
"""

import os
import litellm
import sys


def check_litellm_structure():
    """litellmのディレクトリ構造を確認する"""
    print(f"LiteLLM module path: {os.path.dirname(litellm.__file__)}")

    # バージョン情報を取得（可能であれば）
    try:
        print(f"LiteLLM version: {litellm.__version__}")
    except AttributeError:
        print("LiteLLM version: Not available")

    # モジュール内のディレクトリ構造を確認
    litellm_dir = os.path.dirname(litellm.__file__)
    print(f"\nFiles in litellm directory:")

    for root, dirs, files in os.walk(litellm_dir):
        rel_path = os.path.relpath(root, litellm_dir)
        if rel_path == ".":
            print(f"\nRoot directory:")
        else:
            print(f"\n{rel_path}:")

        for d in dirs:
            print(f"  Dir: {d}")
        for f in files:
            print(f"  File: {f}")


if __name__ == "__main__":
    check_litellm_structure()

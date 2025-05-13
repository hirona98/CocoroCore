#!/usr/bin/env python
# filepath: d:\MyProject\AliceEncoder\DesktopAssistant\CocoroAI\CocoroCore\build_cocoro.py
"""
CocoroCore ビルドスクリプト（簡略化版）
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# ビルド設定
DEFAULT_CONFIG = {
    "app_name": "CocoroCore",
    "icon_path": None,  # アイコンが必要な場合は "resources/icon.ico" などを指定
    "hidden_imports": [],  # 必要に応じて依存モジュールを追加
    "onefile": True,  # True: 単一実行ファイル、False: フォルダ形式
    "console": False,  # True: コンソール表示、False: 非表示
}


def build_cocoro(config=None):
    """CocoroCoreのWindowsバイナリをビルドする簡略化関数"""
    # 設定を使用または初期化
    build_config = config or DEFAULT_CONFIG
    app_name = build_config["app_name"]

    print(f"\n=== {app_name} ビルドを開始します ===")

    # PyInstallerのインストール確認
    try:
        subprocess.check_call([sys.executable, "-c", "import PyInstaller"])
        print("✅ PyInstallerは既にインストールされています")
    except subprocess.CalledProcessError:
        print("📦 PyInstallerをインストールしています...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # ビルドディレクトリをクリーンアップ
    for dir_name in ["dist", "build"]:
        dir_path = Path(dir_name)
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"🗑️ {dir_name} ディレクトリをクリーンアップしました")

    # PyInstallerコマンドの構築
    pyinstaller_args = [
        "pyinstaller",
        f"--name={app_name}",
        "--clean",
    ]

    # 単一ファイル/フォルダ形式の設定
    if build_config["onefile"]:
        pyinstaller_args.append("--onefile")

    # コンソール表示/非表示の設定
    if build_config["console"]:
        pyinstaller_args.append("--console")
    else:
        pyinstaller_args.append("--noconsole")

    # アイコン設定
    if build_config["icon_path"] and os.path.exists(build_config["icon_path"]):
        pyinstaller_args.append(f"--icon={build_config['icon_path']}")

    # 依存モジュール設定
    for imp in build_config["hidden_imports"]:
        pyinstaller_args.append(f"--hidden-import={imp}")

    # メインスクリプト追加
    pyinstaller_args.append("cocoro_core.py")

    # コマンド実行
    print("\n📋 実行するコマンド:", " ".join(pyinstaller_args))
    subprocess.call(pyinstaller_args)

    # 結果確認
    exe_path = Path("dist") / f"{app_name}.exe"
    if exe_path.exists():
        print(f"\n✨ ビルド成功！実行ファイル: {exe_path}")
        return True
    else:
        print("\n❌ ビルドに失敗しました。")
        return False


def main():
    """メイン関数"""
    # カスタム設定ファイルがあれば読み込む
    try:
        from build_config import BUILD_CONFIG

        print("ℹ️ カスタムビルド設定を読み込みました")
        build_cocoro(BUILD_CONFIG)
    except ImportError:
        print("ℹ️ デフォルトビルド設定を使用します")
        build_cocoro()


if __name__ == "__main__":
    main()

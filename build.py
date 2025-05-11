#!/usr/bin/env python
# filepath: d:\MyProject\AliceEncoder\DesktopAssistant\CocoroAI\CocoroCore\build.py
"""
CocoroCore Windowsバイナリビルドスクリプト
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from build_config import BUILD_CONFIG

    print("カスタムビルド設定を読み込みました")
except ImportError:
    print("デフォルトビルド設定を使用します")
    # デフォルトビルド設定
    BUILD_CONFIG = {
        "app_name": "CocoroCore",
        "icon_path": None,
        "hidden_imports": [],
        "onefile": True,
        "console": False,
    }


def check_pyinstaller():
    """PyInstallerがインストールされているか確認し、なければインストールする"""
    try:
        # 直接importせずに、モジュールが利用可能かどうかを確認
        subprocess.check_call([sys.executable, "-c", "import PyInstaller"])
        print("PyInstallerは既にインストールされています")
    except subprocess.CalledProcessError:
        print("PyInstallerをインストールしています...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build_binary():
    """CocoroCoreのWindowsバイナリをビルドする"""
    app_name = BUILD_CONFIG["app_name"]
    print(f"{app_name} Windowsバイナリのビルドを開始します...")

    # ビルド前にdistディレクトリをクリーンアップ
    dist_dir = Path("dist")
    build_dir = Path("build")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # PyInstallerコマンドを構築
    pyinstaller_args = [
        "pyinstaller",
        f"--name={app_name}",
    ]

    # ファイルタイプ (onefile/onedir)
    if BUILD_CONFIG["onefile"]:
        pyinstaller_args.append("--onefile")

    # コンソールの表示/非表示
    if BUILD_CONFIG["console"]:
        pyinstaller_args.append("--console")
    else:
        pyinstaller_args.append("--noconsole")

    # アイコンが指定されていれば追加
    if BUILD_CONFIG["icon_path"]:
        icon_path = BUILD_CONFIG["icon_path"]
        if os.path.exists(icon_path):
            pyinstaller_args.append(f"--icon={icon_path}")

    # クリーンビルド
    pyinstaller_args.append("--clean")

    # 隠しインポートを追加
    for imp in BUILD_CONFIG["hidden_imports"]:
        pyinstaller_args.append(f"--hidden-import={imp}")

    # メインスクリプトを追加
    pyinstaller_args.append("cocoro_core.py")

    # PyInstallerを実行
    print("実行するコマンド:", " ".join(pyinstaller_args))
    subprocess.call(pyinstaller_args)

    # ビルド成功のメッセージ
    exe_path = dist_dir / f"{app_name}.exe"
    if exe_path.exists():
        print("\nビルドが完了しました！")
        print(f"実行ファイル: {exe_path}")
    else:
        print("\nビルドに失敗しました。")


if __name__ == "__main__":
    check_pyinstaller()
    build_binary()

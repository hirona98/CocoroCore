#!/usr/bin/env python
"""CocoroCore ビルドスクリプト"""

import shutil
import subprocess
import sys
from pathlib import Path
import io

# Windows環境でのUTF-8出力対応
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ビルド設定
BUILD_CONFIG = {
    "app_name": "CocoroCore",
    "icon_path": None,  # アイコンが必要な場合は "resources/icon.ico" などを指定
    "hidden_imports": [
        # 最小限の必要なインポート
        "tiktoken",
        "tiktoken.core",
        "litellm",
        "litellm.utils",
        "litellm.litellm_core_utils.tokenizers",
    ],
    "onefile": False,  # True: 単一実行ファイル、False: フォルダ形式
    "console": False,  # True: コンソール表示、False: 非表示
    "datas": [],  # 動的に設定されるため、ここでは空にする
}


def build_cocoro(config=None):
    """CocoroCoreのWindowsバイナリをビルドする簡略化関数"""
    # 設定を使用または初期化
    build_config = config or BUILD_CONFIG
    app_name = build_config["app_name"]

    print(f"\n=== {app_name} ビルドを開始します ===")

    # 動的スペックファイル生成
    print("📋 動的スペックファイルを生成中...")
    try:
        from create_spec import create_spec_file
        spec_file = create_spec_file()
        print(f"✅ スペックファイル生成完了: {spec_file}")
    except Exception as e:
        print(f"❌ スペックファイル生成に失敗: {e}")
        print("既存のスペックファイルを使用します")
        spec_file = "CocoroCore.spec"

    # PyInstallerのインストール確認
    try:
        import importlib.util

        if importlib.util.find_spec("PyInstaller") is None:
            raise ImportError("PyInstaller is not installed")
        print("✅ PyInstallerは既にインストールされています")
    except ImportError:
        print("📦 PyInstallerをインストールしています...")
        # 固定文字列のみを使用してサブプロセスを実行
        try:
            # 安全な固定コマンドのみを使用
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "pyinstaller"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.SubprocessError as e:
            print(f"PyInstallerのインストールに失敗しました: {e}")
            sys.exit(1)

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

    # 依存モジュール設定
    for imp in build_config["hidden_imports"]:
        pyinstaller_args.append(f"--hidden-import={imp}")

    # データファイル設定（動的にパスを解決）
    # 仮想環境のsite-packagesパスを動的に取得
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        # 仮想環境内
        if sys.platform == "win32":
            # Windowsでは'Lib'と'lib'両方の可能性をチェック
            lib_path = Path(sys.prefix) / "Lib" / "site-packages"
            if not lib_path.exists():
                lib_path = Path(sys.prefix) / "lib" / "site-packages"
            site_packages = lib_path
        else:
            site_packages = (
                Path(sys.prefix)
                / "lib"
                / f"python{sys.version_info.major}.{sys.version_info.minor}"
                / "site-packages"
            )
    else:
        # システムPython
        import site

        site_packages = Path(site.getsitepackages()[0])

    # 必要なデータファイルを追加
    data_files = [
        (site_packages / "tiktoken", "tiktoken"),
        (site_packages / "tiktoken_ext", "tiktoken_ext"),
        (
            site_packages / "litellm" / "litellm_core_utils" / "tokenizers",
            "litellm/litellm_core_utils/tokenizers",
        ),
    ]

    for src, dst in data_files:
        if src.exists():
            pyinstaller_args.append(f"--add-data={src.as_posix()};{dst}")
    pyinstaller_args.append("src/main.py")

    # 動的スペックファイルを使用してビルド
    print(f"\n📋 PyInstallerでビルド中（{spec_file}使用）...")
    spec_args = ["pyinstaller", spec_file, "--clean"]
    print("📋 実行するコマンド:", " ".join(spec_args))
    subprocess.call(spec_args)

    # 結果確認
    # ビルド結果の確認（onefile設定に応じて判定方法を変更）
    if build_config["onefile"]:
        exe_path = Path("dist") / f"{app_name}.exe"
    else:
        exe_path = Path("dist") / app_name / f"{app_name}.exe"
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
        print("カスタムビルド設定を読み込みました")
        build_cocoro()
    except ImportError:
        print("デフォルトビルド設定を使用します")
        build_cocoro()


if __name__ == "__main__":
    main()

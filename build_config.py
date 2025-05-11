"""
CocoroCore ビルド設定ファイル
このファイルでビルド設定をカスタマイズできます
"""

# ビルド設定
BUILD_CONFIG = {
    # アプリケーション名
    "app_name": "CocoroCore",
    # アイコンファイル（.icoファイル）のパス（存在する場合）
    "icon_path": None,  # 例: "resources/icon.ico"
    # 含める追加モジュール
    "hidden_imports": [
        # 必要に応じて追加のモジュールを指定
    ],
    # 1つの実行可能ファイルにまとめるかどうか
    "onefile": True,
    # コンソールウィンドウを表示するかどうか
    "console": False,
}

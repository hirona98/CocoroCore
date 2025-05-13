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
        "tiktoken",
        "tiktoken.registry",
        "tiktoken._registry",
        "tiktoken.model",
        "tiktoken.core",
        "tiktoken.load",
        "tiktoken._educational",
        "litellm",
        "litellm.utils",
        "litellm.llms",
        "litellm.cost_calculator",
        "litellm.litellm_core_utils",
        "litellm.litellm_core_utils.llm_cost_calc",
        "litellm.litellm_core_utils.tokenizers",
    ],
    # 1つの実行可能ファイルにまとめるかどうか
    "onefile": True,
    # コンソールウィンドウを表示するかどうか
    "console": False,
    # データファイル
    "datas": [
        # tiketokenのエンコーディングモジュール全体を含める
        ("venv/Lib/site-packages/tiktoken", "tiktoken"),
        ("venv/Lib/site-packages/tiktoken_ext", "tiktoken_ext"),
        # litellmのトークナイザーデータファイルを含める
        (
            "venv/Lib/site-packages/litellm/litellm_core_utils/tokenizers",
            "litellm/litellm_core_utils/tokenizers",
        ),
    ],
}

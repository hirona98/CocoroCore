import argparse
import logging
from fastapi import FastAPI

from aiavatar.adapter.http.server import AIAvatarHttpServer
from aiavatar.sts.llm.litellm import LiteLLMService
from aiavatar.sts.pipeline import STSPipeline
from aiavatar.sts.tts import SpeechSynthesizerDummy

# from aiavatar.sts.llm.gemini import GeminiService
from config_loader import load_config


# コマンドライン引数を解析
parser = argparse.ArgumentParser(description="CocoroCore AI Assistant Server")
parser.add_argument(
    "folder_path", nargs="?", help="設定ファイルのフォルダパス（省略可）"
)
parser.add_argument("--config-dir", "-c", help="設定ファイルのディレクトリパス")
args = parser.parse_args()

# フォルダパスが位置引数で渡された場合は--config-dirより優先
if args.folder_path:
    args.config_dir = args.folder_path

# 設定ファイルを読み込む
config = load_config(args.config_dir if hasattr(args, "config_dir") else None)

# setting.jsonから値を取得
llm_api_key = config.get("characterList", [])[
    config.get("currentCharacterIndex", 0)
].get("apiKey")
llm_model = config.get("characterList", [])[config.get("currentCharacterIndex", 0)].get(
    "llmModel"
)
port = config.get("cocoroCorePort", 55601)

# https://docs.litellm.ai/docs/providers
llm = LiteLLMService(
    api_key=llm_api_key,
    model=llm_model,
    temperature=1.0,
    system_prompt="{system_prompt}",
)

custom_tts = SpeechSynthesizerDummy()

# デフォルトだとAIの発話が保存されるため明示的にFalse指定する
sts = STSPipeline(
    llm=llm,
    tts=custom_tts,
    voice_recorder_enabled=False,
)

# AIAvatarインスタンスを作成
aiavatar_app = AIAvatarHttpServer(
    sts=sts,
    debug=False,
)

# FastAPIアプリを設定し、AIAvatarのルーターを含める
app = FastAPI()
router = aiavatar_app.get_api_router()
app.include_router(router)

# サーバー起動
if __name__ == "__main__":
    import uvicorn
    import time

    # 設定情報のログ出力
    print("CocoroCore を起動します")
    print(
        f"設定ディレクトリ: {args.config_dir if hasattr(args, 'config_dir') and args.config_dir else '(デフォルト)'}"
    )
    print(f"使用ポート: {port}")

    # EXE実行時のログ設定を調整(デフォルトだとコンソールOFFの時に落ちる)
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": "%(levelname)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "simple",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["console"], "level": "INFO"},
        },
    }

    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_config=log_config)
    except Exception as e:
        print(f"サーバー起動エラー: {e}")
        import traceback

        traceback.print_exc()
        try:
            input("Enterキーを押すと終了します...")
        except RuntimeError:
            # EXE実行時にsys.stdinが利用できない場合
            print("5秒後に自動終了します...")
            time.sleep(5)

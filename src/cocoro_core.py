from aiavatar.adapter.http.server import AIAvatarHttpServer
from aiavatar.sts.llm.litellm import LiteLLMService
from aiavatar.sts.pipeline import STSPipeline
from aiavatar.sts.tts import SpeechSynthesizerDummy
from fastapi import FastAPI

from config_loader import load_config
from dummy_db import DummyContextManager, DummyPerformanceRecorder, DummyVoiceRecorder


def create_app(config_dir=None):
    """
    CocoroCore アプリケーションを作成する関数
    
    Args:
        config_dir (str, optional): 設定ディレクトリのパス. デフォルトはNone.
        
    Returns:
        tuple: (FastAPI アプリケーション, ポート番号)
    """
    # 設定ファイルを読み込む
    config = load_config(config_dir)

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
        context_manager=DummyContextManager(),  # context.dbを生成しないようにする
    )

    custom_tts = SpeechSynthesizerDummy()

    # デフォルトだとAIの発話が保存されるため明示的にFalse指定する
    sts = STSPipeline(
        llm=llm,
        tts=custom_tts,
        voice_recorder_enabled=False,
        performance_recorder=DummyPerformanceRecorder(),  # performance.dbを生成しないようにする
        voice_recorder=DummyVoiceRecorder(),  # recorded_voicesディレクトリを生成しないようにする
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
    
    return app, port


def get_log_config():
    """UVicornのログ設定を取得する"""
    return {
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

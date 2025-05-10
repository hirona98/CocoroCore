import os
from dotenv import load_dotenv
from fastapi import FastAPI
from aiavatar.adapter.websocket.server import AIAvatarWebSocketServer

# 環境変数を読み込む
load_dotenv()

# APIキーを環境変数から取得
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# APIキーが設定されていない場合はエラーメッセージを表示
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY が環境変数に設定されていません。.env ファイルまたは環境変数を確認してください。")

# AIAvatarインスタンスを作成
# ここで必要な設定（APIキー、LLMモデル、ボリューム閾値など）を行います
aiavatar_app = AIAvatarWebSocketServer(
    openai_api_key=OPENAI_API_KEY, # OpenAI APIキー
    volume_db_threshold=-30, # 音声環境に合わせて調整
    debug=True
)

# FastAPIアプリを設定し、AIAvatarのWebSocketルーターを含める
app = FastAPI()
router = aiavatar_app.get_websocket_router()
app.include_router(router)

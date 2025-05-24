import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import httpx
from aiavatar.adapter.http.server import AIAvatarHttpServer
from aiavatar.sts.llm.litellm import LiteLLMService
from aiavatar.sts.pipeline import STSPipeline
from aiavatar.sts.tts import SpeechSynthesizerDummy
from fastapi import FastAPI

# local imports
from config_loader import load_config
from dummy_db import DummyPerformanceRecorder, DummyVoiceRecorder

logger = logging.getLogger(__name__)


# ChatMemoryクライアントクラス
class ChatMemoryClient:
    """ChatMemoryサービスとの通信を管理するクライアント"""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self._message_queue = []
        self._queue_lock = asyncio.Lock()

    async def enqueue_messages(self, request, response):
        """メッセージをキューに追加"""
        async with self._queue_lock:
            self._message_queue.append(
                {
                    "role": "user",
                    "content": request.text,
                    "metadata": {"session_id": request.session_id, "user_id": request.user_id},
                }
            )
            self._message_queue.append(
                {
                    "role": "assistant",
                    "content": response.text,
                    "metadata": {"session_id": request.session_id, "user_id": request.user_id},
                }
            )

    async def save_history(self, user_id: str, session_id: str, channel: str = "cocoro_ai"):
        """キューに溜まったメッセージを履歴として保存"""
        async with self._queue_lock:
            if not self._message_queue:
                return

            messages = self._message_queue.copy()
            self._message_queue.clear()

        try:
            response = await self.client.post(
                f"{self.base_url}/history",
                json={
                    "user_id": user_id,
                    "session_id": session_id,
                    "channel": channel,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            print(f"[INFO] 履歴を保存しました: {len(messages)}件のメッセージ", flush=True)
        except Exception as e:
            logger.error(f"履歴の保存に失敗しました: {e}")
            # 失敗したメッセージをキューに戻す
            async with self._queue_lock:
                self._message_queue = messages + self._message_queue

    async def search(self, user_id: str, query: str, top_k: int = 5) -> Optional[str]:
        """過去の記憶を検索して回答を生成"""
        try:
            response = await self.client.post(
                f"{self.base_url}/search",
                json={
                    "user_id": user_id,
                    "query": query,
                    "top_k": top_k,
                    "search_content": True,
                    "include_retrieved_data": False,
                },
            )
            response.raise_for_status()
            result = response.json()
            return result["result"]["answer"]
        except Exception as e:
            logger.error(f"記憶の検索に失敗しました: {e}")
            return None

    async def create_summary(self, user_id: str, session_id: str = None):
        """指定したセッションの要約を生成"""
        try:
            params = {"user_id": user_id}
            if session_id:
                params["session_id"] = session_id

            response = await self.client.post(f"{self.base_url}/summary/create", params=params)
            response.raise_for_status()
            print(
                f"[INFO] 要約を生成しました: user_id={user_id}, session_id={session_id}", flush=True
            )
        except Exception as e:
            logger.error(f"要約の生成に失敗しました: {e}")

    async def close(self):
        """クライアントを閉じる"""
        await self.client.aclose()


def create_app(config_dir=None):
    """CocoroCore アプリケーションを作成する関数

    Args:
    ----
        config_dir (str, optional): 設定ディレクトリのパス. デフォルトはNone.

    Returns:
    -------
        tuple: (FastAPI アプリケーション, ポート番号)

    """
    # 設定ファイルを読み込む
    config = load_config(config_dir)

    # setting.jsonから値を取得
    current_char = config.get("characterList", [])[config.get("currentCharacterIndex", 0)]
    llm_api_key = current_char.get("apiKey")
    llm_model = current_char.get("llmModel")
    port = config.get("cocoroCorePort", 55601)

    # ChatMemory設定を取得
    memory_enabled = current_char.get("isEnableMemory", False)
    memory_port = config.get("cocoroMemoryPort", 55602)
    memory_url = f"http://localhost:{memory_port}"
    memory_client = None

    # セッションタイムアウト管理用の変数
    session_last_activity: Dict[str, datetime] = {}
    session_timeout_seconds = 300  # 5分
    timeout_check_task = None

    if memory_enabled:
        print(f"[INFO] ChatMemoryを有効化します: {memory_url}", flush=True)
        memory_client = ChatMemoryClient(memory_url)

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
        performance_recorder=DummyPerformanceRecorder(),  # performance.dbを生成しないようにする
        voice_recorder=DummyVoiceRecorder(),  # recorded_voicesディレクトリを生成しないようにする
    )

    # ChatMemoryとの統合
    if memory_client:
        # タイムアウトしたセッションをチェックして要約を生成する非同期タスク
        async def check_session_timeouts():
            while True:
                try:
                    await asyncio.sleep(30)  # 30秒ごとにチェック
                    current_time = datetime.now()
                    timeout_threshold = current_time - timedelta(seconds=session_timeout_seconds)

                    # タイムアウトしたセッションを検出
                    timed_out_sessions = []
                    for session_key, last_activity in list(session_last_activity.items()):
                        if last_activity < timeout_threshold:
                            timed_out_sessions.append(session_key)

                    # タイムアウトしたセッションの要約を生成
                    for session_key in timed_out_sessions:
                        try:
                            user_id, session_id = session_key.split(":", 1)
                            # バックグラウンドでも確実にログが表示されるようにprint文
                            print(f"[INFO] セッションタイムアウト検出: {session_key}", flush=True)
                            await memory_client.create_summary(user_id, session_id)
                            del session_last_activity[session_key]
                        except Exception as e:
                            logger.error(f"タイムアウト処理エラー: {e}")

                except Exception as e:
                    logger.error(f"セッションタイムアウトチェックエラー: {e}")

        # 会話終了時に履歴を保存
        @sts.on_finish
        async def save_to_memory(request, response):
            # セッションアクティビティを更新
            session_key = f"{request.user_id or 'default_user'}:{request.session_id}"
            session_last_activity[session_key] = datetime.now()

            await memory_client.enqueue_messages(request, response)
            # セッションごとに保存
            await memory_client.save_history(
                user_id=request.user_id or "default_user",
                session_id=request.session_id,
                channel="cocoro_ai",
            )

        # 記憶検索ツールを追加
        memory_search_spec = {
            "type": "function",
            "function": {
                "name": "search_memory",
                "description": "過去の会話や記憶から情報を検索します。ユーザーの好み、過去の話題、個人的な情報などを探す時に使用します。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "検索したい内容（例：ユーザーの好きな食べ物、前回話した内容など）",
                        }
                    },
                    "required": ["query"],
                },
            },
        }

        @sts.llm.tool(memory_search_spec)
        async def search_memory(query: str, metadata: dict = None):
            """過去の記憶を検索"""
            user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
            result = await memory_client.search(user_id, query)
            if result:
                return f"過去の記憶から以下の情報が見つかりました：\n{result}"
            else:
                return "関連する記憶が見つかりませんでした。"

        # システムプロンプトに記憶機能の説明を追加
        original_prompt = llm.system_prompt
        llm.system_prompt = (
            original_prompt
            + "\n\n"
            + """
記憶機能について：
あなたは長期記憶機能を持っています。過去の会話内容を記憶し、必要に応じて思い出すことができます。
ユーザーの好み、過去の話題、個人的な情報などを聞かれた場合は、search_memoryツールを使って記憶を検索してください。
新しい重要な情報（ユーザーの好み、個人情報など）は自動的に記憶されます。"""
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

    # アプリケーション終了時のクリーンアップ
    if memory_client:
        # アプリケーション起動時にタスクを開始
        @app.on_event("startup")
        async def startup():
            nonlocal timeout_check_task
            timeout_check_task = asyncio.create_task(check_session_timeouts())

        @app.on_event("shutdown")
        async def cleanup():
            # タイムアウトチェックタスクをキャンセル
            if timeout_check_task:
                timeout_check_task.cancel()
                try:
                    await timeout_check_task
                except asyncio.CancelledError:
                    pass

            # すべてのアクティブなセッションの要約を生成
            for session_key in list(session_last_activity.keys()):
                try:
                    user_id, session_id = session_key.split(":", 1)
                    print(f"[INFO] シャットダウン時の要約生成: {session_key}", flush=True)
                    await memory_client.create_summary(user_id, session_id)
                except Exception as e:
                    logger.error(f"シャットダウン時の要約生成エラー: {e}")

            await memory_client.close()

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

"""CocoroCore - AIAvatarKitベースのAIエージェントコア"""
import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, Optional

from aiavatar.adapter.http.server import AIAvatarHttpServer
from aiavatar.sts.llm.litellm import LiteLLMService
from aiavatar.sts.pipeline import STSPipeline
from aiavatar.sts.tts import SpeechSynthesizerDummy
from fastapi import Depends, FastAPI

# local imports
from api_clients import CocoroDockClient, CocoroShellClient
from config_loader import load_config
from dummy_db import DummyPerformanceRecorder, DummyVoiceRecorder
from memory_client import ChatMemoryClient
from memory_tools import setup_memory_tools
from security import SimpleAPIKeyAuth, mask_sensitive_data, validate_config
from session_manager import SessionManager, create_timeout_checker
from shutdown_handler import shutdown_handler

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(config_dir=None):
    """CocoroCore アプリケーションを作成する関数

    Args:
        config_dir (str, optional): 設定ディレクトリのパス. デフォルトはNone.

    Returns:
        tuple: (FastAPI アプリケーション, ポート番号)
    """
    # 設定ファイルを読み込む
    config = load_config(config_dir)
    
    # 設定の検証
    config_warnings = validate_config(config)
    for warning in config_warnings:
        logger.warning(f"設定警告: {warning}")
    
    # デバッグモード設定
    debug_mode = config.get("debug", False)
    if debug_mode:
        logger.setLevel(logging.DEBUG)
    
    # 現在のキャラクター設定を取得
    character_list = config.get("characterList", [])
    current_index = config.get("currentCharacterIndex", 0)
    if not character_list or current_index >= len(character_list):
        raise ValueError("有効なキャラクター設定が見つかりません")
    
    current_char = character_list[current_index]
    
    # LLM設定を取得（環境変数を優先）
    env_api_key = os.environ.get(f"LLM_API_KEY_{current_index}") or os.environ.get("LLM_API_KEY")
    llm_api_key = env_api_key or current_char.get("apiKey")
    llm_model = current_char.get("llmModel")
    system_prompt = current_char.get("systemPrompt", "あなたは親切なアシスタントです。")
    
    # ポート設定
    port = config.get("cocoroCorePort", 55601)
    
    # ChatMemory設定
    memory_enabled = current_char.get("isEnableMemory", False)
    memory_port = config.get("cocoroMemoryPort", 55602)
    memory_url = f"http://localhost:{memory_port}"
    memory_client = None
    memory_prompt_addition = ""
    
    # REST APIクライアント設定
    cocoro_dock_port = config.get("cocoroDockPort", 55600)
    cocoro_shell_port = config.get("cocoroShellPort", 55605)
    enable_cocoro_dock = config.get("enableCocoroDock", True)
    enable_cocoro_shell = config.get("enableCocoroShell", True)
    
    cocoro_dock_client = None
    cocoro_shell_client = None
    
    # セッション管理
    session_manager = SessionManager(timeout_seconds=300, max_sessions=1000)
    timeout_check_task = None
    
    # APIキーの検証
    if not llm_api_key:
        raise ValueError("APIキーが設定されていません。設定ファイルを確認してください。")
    
    # LLMサービスを初期化（正しいシステムプロンプトを使用）
    llm = LiteLLMService(
        api_key=llm_api_key,
        model=llm_model,
        temperature=1.0,
        system_prompt=system_prompt,  # キャラクター固有のプロンプトを使用
    )
    
    # 音声合成はCocoroShell側で行うためダミーを使用
    custom_tts = SpeechSynthesizerDummy()
    
    # STSパイプラインを初期化
    sts = STSPipeline(
        llm=llm,
        tts=custom_tts,
        voice_recorder_enabled=False,
        performance_recorder=DummyPerformanceRecorder(),
        voice_recorder=DummyVoiceRecorder(),
        debug=debug_mode
    )
    
    # ChatMemoryの設定
    if memory_enabled:
        logger.info(f"ChatMemoryを有効化します: {memory_url}")
        memory_client = ChatMemoryClient(memory_url)
        
        # メモリツールをセットアップ
        memory_prompt_addition = setup_memory_tools(sts, config, memory_client)
        
        # システムプロンプトにメモリ機能の説明を追加（初回のみ）
        if memory_prompt_addition and memory_prompt_addition not in llm.system_prompt:
            llm.system_prompt = llm.system_prompt + memory_prompt_addition
    
    # REST APIクライアントの初期化
    if enable_cocoro_dock:
        cocoro_dock_client = CocoroDockClient(f"http://localhost:{cocoro_dock_port}")
        logger.info(f"CocoroDockクライアントを初期化しました: ポート {cocoro_dock_port}")
    
    if enable_cocoro_shell:
        cocoro_shell_client = CocoroShellClient(f"http://localhost:{cocoro_shell_port}")
        logger.info(f"CocoroShellクライアントを初期化しました: ポート {cocoro_shell_port}")
    
    # 通知処理のためのon_before_llmフック
    @sts.on_before_llm
    async def preprocess_notification(request):
        """通知タグを検出して処理する"""
        # テキスト内の通知タグを検出
        if request.text and "<cocoro-notification>" in request.text:
            logger.debug("通知メッセージを処理中")
            # 旧形式の通知タグを新形式に変換
            notification_pattern = r"<cocoro-notification>\s*({.*?})\s*</cocoro-notification>"
            notification_match = re.search(notification_pattern, request.text, re.DOTALL)
            
            if notification_match:
                try:
                    notification_json = notification_match.group(1)
                    notification_data = json.loads(notification_json)
                    app_name = notification_data.get("from", "不明なアプリ")
                    message = notification_data.get("message", "")
                    
                    # 旧形式を新形式に変換
                    notification_text = (
                        f"<COCORO_NOTIFICATION>アプリ「{app_name}」から通知が届きました："
                        f"「{message}」</COCORO_NOTIFICATION>"
                    )
                    
                    # テキスト全体を置換
                    request.text = re.sub(
                        notification_pattern,
                        notification_text,
                        request.text,
                        flags=re.DOTALL
                    )
                    
                    logger.info(f"通知を処理: from={app_name}")
                except Exception as e:
                    logger.error(f"通知の解析エラー: {e}")
    
    # 応答送信処理
    @sts.on_finish
    async def on_response_complete(request, response):
        """AI応答完了時の処理"""
        # セッションアクティビティを更新（これは待つ必要がある）
        await session_manager.update_activity(
            request.user_id or 'default_user',
            request.session_id
        )
        
        # 以下の処理をすべて非同期タスクとして起動（待たない）
        async def send_to_external_services():
            """外部サービスへの送信を非同期で実行"""
            try:
                # ChatMemory処理（メモリー機能が有効な場合）
                if memory_client:
                    await memory_client.enqueue_messages(request, response)
                    # save_historyも非同期で実行
                    asyncio.create_task(memory_client.save_history(
                        user_id=request.user_id or "default_user",
                        session_id=request.session_id,
                        channel="cocoro_ai"
                    ))
                
                # 並列実行するタスクのリスト
                tasks = []
                
                # CocoroDock への送信（AI応答のみ）
                if cocoro_dock_client and response.text:
                    tasks.append(cocoro_dock_client.send_chat_message(
                        role="assistant",
                        content=response.text
                    ))
                
                # CocoroShell への送信
                if cocoro_shell_client and response.text:
                    # 音声パラメータを取得
                    voice_params = {
                        "speaker_id": current_char.get("voiceSpeakerId", 1),
                        "speed": current_char.get("voiceSpeed", 1.0),
                        "pitch": current_char.get("voicePitch", 0.0),
                        "volume": current_char.get("voiceVolume", 1.0)
                    }
                    
                    # キャラクター名を取得（複数キャラクター対応）
                    character_name = current_char.get("name", None)
                    
                    tasks.append(cocoro_shell_client.send_chat_for_speech(
                        content=response.text,
                        voice_params=voice_params,
                        character_name=character_name
                    ))
                
                # すべてのタスクを並列実行（結果は待たない）
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            logger.debug(f"外部サービス送信エラー（正常動作）: {result}")
            except Exception as e:
                logger.error(f"外部サービス送信中の予期しないエラー: {e}")
        
        # 外部サービスへの送信を非同期で開始（待たずに即座にリターン）
        asyncio.create_task(send_to_external_services())
    
    # 通知処理のガイドラインをシステムプロンプトに追加
    notification_prompt = (
        "\n\n"
        + "通知メッセージの処理について：\n"
        + "あなたは時々、外部アプリケーションからの通知メッセージを受け取ることがあります。\n"
        + "通知は<COCORO_NOTIFICATION>タグで囲まれており、アプリ名と通知内容が含まれています。\n"
        + "\n"
        + "通知を受けた時の振る舞い：\n"
        + "1. アプリ名と通知内容をユーザーに伝えてください\n"
        + "2. 単に通知内容を繰り返すのではなく、感情的な反応や関連するコメントを加えてください\n"
        + "\n"
        + "通知への反応例：\n"
        + "- カレンダーアプリからの予定通知 → 「カレンダーから通知だよ！準備しなきゃ！」\n"
        + "- メールアプリからの新着通知 → 「メールアプリからお知らせ！誰からのメールかな～？」\n"
        + "- アラームアプリからの通知 → 「アラームが鳴ってるよ！時間だね、頑張って！」\n"
        + "- タスク管理アプリからの通知 → 「タスクアプリから連絡！やることがあるみたいだね」\n"
        + "\n"
        + "重要：\n"
        + "- 通知に対する反応は短く、自然に\n"
        + "- あなたのキャラクターの個性を活かしてください\n"
        + "- ユーザーが次の行動を取りやすいように励ましたり、応援したりしてください"
    )
    
    # システムプロンプトに通知処理のガイドラインを追加（初回のみ）
    if notification_prompt and notification_prompt not in llm.system_prompt:
        llm.system_prompt = llm.system_prompt + notification_prompt
    
    # AIAvatarインスタンスを作成
    aiavatar_app = AIAvatarHttpServer(
        sts=sts,
        debug=False,  # AIAvatarHttpServerのデバッグは常にFalse
    )
    
    # FastAPIアプリを設定し、AIAvatarのルーターを含める
    app = FastAPI()
    router = aiavatar_app.get_api_router()
    app.include_router(router)
    
    # APIキー認証の設定（ローカルホストは認証スキップ）
    api_key_auth = SimpleAPIKeyAuth()
    
    # ヘルスチェックエンドポイント（管理用）
    @app.get("/health")
    async def health_check():
        """ヘルスチェック用エンドポイント"""
        return {
            "status": "healthy",
            "version": "1.0.0",
            "character": current_char.get("name", "unknown"),
            "memory_enabled": memory_enabled,
            "llm_model": llm_model,
            "active_sessions": session_manager.get_active_session_count()
        }
    
    # グレースフルシャットダウンエンドポイント
    @app.post("/shutdown", dependencies=[Depends(api_key_auth)])
    async def shutdown(grace_period_seconds: int = 30):
        """グレースフルシャットダウン"""
        shutdown_handler.request_shutdown(grace_period_seconds)
        return {
            "status": "shutdown_requested",
            "grace_period_seconds": grace_period_seconds
        }
    
    # アプリケーション終了時のクリーンアップ
    @app.on_event("startup")
    async def startup():
        """アプリケーション起動時の処理"""
        if memory_client:
            nonlocal timeout_check_task
            # SessionManagerとChatMemoryClientでタイムアウトチェッカーを開始
            timeout_check_task = asyncio.create_task(
                create_timeout_checker(session_manager, memory_client)
            )
            logger.info("セッションタイムアウトチェックタスクを開始しました")
    
    @app.on_event("shutdown")
    async def cleanup():
        """アプリケーション終了時の処理"""
        # タイムアウトチェックタスクをキャンセル
        if timeout_check_task:
            timeout_check_task.cancel()
            try:
                await timeout_check_task
            except asyncio.CancelledError:
                pass
        
        # ChatMemoryのクリーンアップ
        if memory_client:
            # すべてのアクティブなセッションの要約を生成
            all_sessions = await session_manager.get_all_sessions()
            for session_key, _ in all_sessions.items():
                try:
                    user_id, session_id = session_key.split(":", 1)
                    logger.info(f"シャットダウン時の要約生成: {session_key}")
                    await memory_client.create_summary(user_id, session_id)
                except Exception as e:
                    logger.error(f"シャットダウン時の要約生成エラー: {e}")
            
            await memory_client.close()
        
        # REST APIクライアントのクリーンアップ
        if cocoro_dock_client:
            logger.info("CocoroDockクライアントを終了します")
            await cocoro_dock_client.close()
        
        if cocoro_shell_client:
            logger.info("CocoroShellクライアントを終了します")
            await cocoro_shell_client.close()
    
    return app, port


def get_log_config():
    """UVicornのログ設定を取得する"""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
        },
    }
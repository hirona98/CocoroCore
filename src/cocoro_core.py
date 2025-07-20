"""CocoroCore - AIAvatarKitベースのAIエージェントコア"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from aiavatar.adapter.http.server import AIAvatarHttpServer
from aiavatar.device.audio import AudioDevice, AudioRecorder
from aiavatar.sts.pipeline import STSPipeline
from aiavatar.sts.tts import SpeechSynthesizerDummy
from aiavatar.sts.voice_recorder.file import FileVoiceRecorder
from fastapi import Depends, FastAPI

# local imports
from api_clients import CocoroDockClient, CocoroShellClient
from app_initializer import (
    initialize_config,
    initialize_dock_log_handler,
    setup_debug_mode,
    get_character_config,
    extract_llm_config,
    extract_port_config,
    extract_stt_config,
)
from client_initializer import (
    initialize_memory_client,
    initialize_api_clients,
    initialize_llm_manager,
    initialize_session_manager,
)
from config_loader import load_config
from config_validator import validate_config
from dummy_db import DummyPerformanceRecorder, DummyVoiceRecorder
from endpoints import setup_endpoints
from hook_processor import RequestHookProcessor
from image_processor import parse_image_response, generate_image_description
from llm_manager import LLMStatusManager, create_llm_service
from mcp_tools import (
    get_mcp_status,
    initialize_mcp_if_pending,
    setup_mcp_tools,
    shutdown_mcp_system,
)
from memory_client import ChatMemoryClient
from memory_tools import setup_memory_tools
from session_manager import SessionManager, create_timeout_checker
from shutdown_handler import shutdown_handler
from stt_manager import create_stt_service
from time_utils import generate_current_time_info, create_time_guidelines
from prompt_utils import add_system_prompts
from response_processor import ResponseProcessor
from voice_processor import process_mic_input
from vad_manager import SmartVoiceDetector, VADEventHandler

# Ollama画像サポートパッチを適用
try:
    import sys

    patches_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "patches"
    )
    sys.path.insert(0, patches_dir)
    from ollama_chat_image_patch import patch_ollama_chat_transform

    patch_ollama_chat_transform()
except Exception as e:
    logging.warning(f"Ollama画像サポートパッチの適用をスキップ: {e}")

# ログ設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# CocoroDock用ログハンドラーの初期化（グローバル変数として宣言のみ）
dock_log_handler = None






def create_app(config_dir=None):
    """CocoroCore アプリケーションを作成する関数

    Args:
        config_dir (str, optional): 設定ディレクトリのパス. デフォルトはNone.

    Returns:
        tuple: (FastAPI アプリケーション, ポート番号)
    """
    # 設定の初期化
    config = initialize_config(config_dir)
    
    # CocoroDock用ログハンドラーの初期化
    global dock_log_handler
    dock_log_handler = initialize_dock_log_handler(config)
    
    # デバッグモードの設定
    debug_mode = setup_debug_mode(config)
    
    # キャラクター設定の取得
    character_list = config.get("characterList", [])
    current_index = config.get("currentCharacterIndex", 0)
    current_char = get_character_config(config)
    
    # LLM設定の抽出
    llm_api_key, llm_model, system_prompt, user_id = extract_llm_config(config, current_char, current_index)
    
    # ポート設定の取得
    port = extract_port_config(config)
    
    # STT設定の抽出
    (is_use_stt, stt_engine, stt_wake_word, stt_api_key, stt_language,
     vad_auto_adjustment, vad_threshold) = extract_stt_config(current_char, config)
    
    # クライアント初期化
    memory_client, memory_enabled, memory_prompt_addition = initialize_memory_client(current_char, config)
    cocoro_dock_client, cocoro_shell_client = initialize_api_clients(config)
    session_manager = initialize_session_manager()
    llm_status_manager = initialize_llm_manager(cocoro_dock_client)
    
    # 音声とテキストで共有するcontext_id
    shared_context_id = None
    timeout_check_task = None

    # shared_context_idのプロバイダー関数を定義
    def get_shared_context_id():
        return shared_context_id

    # LLMサービスを初期化
    llm = create_llm_service(
        api_key=llm_api_key,
        model=llm_model,
        system_prompt=system_prompt,
        context_provider=get_shared_context_id,
        temperature=1.0,
    )

    # 音声合成はCocoroShell側で行うためダミーを使用
    custom_tts = SpeechSynthesizerDummy()

    # STTインスタンスの初期化（APIキーがあれば常に作成）
    stt_instance = None
    voice_recorder_instance = None
    voice_recorder_enabled = False
    wakewords = None
    vad_instance = None

    # STTサービスを作成
    stt_instance = create_stt_service(
        engine=stt_engine,
        api_key=stt_api_key,
        language=stt_language,
        dock_client=cocoro_dock_client,
        debug=debug_mode,
    )

    if stt_instance:
        # デバッグモード時のみ音声記録を有効化
        if debug_mode:
            voice_recorder_enabled = True
            # 音声記録用ディレクトリの作成
            voice_record_dir = "./voice_records"
            os.makedirs(voice_record_dir, exist_ok=True)

            voice_recorder_instance = FileVoiceRecorder(record_dir=voice_record_dir)
            logger.info("デバッグモード: 音声記録を有効化しました")
        else:
            voice_recorder_enabled = False
            voice_recorder_instance = DummyVoiceRecorder()

        # VAD（音声アクティビティ検出）の設定（常に作成）
        # shared_context_idのプロバイダー関数を定義
        def get_shared_context_id():
            return shared_context_id

        vad_instance = SmartVoiceDetector(
            context_provider=get_shared_context_id,
            dock_client=cocoro_dock_client,
            auto_adjustment=vad_auto_adjustment,  # 設定ファイルから読み込み
            fixed_threshold=vad_threshold,  # 設定ファイルから読み込み
            # volume_db_thresholdは自動設定されるため指定しない
            silence_duration_threshold=0.5,  # 無音継続時間閾値（秒）
            max_duration=10.0,  # 最大録音時間を10秒に設定
            sample_rate=16000,
            debug=debug_mode,
        )

        # 定期調整タスクはアプリ起動後に開始（startup_eventで実行）

        # ウェイクワードの設定（カンマ区切りで複数対応）
        if stt_wake_word:
            # カンマ区切りで分割して空でない項目のみを取得
            wakewords = [word.strip() for word in stt_wake_word.split(',') if word.strip()]
            logger.info(f"ウェイクワードを設定: {wakewords}")

        # is_use_sttの状態をログ出力
        if is_use_stt:
            logger.info("STT機能は有効状態で初期化されました")
        else:
            logger.info("STT機能は無効状態で初期化されました（APIで動的に有効化可能）")
    else:
        voice_recorder_instance = DummyVoiceRecorder()

    # STSパイプラインを初期化
    sts = STSPipeline(
        llm=llm,
        tts=custom_tts,
        stt=stt_instance,
        vad=vad_instance,  # VADインスタンスを追加
        voice_recorder_enabled=voice_recorder_enabled,
        voice_recorder=voice_recorder_instance,
        wakewords=wakewords,
        wakeword_timeout=60.0,  # ウェイクワードタイムアウト（秒）
        performance_recorder=DummyPerformanceRecorder(),
        debug=debug_mode,
    )

    # process_requestメソッドをオーバーライドして、音声入力時のcontext_id処理を追加
    if hasattr(sts, "process_request"):
        original_process_request = sts.process_request

        async def custom_process_request(request):
            """音声入力時に共有context_idを適用するカスタムメソッド"""
            nonlocal shared_context_id

            # 音声入力かつ共有context_idがある場合
            if shared_context_id:
                # SimpleNamespaceオブジェクトの場合
                if hasattr(request, "__dict__"):
                    if hasattr(request, "audio_data") and request.audio_data is not None:
                        if not getattr(request, "context_id", None):
                            request.context_id = shared_context_id
                            logger.info(
                                f"音声入力リクエストに共有context_idを設定: {shared_context_id}"
                            )
                # 辞書型の場合
                elif isinstance(request, dict):
                    if request.get("audio_data") is not None:
                        if not request.get("context_id"):
                            request["context_id"] = shared_context_id
                            logger.info(
                                f"音声入力リクエスト(dict)に共有context_idを設定: "
                                f"{shared_context_id}"
                            )

            # 元のメソッドを呼び出し
            return await original_process_request(request)

        # メソッドを置き換え
        sts.process_request = custom_process_request
    else:
        logger.warning("STSPipelineにprocess_requestメソッドが見つかりません")

    # is_awakeメソッドをオーバーライドして、テキストチャットの場合は常にTrueを返す
    original_is_awake = sts.is_awake

    def custom_is_awake(request, last_request_at):
        # 共有context_idがある場合は、既に会話が開始されているのでウェイクワード不要
        if shared_context_id:
            logger.debug(f"既存の会話コンテキストあり（{shared_context_id}）、ウェイクワード不要")
            return True

        # audio_dataの有無でテキストチャットか判定
        # テキストチャットの場合はaudio_dataがNoneまたは存在しない
        is_text_chat = False
        if hasattr(request, "audio_data"):
            if request.audio_data is None:
                is_text_chat = True
        else:
            # audio_data属性自体がない場合もテキストチャット
            is_text_chat = True

        if is_text_chat:
            logger.debug("テキストチャットのため、ウェイクワード検出済みとして処理")
            return True

        # それ以外（音声入力）は元の処理を実行
        return original_is_awake(request, last_request_at)

    sts.is_awake = custom_is_awake

    # フック処理クラスの初期化
    request_hook_processor = RequestHookProcessor(
        config=config,
        llm=llm,
        user_id=user_id,
        llm_status_manager=llm_status_manager,
        cocoro_dock_client=cocoro_dock_client,
        cocoro_shell_client=cocoro_shell_client,
        wakewords=wakewords,
    )

    response_processor = ResponseProcessor(
        user_id=user_id,
        llm_status_manager=llm_status_manager,
        session_manager=session_manager,
        memory_client=memory_client,
        cocoro_dock_client=cocoro_dock_client,
        cocoro_shell_client=cocoro_shell_client,
        current_char=current_char,
        vad_instance=vad_instance,
    )

    # on_before_llmフック（音声認識の有無に関わらず統一）
    @sts.on_before_llm
    async def handle_before_llm(request):
        nonlocal shared_context_id
        await request_hook_processor.process_before_llm(request, shared_context_id)

    # ChatMemoryの設定
    if memory_enabled:
        logger.info(f"ChatMemoryを有効化します: {memory_url}")
        memory_client = ChatMemoryClient(memory_url)

        # メモリツールをセットアップ
        memory_prompt_addition = setup_memory_tools(
            sts, config, memory_client, session_manager, cocoro_dock_client
        )

        # システムプロンプトにメモリ機能の説明を追加（初回のみ）
        if memory_prompt_addition and memory_prompt_addition not in llm.system_prompt:
            llm.system_prompt = llm.system_prompt + memory_prompt_addition

    # MCPツールをセットアップ（isEnableMcpがTrueの場合のみ）
    if config.get("isEnableMcp", False):
        logger.info("MCPツールを初期化します")
        mcp_prompt_addition = setup_mcp_tools(sts, config, cocoro_dock_client)
        if mcp_prompt_addition:
            llm.system_prompt = llm.system_prompt + mcp_prompt_addition
            logger.info("MCPツールの説明をシステムプロンプトに追加しました")
    else:
        logger.info("MCPツールは無効になっています")
    
    # MCPシステムのクリーンアップタスクを登録
    shutdown_handler.register_cleanup_task(shutdown_mcp_system, "MCP System")

    # REST APIクライアントの初期化
    if enable_cocoro_shell:
        cocoro_shell_client = CocoroShellClient(f"http://127.0.0.1:{cocoro_shell_port}")
        logger.info(f"CocoroShellクライアントを初期化しました: ポート {cocoro_shell_port}")

    # 応答送信処理
    @sts.on_finish
    async def on_response_complete(request, response):
        """AI応答完了時の処理"""
        nonlocal shared_context_id
        
        def set_shared_context_id(context_id):
            nonlocal shared_context_id
            shared_context_id = context_id
        
        await response_processor.process_response_complete(request, response, set_shared_context_id)
        

    # システムプロンプトにガイドラインを追加
    add_system_prompts(llm, logger)

    # AIAvatarインスタンスを作成
    aiavatar_app = AIAvatarHttpServer(
        sts=sts,
        debug=False,  # AIAvatarHttpServerのデバッグは常にFalse
    )

    # STSパイプラインのinvokeメソッドをラップ
    original_invoke = sts.invoke

    async def wrapped_invoke(request):
        nonlocal shared_context_id

        # テキストリクエストで共有context_idがある場合
        if shared_context_id and hasattr(request, "text") and request.text:
            # context_idが未設定の場合は共有context_idを設定
            if not getattr(request, "context_id", None):
                request.context_id = shared_context_id
                logger.info(f"STSリクエストに共有context_idを設定: {shared_context_id}")

        # 元のinvokeを呼び出し
        async for chunk in original_invoke(request):
            yield chunk

    # メソッドを置き換え
    sts.invoke = wrapped_invoke

    # FastAPIアプリを設定し、AIAvatarのルーターを含める
    app = FastAPI()
    router = aiavatar_app.get_api_router()
    app.include_router(router)

    # アプリケーション起動時イベント：VAD定期調整タスクを開始
    @app.on_event("startup")
    async def startup_event():
        if (
            vad_instance
            and hasattr(vad_instance, "start_periodic_adjustment_task")
            and vad_auto_adjustment
        ):
            asyncio.create_task(vad_instance.start_periodic_adjustment_task())
            logger.info("🔄 VAD定期調整タスクを開始しました")
        elif vad_instance and not vad_auto_adjustment:
            logger.info("🔧 VAD自動調整無効のため、定期調整タスクはスキップしました")
        
        # MCP初期化が保留中の場合は実行
        await initialize_mcp_if_pending()

    # STSパイプラインの_process_text_requestメソッドをオーバーライド
    if hasattr(sts, "_process_text_request"):
        original_process_text_request = sts._process_text_request

        async def custom_process_text_request(request):
            """テキストリクエスト処理時に共有context_idを適用"""
            nonlocal shared_context_id

            # 共有context_idがあり、リクエストにcontext_idがない場合は設定
            if shared_context_id and not getattr(request, "context_id", None):
                if hasattr(request, "__dict__"):
                    request.context_id = shared_context_id
                    logger.info(f"テキストリクエストに共有context_idを設定: {shared_context_id}")
                elif isinstance(request, dict) and not request.get("context_id"):
                    request["context_id"] = shared_context_id
                    logger.info(
                        f"テキストリクエスト(dict)に共有context_idを設定: {shared_context_id}"
                    )

            # 元のメソッドを呼び出し
            return await original_process_text_request(request)

        sts._process_text_request = custom_process_text_request
        logger.info("STSパイプラインの_process_text_requestメソッドをオーバーライドしました")

    # マイク入力タスクの管理
    mic_input_task = None

    # 共有context_idのプロバイダー関数
    def get_shared_context_id():
        return shared_context_id

    # エンドポイント依存関係のコンテナ（可変参照用）
    class DepsContainer:
        def __init__(self):
            self.mic_input_task = mic_input_task
            self.is_use_stt = is_use_stt

    deps_container = DepsContainer()

    # エンドポイントの設定
    deps = {
        "config": config,
        "current_char": current_char,
        "memory_enabled": memory_enabled,
        "llm_model": llm_model,
        "session_manager": session_manager,
        "dock_log_handler": dock_log_handler,
        "is_use_stt": is_use_stt,
        "stt_api_key": stt_api_key,
        "vad_instance": vad_instance,
        "user_id": user_id,
        "get_shared_context_id": get_shared_context_id,
        "cocoro_dock_client": cocoro_dock_client,
        "mic_input_task": mic_input_task,
        "shutdown_handler": shutdown_handler,
        "deps_container": deps_container,
    }
    setup_endpoints(app, deps)

    # アプリケーション終了時のクリーンアップ
    @app.on_event("startup")
    async def startup():
        """アプリケーション起動時の処理"""
        if memory_client:
            nonlocal timeout_check_task
            nonlocal shared_context_id

            # SessionManagerとChatMemoryClientでタイムアウトチェッカーを開始
            async def timeout_checker_with_context_clear():
                """タイムアウトチェッカーにcontext_idクリア機能を追加"""
                nonlocal shared_context_id
                checker = create_timeout_checker(session_manager, memory_client)
                while True:
                    await checker
                    # セッションタイムアウト時に共有context_idもクリア
                    active_sessions = await session_manager.get_all_sessions()
                    if not active_sessions and shared_context_id:
                        logger.info(
                            f"全セッションタイムアウトにより共有context_idをクリア: {shared_context_id}"
                        )
                        shared_context_id = None

            timeout_check_task = asyncio.create_task(timeout_checker_with_context_clear())
            logger.info("セッションタイムアウトチェックタスクを開始しました")

        # マイク入力の開始（STTが有効かつインスタンスが作成されている場合）
        if deps_container.is_use_stt and stt_api_key and vad_instance:
            deps_container.mic_input_task = asyncio.create_task(
                process_mic_input(vad_instance, user_id, get_shared_context_id, cocoro_dock_client)
            )
            logger.info("起動時にSTTが有効のため、マイク入力を開始しました")
        elif stt_api_key and vad_instance:
            logger.info("STTインスタンスは準備済み、APIコマンドで有効化可能です")

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

        # 残っているLLMステータス送信タスクをすべてキャンセル
        for request_id, task in list(llm_status_manager.active_requests.items()):
            llm_status_manager.stop_periodic_status(request_id)
        logger.info("すべてのLLMステータス送信タスクを停止しました")

        # REST APIクライアントのクリーンアップ
        if cocoro_dock_client:
            logger.info("CocoroDockクライアントを終了します")
            await cocoro_dock_client.close()

        if cocoro_shell_client:
            logger.info("CocoroShellクライアントを終了します")
            await cocoro_shell_client.close()

        # STT（音声認識）のクリーンアップ
        if stt_instance:
            logger.info("音声認識クライアントを終了します")
            await stt_instance.close()

        # マイク入力タスクのキャンセル
        if deps_container.mic_input_task:
            logger.info("マイク入力タスクを停止します")
            deps_container.mic_input_task.cancel()
            try:
                await deps_container.mic_input_task
            except asyncio.CancelledError:
                pass

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

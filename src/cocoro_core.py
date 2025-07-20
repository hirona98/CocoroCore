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
from event_handlers import AppEventHandlers
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
from sts_configurator import STSConfigurator
from tools_configurator import ToolsConfigurator
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

    # STT/VAD/音声記録の初期化
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

    # STSパイプラインの設定
    sts_configurator = STSConfigurator()
    sts = sts_configurator.create_pipeline(
        llm=llm,
        stt_instance=stt_instance,
        vad_instance=vad_instance,
        voice_recorder_enabled=voice_recorder_enabled,
        voice_recorder_instance=voice_recorder_instance,
        wakewords=wakewords,
        debug_mode=debug_mode,
    )

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

    # ツール設定の初期化
    tools_configurator = ToolsConfigurator()
    
    # ChatMemoryツールの設定
    memory_prompt_addition = tools_configurator.setup_memory_tools(
        sts, config, memory_client, session_manager, cocoro_dock_client, llm, memory_enabled
    )
    
    # MCPツールの設定
    mcp_prompt_addition = tools_configurator.setup_mcp_tools(
        sts, config, cocoro_dock_client, llm
    )
    
    # クリーンアップタスクの登録
    tools_configurator.register_cleanup_tasks(shutdown_handler)

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

    # STSパイプラインの追加設定
    sts_configurator.setup_invoke_wrapper(sts)
    sts_configurator.setup_text_request_override(sts)
    
    # 共有context_idの更新機能を設定
    def update_shared_context_id():
        sts_configurator.set_shared_context_id(sts, shared_context_id)
    
    # 初期設定
    update_shared_context_id()

    # FastAPIアプリを設定し、AIAvatarのルーターを含める
    app = FastAPI()
    router = aiavatar_app.get_api_router()
    app.include_router(router)

    # イベントハンドラーの設定
    event_handlers = AppEventHandlers(
        memory_client=memory_client,
        session_manager=session_manager,
        deps_container=deps_container,
        vad_instance=vad_instance,
        vad_auto_adjustment=vad_auto_adjustment,
        stt_api_key=stt_api_key,
        user_id=user_id,
        get_shared_context_id=get_shared_context_id,
        cocoro_dock_client=cocoro_dock_client,
    )
    
    # VAD用startup イベント
    startup_vad_handler = event_handlers.create_vad_startup_handler()
    app.on_event("startup")(startup_vad_handler)

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

    # メイン startup ハンドラー
    startup_handler = event_handlers.create_startup_handler()
    app.on_event("startup")(startup_handler)
    
    # shutdown ハンドラー
    shutdown_handler_func = event_handlers.create_shutdown_handler(
        llm_status_manager, cocoro_dock_client, cocoro_shell_client, stt_instance
    )
    app.on_event("shutdown")(shutdown_handler_func)

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

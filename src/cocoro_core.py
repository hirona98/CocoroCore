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

    # on_before_llmフック（音声認識の有無に関わらず統一）
    @sts.on_before_llm
    async def handle_before_llm(request):
        nonlocal shared_context_id

        # 現在時刻情報を動的に更新
        current_time_info = generate_current_time_info()

        # システムプロンプトに現在時刻を動的に追加
        # 前回の時刻情報があれば削除してから新しい情報を追加
        original_prompt = llm.system_prompt
        time_marker = "現在の日時:"

        # 既存の時刻情報を削除
        if time_marker in original_prompt:
            lines = original_prompt.split("\n")
            filtered_lines = [line for line in lines if not line.strip().startswith(time_marker)]
            llm.system_prompt = "\n".join(filtered_lines)

        # 新しい時刻情報を追加
        llm.system_prompt = llm.system_prompt + f"\n\n{current_time_info}\n"

        logger.debug(f"時刻情報を更新: {current_time_info}")

        # user_idを設定ファイルから読み込んだ値に上書き
        if hasattr(request, 'user_id') and user_id:
            original_user_id = request.user_id
            request.user_id = user_id
            logger.info(f"user_idを設定値に変更: {original_user_id} → {user_id}")

        # 音声入力でcontext_idが未設定の場合、共有context_idを設定
        if shared_context_id:
            # テキストチャットか音声入力かを判定
            is_voice_input = hasattr(request, "audio_data") and request.audio_data is not None

            if is_voice_input and not getattr(request, "context_id", None):
                # requestオブジェクトが読み取り専用の場合があるため、
                # 新しい属性として設定を試みる
                try:
                    request.context_id = shared_context_id
                    logger.info(f"音声入力に共有context_idを設定: {shared_context_id}")
                except AttributeError:
                    # 読み取り専用の場合は、別の方法で設定
                    logger.warning(
                        f"requestオブジェクトは読み取り専用です。context_id: "
                        f"{shared_context_id}を別の方法で設定します"
                    )
                    # STSパイプラインにcontext_idを直接設定する試み
                    if hasattr(sts, "context_id"):
                        sts.context_id = shared_context_id
                        logger.info(f"STSパイプラインにcontext_idを直接設定: {shared_context_id}")

        # リクエストの詳細情報をログ出力
        logger.debug(f"[on_before_llm] request.text: '{request.text}'")
        logger.debug(f"[on_before_llm] request.session_id: {request.session_id}")
        logger.debug(f"[on_before_llm] request.user_id: {request.user_id}")
        logger.debug(
            f"[on_before_llm] request.context_id: {getattr(request, 'context_id', 'なし')}"
        )
        logger.debug(f"[on_before_llm] request.metadata: {getattr(request, 'metadata', {})}")
        logger.debug(
            f"[on_before_llm] has audio_data: {hasattr(request, 'audio_data')} "
            f"(is None: {getattr(request, 'audio_data', None) is None})"
        )

        # リクエストオブジェクトの全属性をデバッグ出力
        logger.debug(f"[on_before_llm] request type: {type(request)}")
        logger.debug(
            f"[on_before_llm] request dir: "
            f"{[attr for attr in dir(request) if not attr.startswith('_')]}"
        )
        if hasattr(request, "__dict__"):
            # audio_dataを除外して表示
            filtered_dict = {k: v for k, v in request.__dict__.items() if k != "audio_data"}
            logger.debug(f"[on_before_llm] request.__dict__: {filtered_dict}")
            if "audio_data" in request.__dict__:
                logger.debug(
                    f"[on_before_llm] audio_data: <{len(request.audio_data) if request.audio_data else 0} bytes>"
                )

        # 音声認識結果のCocoroDockへの送信とログ出力
        if request.text:
            # テキストチャットか音声認識かを判定
            # audio_dataの有無で判定（音声認識の場合はaudio_dataがある）
            is_text_chat = False
            if hasattr(request, "audio_data"):
                # audio_dataがNoneまたは存在しない場合はテキストチャット
                if request.audio_data is None:
                    is_text_chat = True
            else:
                # audio_data属性自体がない場合もテキストチャット
                is_text_chat = True

            if is_text_chat:
                logger.info(
                    f"💬 テキストチャット受信: '{request.text}' "
                    f"(session_id: {request.session_id}, user_id: {request.user_id})"
                )
            else:
                # 音声認識の場合
                logger.info(
                    f"🎤 音声認識結果: '{request.text}' "
                    f"(session_id: {request.session_id}, user_id: {request.user_id})"
                )
                # 音声認識したテキストをCocoroDockに送信（非同期）
                if cocoro_dock_client:
                    asyncio.create_task(
                        cocoro_dock_client.send_chat_message(role="user", content=request.text)
                    )
                    logger.debug(f"音声認識テキストをCocoroDockに送信: '{request.text}'")
            
            # メッセージ受信時に正面を向く処理
            if cocoro_shell_client:
                asyncio.create_task(
                    cocoro_shell_client.send_control_command(command="lookForward")
                )
                logger.debug("正面を向くコマンドをCocoroShellに送信")

            if wakewords:
                for wakeword in wakewords:
                    if wakeword.lower() in request.text.lower():
                        # ウェイクワード検出ステータス送信（非同期）
                        if cocoro_dock_client:
                            asyncio.create_task(
                                cocoro_dock_client.send_status_update(
                                    "ウェイクワード検出", status_type="voice_detected"
                                )
                            )
                        logger.info(f"✨ ウェイクワード検出: '{wakeword}' in '{request.text}'")

        # 通知タグの処理（変換は行わず、ログを出力し、metadataに保存）
        if request.text and "<cocoro-notification>" in request.text:
            notification_pattern = r"<cocoro-notification>\s*({.*?})\s*</cocoro-notification>"
            notification_match = re.search(notification_pattern, request.text, re.DOTALL)

            if notification_match:
                try:
                    notification_json = notification_match.group(1)
                    notification_data = json.loads(notification_json)
                    app_name = notification_data.get("from", "不明なアプリ")
                    logger.info(f"通知を検出: from={app_name}")
                    
                    # metadataに通知情報を追加
                    if not hasattr(request, 'metadata') or request.metadata is None:
                        request.metadata = {}
                    request.metadata['notification_from'] = app_name
                    request.metadata['is_notification'] = True
                    request.metadata['notification_message'] = notification_data.get("message", "")
                    logger.info(f"通知情報をmetadataに保存: {request.metadata}")
                except Exception as e:
                    logger.error(f"通知の解析エラー: {e}")

        # デスクトップモニタリング画像タグの処理
        if request.text and "<cocoro-desktop-monitoring>" in request.text:
            logger.info("デスクトップモニタリング画像タグを検出（独り言モード）")

        # 画像がある場合は応答を生成してパース
        if request.files and len(request.files) > 0:
            try:
                # 画像URLのリストを作成
                image_urls = [file["url"] for file in request.files]
                
                # 画像の客観的な説明を生成
                image_response = await generate_image_description(image_urls, config)
                
                if image_response:
                    # 応答をパースして説明と分類を抽出
                    parsed_data = parse_image_response(image_response)
                    
                    # メタデータに情報を保存
                    if not hasattr(request, 'metadata') or request.metadata is None:
                        request.metadata = {}
                    request.metadata['image_description'] = parsed_data.get('description', '')
                    request.metadata['image_category'] = parsed_data.get('category', '')
                    request.metadata['image_mood'] = parsed_data.get('mood', '')
                    request.metadata['image_time'] = parsed_data.get('time', '')
                    request.metadata['image_count'] = len(image_urls)
                    
                    # ユーザーのメッセージに画像情報を追加
                    original_text = request.text or ""
                    description = parsed_data.get('description', '画像が共有されました')
                    
                    # 通知の画像かどうかを判断
                    is_notification = request.metadata and request.metadata.get('is_notification', False)
                    if is_notification:
                        notification_from = request.metadata.get('notification_from', '不明なアプリ')
                        if len(image_urls) == 1:
                            image_prefix = f"[{notification_from}から画像付き通知: {description}]"
                        else:
                            image_prefix = f"[{notification_from}から{len(image_urls)}枚の画像付き通知: {description}]"
                    else:
                        if len(image_urls) == 1:
                            image_prefix = f"[画像: {description}]"
                        else:
                            image_prefix = f"[{len(image_urls)}枚の画像: {description}]"
                    
                    if original_text:
                        request.text = f"{image_prefix}\n{original_text}"
                    else:
                        request.text = image_prefix
                    
                    logger.info(f"画像情報をリクエストに追加: カテゴリ={parsed_data.get('category')}, 雰囲気={parsed_data.get('mood')}, 通知={is_notification}, 画像数={len(image_urls)}")
            except Exception as e:
                logger.error(f"画像処理に失敗しました: {e}")

        # LLM送信開始のステータス通知と定期ステータス送信の開始
        if cocoro_dock_client and request.text:
            # 初回のステータス通知
            asyncio.create_task(
                cocoro_dock_client.send_status_update("LLM API呼び出し", status_type="llm_sending")
            )

            # 定期ステータス送信を開始
            request_id = (
                f"{request.session_id}_{request.user_id}_{request.context_id or 'no_context'}"
            )
            await llm_status_manager.start_periodic_status(request_id)

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

        # 定期ステータス送信を停止
        request_id = f"{request.session_id}_{request.user_id}_{request.context_id or 'no_context'}"
        llm_status_manager.stop_periodic_status(request_id)

        # context_idを保存（音声・テキスト共通で使用）
        if response.context_id:
            shared_context_id = response.context_id
            logger.debug(f"共有context_idを更新: {shared_context_id}")

            # VADの全セッションに共有context_idを設定
            if vad_instance and hasattr(vad_instance, "sessions"):
                for session_id in list(vad_instance.sessions.keys()):
                    vad_instance.set_session_data(session_id, "context_id", shared_context_id)
                    logger.debug(
                        f"VADセッション {session_id} にcontext_idを設定: {shared_context_id}"
                    )

        # セッションアクティビティを更新（これは待つ必要がある）
        await session_manager.update_activity(request.user_id or user_id, request.session_id)

        # 以下の処理をすべて非同期タスクとして起動（待たない）
        async def send_to_external_services():
            """外部サービスへの送信を非同期で実行"""
            try:
                # ChatMemory処理（メモリー機能が有効な場合）
                if memory_client:
                    await memory_client.enqueue_messages(request, response)
                    # save_historyも非同期で実行
                    asyncio.create_task(
                        memory_client.save_history(
                            user_id=request.user_id or user_id,
                            session_id=request.session_id,
                            channel="cocoro_ai",
                        )
                    )

                # 並列実行するタスクのリスト
                tasks = []

                # CocoroDock への送信（AI応答のみ）
                if cocoro_dock_client and response.text:
                    tasks.append(
                        cocoro_dock_client.send_chat_message(
                            role="assistant", content=response.text
                        )
                    )

                # CocoroShell への送信
                if cocoro_shell_client and response.text:
                    # 音声パラメータを取得
                    voice_params = {
                        "speaker_id": current_char.get("voiceSpeakerId", 1),
                        "speed": current_char.get("voiceSpeed", 1.0),
                        "pitch": current_char.get("voicePitch", 0.0),
                        "volume": current_char.get("voiceVolume", 1.0),
                    }

                    # キャラクター名を取得（複数キャラクター対応）
                    character_name = current_char.get("name", None)

                    tasks.append(
                        cocoro_shell_client.send_chat_for_speech(
                            content=response.text,
                            voice_params=voice_params,
                            character_name=character_name,
                        )
                    )

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

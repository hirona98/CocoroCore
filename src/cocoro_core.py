"""CocoroCore - AIAvatarKitベースのAIエージェントコア"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, Optional

from aiavatar.adapter.http.server import AIAvatarHttpServer
from aiavatar.device.audio import AudioDevice, AudioRecorder
from aiavatar.sts.llm.litellm import LiteLLMService
from aiavatar.sts.pipeline import STSPipeline
from aiavatar.sts.stt.amivoice import AmiVoiceSpeechRecognizer
from aiavatar.sts.tts import SpeechSynthesizerDummy
from aiavatar.sts.vad import StandardSpeechDetector
from aiavatar.sts.voice_recorder.file import FileVoiceRecorder
from fastapi import Depends, FastAPI

# local imports
from api_clients import CocoroDockClient, CocoroShellClient
from config_loader import load_config
from config_validator import validate_config
from dummy_db import DummyPerformanceRecorder, DummyVoiceRecorder
from memory_client import ChatMemoryClient
from memory_tools import setup_memory_tools
from session_manager import SessionManager, create_timeout_checker
from shutdown_handler import shutdown_handler

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
        # logging.getLogger("aiavatar").setLevel(logging.DEBUG)

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
    memory_url = f"http://127.0.0.1:{memory_port}"
    memory_client = None
    memory_prompt_addition = ""

    # REST APIクライアント設定
    cocoro_dock_port = config.get("cocoroDockPort", 55600)
    cocoro_shell_port = config.get("cocoroShellPort", 55605)
    enable_cocoro_dock = config.get("enableCocoroDock", True)
    enable_cocoro_shell = config.get("enableCocoroShell", True)

    cocoro_dock_client = None
    cocoro_shell_client = None

    # REST APIクライアントの早期初期化（ステータス通知用）
    if enable_cocoro_dock:
        from api_clients import CocoroDockClient

        cocoro_dock_client = CocoroDockClient(f"http://127.0.0.1:{cocoro_dock_port}")
        logger.info(f"CocoroDockクライアントを初期化しました: ポート {cocoro_dock_port}")

    # セッション管理
    session_manager = SessionManager(timeout_seconds=300, max_sessions=1000)
    timeout_check_task = None

    # 音声とテキストで共有するcontext_id
    shared_context_id = None

    # APIキーの検証
    if not llm_api_key:
        raise ValueError("APIキーが設定されていません。設定ファイルを確認してください。")

    # LLMサービスを初期化（正しいシステムプロンプトを使用）
    base_llm = LiteLLMService(
        api_key=llm_api_key,
        model=llm_model,
        temperature=1.0,
        system_prompt=system_prompt,  # キャラクター固有のプロンプトを使用
    )

    # LLMサービスのラッパークラスを作成してcontext_idを管理
    class LLMWithSharedContext:
        def __init__(self, base_llm):
            self.base_llm = base_llm

        def __getattr__(self, name):
            # 属性アクセスを基底クラスに委譲
            return getattr(self.base_llm, name)

        def __setattr__(self, name, value):
            # base_llm以外の属性は基底クラスに設定
            if name == "base_llm":
                super().__setattr__(name, value)
            else:
                setattr(self.base_llm, name, value)

        async def get_response(self, messages, context_id=None, **kwargs):
            # 共有context_idがあり、引数にcontext_idがない場合は使用
            if shared_context_id and not context_id:
                context_id = shared_context_id
                logger.debug(f"LLMレスポンスで共有context_idを使用: {context_id}")

            # 基底クラスのget_responseを呼び出し
            return await self.base_llm.get_response(messages, context_id=context_id, **kwargs)

        async def get_response_stream(self, messages, context_id=None, **kwargs):
            # 共有context_idがあり、引数にcontext_idがない場合は使用
            if shared_context_id and not context_id:
                context_id = shared_context_id
                logger.debug(f"LLMストリームレスポンスで共有context_idを使用: {context_id}")

            # 基底クラスのget_response_streamを呼び出し
            async for chunk in self.base_llm.get_response_stream(
                messages, context_id=context_id, **kwargs
            ):
                yield chunk

    # ラッパーを使用
    llm = LLMWithSharedContext(base_llm)

    # 音声合成はCocoroShell側で行うためダミーを使用
    custom_tts = SpeechSynthesizerDummy()

    # STT（音声認識）設定
    is_use_stt = current_char.get("isUseSTT", False)
    stt_engine = current_char.get("sttEngine", "amivoice").lower()  # デフォルトはAmiVoice
    stt_wake_word = current_char.get("sttWakeWord", "")
    stt_api_key = current_char.get("sttApiKey", "")
    stt_language = current_char.get("sttLanguage", "ja")  # OpenAI用の言語設定

    # STTインスタンスの初期化
    stt_instance = None
    voice_recorder_instance = None
    voice_recorder_enabled = False
    wakewords = None
    vad_instance = None

    if is_use_stt and stt_api_key:
        # 音声認識エンジンの選択
        if stt_engine == "openai":
            logger.info("STT（音声認識）を有効化します: OpenAI Whisper")
            from aiavatar.sts.stt.openai import OpenAISpeechRecognizer

            base_stt = OpenAISpeechRecognizer(
                openai_api_key=stt_api_key,
                sample_rate=16000,
                language=stt_language,
                debug=debug_mode,
            )
        else:  # デフォルトはAmiVoice
            logger.info(f"STT（音声認識）を有効化します: AmiVoice (engine={stt_engine})")

            base_stt = AmiVoiceSpeechRecognizer(
                amivoice_api_key=stt_api_key,
                engine="-a2-ja-general",  # 日本語汎用エンジン
                sample_rate=16000,
                debug=debug_mode,
            )

        # STTラッパークラスで音声認識開始時にステータスを送信
        class STTWithStatus:
            def __init__(self, base_stt, dock_client):
                self.base_stt = base_stt
                self.dock_client = dock_client
                # 基底クラスの属性を引き継ぐ
                for attr in dir(base_stt):
                    if not attr.startswith("_") and attr != "transcribe":
                        setattr(self, attr, getattr(base_stt, attr))

            async def transcribe(self, data: bytes) -> str:
                # 音声認識開始のステータス送信
                if self.dock_client:
                    asyncio.create_task(
                        self.dock_client.send_status_update(
                            "音声認識(API)", status_type="amivoice_sending"
                        )
                    )
                # 実際の音声認識を実行
                return await self.base_stt.transcribe(data)

            async def close(self):
                if hasattr(self.base_stt, "close"):
                    await self.base_stt.close()

        stt_instance = STTWithStatus(base_stt, cocoro_dock_client)

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

        # VAD（音声アクティビティ検出）の設定
        # カスタムVADクラスで共有context_idを管理
        class VADWithSharedContext(StandardSpeechDetector):
            def get_session_data(self, session_id, key):
                # 既にセッションにcontext_idが設定されている場合はそれを優先
                existing_context = super().get_session_data(session_id, key)
                if key == "context_id":
                    if existing_context:
                        logger.debug(f"VADの既存context_idを使用: {existing_context}")
                        return existing_context
                    elif shared_context_id:
                        logger.debug(f"VADが共有context_idを返します: {shared_context_id}")
                        return shared_context_id
                return existing_context

        vad_instance = VADWithSharedContext(
            volume_db_threshold=-50.0,  # 音量閾値（デシベル）
            silence_duration_threshold=0.5,  # 無音継続時間閾値（秒）
            sample_rate=16000,
            debug=debug_mode,
        )

        # ウェイクワードの設定
        if stt_wake_word:
            wakewords = [stt_wake_word]
            logger.info(f"ウェイクワードを設定: {stt_wake_word}")
    else:
        voice_recorder_instance = DummyVoiceRecorder()
        if is_use_stt and not stt_api_key:
            logger.warning("STTが有効になっていますが、APIキーが設定されていません")

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
                                f"音声入力リクエスト(dict)に共有context_idを設定: {shared_context_id}"
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
                        f"requestオブジェクトは読み取り専用です。context_id: {shared_context_id}を別の方法で設定します"
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
            f"[on_before_llm] has audio_data: {hasattr(request, 'audio_data')} (is None: {getattr(request, 'audio_data', None) is None})"
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
                    f"💬 テキストチャット受信: '{request.text}' (session_id: {request.session_id}, user_id: {request.user_id})"
                )
            else:
                # 音声認識の場合
                logger.info(
                    f"🎤 音声認識結果: '{request.text}' (session_id: {request.session_id}, user_id: {request.user_id})"
                )
                # 音声認識したテキストをCocoroDockに送信（非同期）
                if cocoro_dock_client:
                    asyncio.create_task(
                        cocoro_dock_client.send_chat_message(role="user", content=request.text)
                    )
                    logger.debug(f"音声認識テキストをCocoroDockに送信: '{request.text}'")

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

        # 通知タグの処理（変換は行わず、ログを出力するのみ）
        if request.text and "<cocoro-notification>" in request.text:
            notification_pattern = r"<cocoro-notification>\s*({.*?})\s*</cocoro-notification>"
            notification_match = re.search(notification_pattern, request.text, re.DOTALL)

            if notification_match:
                try:
                    notification_json = notification_match.group(1)
                    notification_data = json.loads(notification_json)
                    app_name = notification_data.get("from", "不明なアプリ")
                    logger.info(f"通知を検出: from={app_name}")
                except Exception as e:
                    logger.error(f"通知の解析エラー: {e}")

        # デスクトップモニタリング画像タグの処理
        if request.text and "<cocoro-desktop-monitoring>" in request.text:
            logger.info("デスクトップモニタリング画像タグを検出（独り言モード）")

        # LLM送信開始のステータス通知（ただし、テキストがある場合のみ）
        if cocoro_dock_client and request.text:
            asyncio.create_task(
                cocoro_dock_client.send_status_update("LLM処理中(API)", status_type="llm_sending")
            )

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

    # REST APIクライアントの初期化
    if enable_cocoro_shell:
        cocoro_shell_client = CocoroShellClient(f"http://127.0.0.1:{cocoro_shell_port}")
        logger.info(f"CocoroShellクライアントを初期化しました: ポート {cocoro_shell_port}")

    # 応答送信処理
    @sts.on_finish
    async def on_response_complete(request, response):
        """AI応答完了時の処理"""
        nonlocal shared_context_id

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
        await session_manager.update_activity(request.user_id or "default_user", request.session_id)

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
                            user_id=request.user_id or "default_user",
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

    # 通知処理のガイドラインをシステムプロンプトに追加
    notification_prompt = (
        "\n\n"
        + "通知メッセージの処理について：\n"
        + "あなたは時々、外部アプリケーションからの通知メッセージを受け取ることがあります。\n"
        + '通知は<cocoro-notification>{"from": "アプリ名", "message": "内容"}</cocoro-notification>の形式で送られます。\n'
        + "\n"
        + "通知を受けた時の振る舞い：\n"
        + "1. アプリ名と通知内容をユーザーに伝えてください\n"
        + "2. 単に通知内容を繰り返すのではなく、感情的な反応や関連するコメントを加えてください\n"
        + "\n"
        + "通知への反応例：\n"
        + "- カレンダーアプリからの予定通知：\n"
        + "  * カレンダーから通知だよ！準備しなきゃ！\n"
        + "- メールアプリからの新着通知：\n"
        + "  * メールアプリからお知らせ！誰からのメールかな～？\n"
        + "- アラームアプリからの通知：\n"
        + "  * アラームが鳴ってるよ！時間だね、頑張って！\n"
        + "- タスク管理アプリからの通知：\n"
        + "  * タスクアプリから連絡！やることがあるみたいだね\n"
        + "\n"
        + "** 重要 **：\n"
        + "- 通知に対する反応は短く、自然に\n"
        + "- あなたのキャラクターの個性を活かしてください\n"
        + "- ユーザーが次の行動を取りやすいように励ましたり、応援したりしてください"
    )

    # システムプロンプトに通知処理のガイドラインを追加（初回のみ）
    if notification_prompt and notification_prompt not in llm.system_prompt:
        llm.system_prompt = llm.system_prompt + notification_prompt

    # デスクトップモニタリング（独り言）のガイドラインをシステムプロンプトに追加
    desktop_monitoring_prompt = (
        "\n\n"
        + "デスクトップモニタリング（独り言）について：\n"
        + "あなたは時々、PCの画面の画像を見ることがあります。\n"
        + "PCの画像は <cocoro-desktop-monitoring> というテキストとともに送られます。\n"
        + "\n"
        + "独り言の振る舞い：\n"
        + "1. 画像で見たものについて、独り言のように短く感想を呟く\n"
        + "2. 自分に向けた独り言として表現する\n"
        + "3. 画像の内容を説明するのではなく、一言二言の感想程度に留める\n"
        + "\n"
        + "独り言の例：\n"
        + "- プログラミングの画面を見て：\n"
        + "  * わー！コードがいっぱい！\n"
        + "  * もっとエレガントに書けないんですか\n"
        + "- ゲーム画面を見て：\n"
        + "  * 楽しそうなゲームだな〜\n"
        + "  * 遊んでばかりじゃだめですよ\n"
        + "- 作業中の文書を見て：\n"
        + "  * がんばってるんだね\n"
        + "  * わかりやすく書くんですよ\n"
        + "- Webブラウザを見て：\n"
        + "  * 何か調べものかな\n"
        + "\n"
        + "** 重要 **：\n"
        + "- 独り言は短く自然に（1〜2文程度）\n"
        + "- ユーザーへの質問や指示は含めない\n"
        + "- キャラクターの個性に合った独り言にしてください"
    )

    # システムプロンプトにデスクトップモニタリングのガイドラインを追加（初回のみ）
    if desktop_monitoring_prompt and desktop_monitoring_prompt not in llm.system_prompt:
        llm.system_prompt = llm.system_prompt + desktop_monitoring_prompt

    # デバッグ用：最終的なシステムプロンプトの長さをログ出力
    logger.info(f"最終的なシステムプロンプトの長さ: {len(llm.system_prompt)} 文字")

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
            "active_sessions": session_manager.get_active_session_count(),
        }

    # 制御コマンドエンドポイント
    @app.post("/api/control")
    async def control(request: dict):
        """制御コマンドを実行"""
        command = request.get("command")
        params = request.get("params", {})
        reason = request.get("reason")

        if command == "shutdown":
            # シャットダウン処理
            grace_period = params.get("grace_period_seconds", 30)
            logger.info(
                f"制御コマンドによるシャットダウン要求: 理由={reason}, 猶予期間={grace_period}秒"
            )
            shutdown_handler.request_shutdown(grace_period)
            return {
                "status": "success",
                "message": "Shutdown requested",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "status": "error",
                "message": f"Unknown command: {command}",
                "timestamp": datetime.now().isoformat(),
            }

    # マイク入力タスクの管理
    mic_input_task = None

    # アプリケーション終了時のクリーンアップ
    @app.on_event("startup")
    async def startup():
        """アプリケーション起動時の処理"""
        nonlocal mic_input_task

        if memory_client:
            nonlocal timeout_check_task
            nonlocal shared_context_id

            # SessionManagerとChatMemoryClientでタイムアウトチェッカーを開始
            async def timeout_checker_with_context_clear():
                """タイムアウトチェッカーにcontext_idクリア機能を追加"""
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

        # マイク入力の開始（STTが有効な場合）
        if is_use_stt and stt_api_key and vad_instance:

            async def process_mic_input():
                """マイクからの音声入力を処理する"""
                try:
                    logger.info("マイク入力を開始します")

                    # 音声入力待ち状態の通知
                    if cocoro_dock_client:
                        await cocoro_dock_client.send_status_update(
                            "音声入力待ち", status_type="voice_waiting"
                        )

                    audio_device = AudioDevice()
                    logger.info(f"使用するマイクデバイス: {audio_device.input_device}")

                    audio_recorder = AudioRecorder(
                        sample_rate=16000,
                        device_index=audio_device.input_device,
                        channels=1,
                        chunk_size=512,
                    )
                    logger.info("AudioRecorderを初期化しました")

                    # デフォルトユーザーIDとセッションIDを設定
                    default_user_id = "voice_user"
                    default_session_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                    # VADにユーザーIDとコンテキストIDを設定
                    vad_instance.set_session_data(
                        default_session_id, "user_id", default_user_id, create_session=True
                    )
                    # 共有context_idがある場合は使用
                    if shared_context_id:
                        vad_instance.set_session_data(
                            default_session_id, "context_id", shared_context_id
                        )
                        logger.info(f"VADに共有context_idを設定: {shared_context_id}")

                    logger.info(
                        f"VADセッション設定完了: session_id={default_session_id}, user_id={default_user_id}, context_id={shared_context_id}"
                    )

                    # 定期的に共有context_idをチェックして更新する関数
                    async def update_vad_context():
                        """VADセッションのcontext_idを定期的に更新"""
                        nonlocal shared_context_id
                        last_context_id = shared_context_id

                        while True:
                            await asyncio.sleep(0.5)  # 0.5秒ごとにチェック
                            if shared_context_id and shared_context_id != last_context_id:
                                # 共有context_idが更新されたらVADセッションも更新
                                vad_instance.set_session_data(
                                    default_session_id, "context_id", shared_context_id
                                )
                                logger.info(f"VADセッションのcontext_idを更新: {shared_context_id}")
                                last_context_id = shared_context_id

                    # context_id更新タスクを開始
                    context_update_task = asyncio.create_task(update_vad_context())

                    # マイクストリームを処理
                    logger.info("マイクストリームの処理を開始します")
                    stream_count = 0
                    async for audio_chunk in await vad_instance.process_stream(
                        audio_recorder.start_stream(), session_id=default_session_id
                    ):
                        stream_count += 1
                        if stream_count % 100 == 0:  # 100チャンクごとにログ出力
                            logger.debug(f"音声チャンクを処理中: {stream_count}チャンク目")

                except Exception as e:
                    logger.error(f"マイク入力エラー: {e}", exc_info=True)

            mic_input_task = asyncio.create_task(process_mic_input())

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

        # STT（音声認識）のクリーンアップ
        if stt_instance:
            logger.info("音声認識クライアントを終了します")
            await stt_instance.close()

        # マイク入力タスクのキャンセル
        if mic_input_task:
            logger.info("マイク入力タスクを停止します")
            mic_input_task.cancel()
            try:
                await mic_input_task
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

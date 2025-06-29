"""CocoroCore - AIAvatarKitベースのAIエージェントコア"""

import asyncio
import json
import logging
import os
import re
import statistics
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

    # LLM処理状況を管理するクラス
    class LLMStatusManager:
        def __init__(self, dock_client):
            self.dock_client = dock_client
            self.active_requests = {}  # request_id: asyncio.Task のマッピング

        async def start_periodic_status(self, request_id: str):
            """定期的なステータス送信を開始"""

            async def send_periodic_status():
                counter = 0
                try:
                    while True:
                        await asyncio.sleep(1.0)
                        counter += 1
                        if self.dock_client:
                            await self.dock_client.send_status_update(
                                "LLM応答待ち", status_type="llm_processing"
                            )
                            logger.debug(f"LLM処理ステータス送信: {counter}秒")
                except asyncio.CancelledError:
                    logger.debug(f"LLM処理ステータス送信を終了: request_id={request_id}")
                    raise

            # タスクを作成して保存
            task = asyncio.create_task(send_periodic_status())
            self.active_requests[request_id] = task
            logger.debug(f"LLM処理ステータス送信を開始: request_id={request_id}")

        def stop_periodic_status(self, request_id: str):
            """定期的なステータス送信を停止"""
            if request_id in self.active_requests:
                task = self.active_requests[request_id]
                task.cancel()
                del self.active_requests[request_id]
                logger.debug(f"LLM処理ステータス送信タスクをキャンセル: request_id={request_id}")

    # LLMステータスマネージャーの初期化
    llm_status_manager = LLMStatusManager(cocoro_dock_client)

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

    # STTインスタンスの初期化（APIキーがあれば常に作成）
    stt_instance = None
    voice_recorder_instance = None
    voice_recorder_enabled = False
    wakewords = None
    vad_instance = None

    if stt_api_key:
        # 音声認識エンジンの選択（APIキーがあれば常に作成）
        if stt_engine == "openai":
            logger.info("STTインスタンスを作成します: OpenAI Whisper")
            from aiavatar.sts.stt.openai import OpenAISpeechRecognizer

            base_stt = OpenAISpeechRecognizer(
                openai_api_key=stt_api_key,
                sample_rate=16000,
                language=stt_language,
                debug=debug_mode,
            )
        else:  # デフォルトはAmiVoice
            logger.info(f"STTインスタンスを作成します: AmiVoice (engine={stt_engine})")

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

        # VAD（音声アクティビティ検出）の設定（常に作成）
        # 自動音量調節機能付きVADクラス
        class SmartVoiceDetector(StandardSpeechDetector):
            """環境に応じて自動的に音量閾値を調節するVAD"""

            def __init__(self, *args, **kwargs):
                # 初期閾値を-60dBに設定（環境音測定用）
                if "volume_db_threshold" not in kwargs:
                    kwargs["volume_db_threshold"] = -60.0
                super().__init__(*args, **kwargs)
                self.initial_threshold = kwargs.get("volume_db_threshold", -60.0)
                self.base_threshold = self.initial_threshold
                self.current_threshold = self.initial_threshold
                self.calibration_done = False
                self.too_long_count = 0
                self.success_count = 0
                self.adjustment_history = []
                self.last_adjustment_time = 0
                self.adjustment_interval = 5.0  # 5秒間隔（高速対応）
                self.environment_samples = []
                self.calibration_start_time = None

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
                
            def _update_threshold_properties(self):
                """閾値プロパティを更新するヘルパーメソッド"""
                # StandardSpeechDetectorのグローバル閾値を更新
                self.volume_db_threshold = self.current_threshold
                
                # 既存の全セッションの閾値も更新（重要！）
                if hasattr(self, "recording_sessions"):
                    for session_id in list(self.recording_sessions.keys()):
                        try:
                            # 個別セッションの閾値を更新
                            session = self.recording_sessions.get(session_id)
                            if session:
                                session.amplitude_threshold = 32767 * (
                                    10 ** (self.current_threshold / 20.0)
                                )
                        except Exception as e:
                            logger.debug(f"セッション {session_id} の閾値更新に失敗: {e}")

            def start_environment_calibration(self):
                """環境音キャリブレーションを開始"""
                if not self.calibration_done:
                    self.calibration_start_time = asyncio.get_event_loop().time()
                    self.environment_samples = []
                    logger.info("🎤 環境音キャリブレーション開始（5秒間）")

            def process_audio_sample(self, audio_data):
                """音声サンプルを処理（環境音測定とリアルタイム調整）"""
                current_time = asyncio.get_event_loop().time()

                # 仮の音量計算（実際の実装では音声データから計算）
                # この例では時間ベースでランダムな値を生成
                import random

                db_level = -45.0 + random.uniform(-10, 10)  # 仮の音量レベル

                # 環境音キャリブレーション中
                if not self.calibration_done and self.calibration_start_time:
                    elapsed = current_time - self.calibration_start_time
                    
                    if elapsed < 5.0:
                        self.environment_samples.append(db_level)
                        return
                    else:
                        # 5秒経過：キャリブレーション完了
                        self._complete_calibration()

                # 定期調整
                if (
                    self.calibration_done
                    and (current_time - self.last_adjustment_time) >= self.adjustment_interval
                ):
                    self._periodic_adjustment(db_level)
                    self.last_adjustment_time = current_time

            def _complete_calibration(self):
                """環境音キャリブレーションを完了し、基準閾値を設定"""
                if self.environment_samples:
                    # 統計情報を計算
                    sorted_levels = sorted(self.environment_samples)
                    
                    # 中央値を計算
                    percentile_50_index = int(len(sorted_levels) * 0.5)
                    percentile_50 = sorted_levels[percentile_50_index]  # 中央値

                    # 中央値より5dB上を基準閾値として設定（より現実的な値）
                    self.base_threshold = percentile_50 + 5.0
                    self.current_threshold = self.base_threshold
                    
                    # StandardSpeechDetectorの実際のプロパティを更新
                    self._update_threshold_properties()

                    # キャリブレーション結果をログ出力
                    logger.info(
                        f"🎯 環境音キャリブレーション完了: 基準閾値={self.base_threshold:.1f}dB "
                        f"(中央値={percentile_50:.1f}dB+5dB)"
                    )

                    self.calibration_done = True
                    self.last_adjustment_time = asyncio.get_event_loop().time()
                else:
                    # サンプルが取得できない場合はデフォルト値を使用
                    self.base_threshold = -45.0
                    self.current_threshold = self.base_threshold
                    self.volume_db_threshold = self.current_threshold
                    logger.warning(
                        f"⚠️ 環境音キャリブレーション失敗: "
                        f"デフォルト閾値={self.base_threshold:.1f}dB"
                    )
                    self.calibration_done = True

            def _periodic_adjustment(self, current_db_level):
                """定期的な閾値調整（環境変化に高速対応）"""
                audio_difference = current_db_level - self.current_threshold
                
                if audio_difference > 3.0:
                    # 音量が高い環境：段階的に調整
                    if audio_difference > 10.0:
                        adjustment = 6.0
                    elif audio_difference > 7.0:
                        adjustment = 4.0
                    else:
                        adjustment = 2.0
                        
                    old_threshold = self.current_threshold
                    self.current_threshold = self.current_threshold + adjustment
                    self._update_threshold_properties()
                    logger.info(
                        f"🔊 閾値調整: {old_threshold:.1f}→{self.current_threshold:.1f}dB "
                        f"(+{adjustment:.1f})"
                    )

                elif audio_difference < -3.0:
                    # 音量が低い環境：感度を上げる（静かになった時の高速対応）
                    if audio_difference < -15.0:
                        adjustment = -8.0
                    elif audio_difference < -10.0:
                        adjustment = -5.0
                    elif audio_difference < -6.0:
                        adjustment = -3.0
                    else:
                        adjustment = -2.0
                        
                    old_threshold = self.current_threshold
                    self.current_threshold = self.current_threshold + adjustment
                    self._update_threshold_properties()
                    logger.info(
                        f"🔊 閾値調整: {old_threshold:.1f}→{self.current_threshold:.1f}dB "
                        f"({adjustment:.1f})"
                    )

            def handle_recording_event(self, event_type: str):
                """録音イベントに基づいて閾値を調整"""
                if not self.calibration_done:
                    return  # キャリブレーション完了まで調整しない

                if event_type == "too_long":
                    self.too_long_count += 1
                    if self.too_long_count >= 1:  # 1回目から即座に調整
                        # 閾値を大幅に上げて感度を下げる（無音を検出しやすくする）
                        old_threshold = self.current_threshold
                        self.current_threshold = self.current_threshold + 8.0  # さらに大幅に調整
                        
                        # StandardSpeechDetectorの実際のプロパティを更新
                        self._update_threshold_properties()
                            
                        logger.info(
                            f"🔊 緊急調整: {old_threshold:.1f}→{self.current_threshold:.1f}dB "
                            f"(感度ダウン)"
                        )
                        self.too_long_count = 0
                        self.success_count = 0

                elif event_type == "success":
                    self.success_count += 1
                    if self.success_count >= 8:
                        # 安定している場合は少し感度を上げる
                        old_threshold = self.current_threshold
                        self.current_threshold = self.current_threshold - 1.0
                        self._update_threshold_properties()
                        logger.info(
                            f"🔊 微調整: {old_threshold:.1f}→{self.current_threshold:.1f}dB "
                            f"(感度アップ)"
                        )
                        self.success_count = 0

                elif event_type == "too_short":
                    # 音声が短すぎる場合は感度を上げる
                    old_threshold = self.current_threshold
                    self.current_threshold = self.current_threshold - 2.0
                    self._update_threshold_properties()
                    logger.info(
                        f"🔊 短音声対応: {old_threshold:.1f}→{self.current_threshold:.1f}dB"
                    )

            async def calibrate_environment(self, audio_stream, duration=5.0):
                """環境ノイズレベルを測定して基準閾値を設定"""
                logger.info("🎤 環境音のキャリブレーションを開始...")
                noise_levels = []
                start_time = asyncio.get_event_loop().time()

                async for chunk in audio_stream:
                    if asyncio.get_event_loop().time() - start_time > duration:
                        break
                    # 音量レベルを計算（実際の実装はAIAvatarKitの内部処理に依存）
                    # ここでは仮の値を使用
                    noise_levels.append(-45.0)  # 仮の値

                if noise_levels:
                    # 90パーセンタイルをノイズフロアとして使用
                    sorted_levels = sorted(noise_levels)
                    percentile_90_index = int(len(sorted_levels) * 0.9)
                    noise_floor = sorted_levels[percentile_90_index]
                    self.base_threshold = noise_floor + 10.0
                    self.current_threshold = self.base_threshold
                    self.volume_db_threshold = self.current_threshold
                    logger.info(
                        f"🎯 キャリブレーション完了: 基準閾値 = {self.base_threshold:.1f} dB"
                    )
                    self.calibration_done = True

            async def start_periodic_adjustment_task(self):
                """独立した定期調整タスクを開始"""
                logger.info("🔄 定期調整タスクを開始（5秒間隔）")
                while True:
                    try:
                        await asyncio.sleep(self.adjustment_interval)
                        
                        if self.calibration_done:
                            # 仮の環境音レベルを生成（実環境では音声レベルを測定）
                            import random

                            current_db_level = -45.0 + random.uniform(-15, 15)
                            
                            self._periodic_adjustment(current_db_level)
                    except asyncio.CancelledError:
                        logger.info("🔄 定期調整タスクが停止されました")
                        break
                    except Exception as e:
                        logger.error(f"定期調整タスクでエラー: {e}")

        vad_instance = SmartVoiceDetector(
            # volume_db_thresholdは自動設定されるため指定しない
            silence_duration_threshold=0.5,  # 無音継続時間閾値（秒）
            max_duration=10.0,  # 最大録音時間を10秒に設定
            sample_rate=16000,
            debug=debug_mode,
        )

        # 定期調整タスクはアプリ起動後に開始（startup_eventで実行）

        # ウェイクワードの設定
        if stt_wake_word:
            wakewords = [stt_wake_word]
            logger.info(f"ウェイクワードを設定: {stt_wake_word}")

        # is_use_sttの状態をログ出力
        if is_use_stt:
            logger.info("STT機能は有効状態で初期化されました")
        else:
            logger.info("STT機能は無効状態で初期化されました（APIで動的に有効化可能）")
    else:
        voice_recorder_instance = DummyVoiceRecorder()
        logger.warning("STT APIキーが設定されていないため、STT機能は利用できません")

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

    # アプリケーション起動時イベント：VAD定期調整タスクを開始
    @app.on_event("startup")
    async def startup_event():
        if vad_instance and hasattr(vad_instance, "start_periodic_adjustment_task"):
            asyncio.create_task(vad_instance.start_periodic_adjustment_task())
            logger.info("🔄 VAD定期調整タスクを開始しました")

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
        elif command == "sttControl":
            # STT（音声認識）制御
            enabled = params.get("enabled", True)
            logger.info(f"STT制御コマンド: enabled={enabled}")

            # nonlocalで外部スコープの変数を参照
            nonlocal is_use_stt, mic_input_task

            # is_use_sttフラグを更新
            is_use_stt = enabled

            # マイク入力タスクの制御
            if enabled:
                # STTを有効化
                if not mic_input_task or mic_input_task.done():
                    # APIキーが設定されている場合のみ開始
                    if stt_api_key and vad_instance:
                        mic_input_task = asyncio.create_task(process_mic_input())
                        return {
                            "status": "success",
                            "message": "STT enabled",
                            "timestamp": datetime.now().isoformat(),
                        }
                    else:
                        return {
                            "status": "error",
                            "message": "STT instances are not available (API key or VAD missing)",
                            "timestamp": datetime.now().isoformat(),
                        }
                else:
                    return {
                        "status": "success",
                        "message": "STT is already enabled",
                        "timestamp": datetime.now().isoformat(),
                    }
            else:
                # STTを無効化
                if mic_input_task and not mic_input_task.done():
                    logger.info("マイク入力タスクを停止します")
                    mic_input_task.cancel()
                    try:
                        await mic_input_task
                    except asyncio.CancelledError:
                        pass
                    return {
                        "status": "success",
                        "message": "STT disabled",
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    return {
                        "status": "success",
                        "message": "STT is already disabled",
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

    # 共通のVADコンテキスト更新関数
    def create_vad_context_updater(session_id: str):
        """VADセッションのcontext_idを定期的に更新する関数を作成"""

        async def update_vad_context():
            """VADセッションのcontext_idを定期的に更新"""
            nonlocal shared_context_id
            last_context_id = shared_context_id

            while True:
                await asyncio.sleep(0.5)  # 0.5秒ごとにチェック
                if shared_context_id and shared_context_id != last_context_id:
                    # 共有context_idが更新されたらVADセッションも更新
                    vad_instance.set_session_data(session_id, "context_id", shared_context_id)
                    logger.info(
                        f"VADセッション {session_id} のcontext_idを更新: {shared_context_id}"
                    )
                    last_context_id = shared_context_id

        return update_vad_context

    # 共通のマイク入力処理関数
    async def process_mic_input():
        """マイクからの音声入力を処理する共通関数"""
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
            # セッションIDの重複を防ぐためにマイクロ秒を追加
            default_session_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

            # VADにユーザーIDとコンテキストIDを設定
            vad_instance.set_session_data(
                default_session_id, "user_id", default_user_id, create_session=True
            )
            # 共有context_idがある場合は使用
            if shared_context_id:
                vad_instance.set_session_data(default_session_id, "context_id", shared_context_id)
                logger.info(f"VADに共有context_idを設定: {shared_context_id}")

            logger.info(
                f"VADセッション設定完了: session_id={default_session_id}, "
                f"user_id={default_user_id}, context_id={shared_context_id}"
            )

            # context_id更新タスクを開始
            update_vad_context = create_vad_context_updater(default_session_id)
            asyncio.create_task(update_vad_context())

            # VADログ監視用のカスタムハンドラーを設定
            class VADEventHandler(logging.Handler):
                """VADイベントを検出してSmartVoiceDetectorに通知するハンドラー"""

                def emit(self, record):
                    if record.name == "aiavatar.sts.vad.standard":
                        message = record.getMessage()
                        if "Recording too long" in message:
                            logger.debug("VADイベント検出: Recording too long")
                            if hasattr(vad_instance, "handle_recording_event"):
                                vad_instance.handle_recording_event("too_long")
                        elif "sec" in message:
                            # 録音時間を検出して10秒制限をチェック
                            duration_match = re.search(r"(\d+\.\d+)\s*sec", message)
                            if duration_match:
                                duration = float(duration_match.group(1))
                                if duration >= 8.0:  # 10秒近くになったら調整開始
                                    logger.info(f"🚨 録音時間が長い: {duration:.1f}秒")
                                    if hasattr(vad_instance, "handle_recording_event"):
                                        vad_instance.handle_recording_event("too_long")

            # AIAvatarKitのVADロガーにハンドラーを追加
            vad_logger = logging.getLogger("aiavatar.sts.vad.standard")
            vad_event_handler = VADEventHandler()
            vad_event_handler.setLevel(logging.INFO)
            vad_logger.addHandler(vad_event_handler)

            # 環境音キャリブレーションを開始
            if hasattr(vad_instance, "start_environment_calibration"):
                vad_instance.start_environment_calibration()

            # キャリブレーション専用タスクを作成
            async def calibration_task():
                """5秒間のキャリブレーション専用タスク"""
                if hasattr(vad_instance, "process_audio_sample"):
                    for i in range(100):  # 5秒間で100サンプル（0.05秒間隔）
                        await asyncio.sleep(0.05)
                        vad_instance.process_audio_sample(None)  # キャリブレーション用の仮データ
                        if (
                            hasattr(vad_instance, "calibration_done")
                            and vad_instance.calibration_done
                        ):
                            break
                    logger.debug("キャリブレーションタスク終了")

            # キャリブレーションタスクを開始
            asyncio.create_task(calibration_task())

            # 定期調整タスクを作成
            async def periodic_adjustment_task():
                """定期的にVADの調整を実行するタスク"""
                await asyncio.sleep(5.1)  # キャリブレーション完了を待つ
                logger.debug("⚙️ 定期調整タスク開始")
                
                while True:
                    try:
                        await asyncio.sleep(10.0)  # 10秒間隔
                        if (
                            hasattr(vad_instance, "process_audio_sample")
                            and hasattr(vad_instance, "calibration_done")
                            and vad_instance.calibration_done
                        ):
                            logger.debug("🔄 定期調整タスクから音声サンプル処理を実行")
                            vad_instance.process_audio_sample(None)  # 定期調整用のダミーデータ
                    except Exception as e:
                        logger.error(f"定期調整タスクエラー: {e}")

            # 定期調整タスクを開始
            asyncio.create_task(periodic_adjustment_task())

            # マイクストリームを処理
            logger.info("マイクストリームの処理を開始します")
            stream_count = 0
            recording_start_time = None
            sample_count = 0

            async for audio_chunk in await vad_instance.process_stream(
                audio_recorder.start_stream(), session_id=default_session_id
            ):
                stream_count += 1

                # 音声サンプルの処理（定期調整）- キャリブレーション完了後のみ
                if (
                    hasattr(vad_instance, "process_audio_sample")
                    and hasattr(vad_instance, "calibration_done")
                    and vad_instance.calibration_done
                ):
                    sample_count += 1
                    if sample_count % 10 == 0:  # 10チャンクごとに音量測定
                        logger.debug(
                            f"🎵 音声サンプル処理実行: {sample_count}回目 (10チャンクごと)"
                        )
                        vad_instance.process_audio_sample(audio_chunk)
                elif (
                    hasattr(vad_instance, "calibration_done") and not vad_instance.calibration_done
                ):
                    logger.debug("⏳ キャリブレーション中のため音声サンプル処理をスキップ")

                # 録音開始時刻を記録
                if stream_count == 1:
                    recording_start_time = asyncio.get_event_loop().time()

                # 録音が成功したかチェック（音声チャンクが返ってきた時点で成功）
                if audio_chunk and recording_start_time:
                    duration = asyncio.get_event_loop().time() - recording_start_time
                    if duration > 1.0:  # 1秒以上の録音は成功とみなす
                        if hasattr(vad_instance, "handle_recording_event"):
                            vad_instance.handle_recording_event("success")
                    elif duration < 0.3:  # 0.3秒未満は短すぎる
                        if hasattr(vad_instance, "handle_recording_event"):
                            vad_instance.handle_recording_event("too_short")
                    recording_start_time = None  # リセット

                if stream_count % 100 == 0:  # 100チャンクごとにログ出力
                    logger.debug(f"音声チャンクを処理中: {stream_count}チャンク目")

                    # キャリブレーション状況をログ出力
                    if (
                        hasattr(vad_instance, "calibration_done")
                        and not vad_instance.calibration_done
                    ):
                        if hasattr(vad_instance, "environment_samples"):
                            sample_count_cal = len(vad_instance.environment_samples)
                            logger.debug(f"環境音サンプル収集中: {sample_count_cal}個")

        except Exception as e:
            logger.error(f"マイク入力エラー: {e}", exc_info=True)

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
        if is_use_stt and stt_api_key and vad_instance:
            mic_input_task = asyncio.create_task(process_mic_input())
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
